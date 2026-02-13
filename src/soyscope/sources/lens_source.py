"""Lens.org API adapter for SoyScope.

Bridges patent and scholarly literature — 200M+ scholarly records + global patents.
Uses POST endpoints with Elasticsearch Query DSL.
Bearer token required (free for academic/non-commercial).
Rate limit: 50 requests/minute.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import OAStatus, Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class LensSource(BaseSource):
    """Search adapter for the Lens.org API (scholarly + patents)."""

    SCHOLARLY_URL = "https://api.lens.org/scholarly/search"
    PATENT_URL = "https://api.lens.org/patent/search"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key=api_key)

    @property
    def name(self) -> str:
        return "lens"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        search_type = kwargs.get("search_type", "scholarly")  # "scholarly" or "patent"

        if search_type == "patent":
            return await self._search_patents(query, max_results, year_start, year_end)
        return await self._search_scholarly(query, max_results, year_start, year_end)

    async def _search_scholarly(
        self, query: str, max_results: int,
        year_start: int | None, year_end: int | None,
    ) -> SearchResult:
        must_clauses: list[dict[str, Any]] = [
            {"match": {"title": query}},
        ]

        if year_start is not None or year_end is not None:
            year_range: dict[str, Any] = {}
            if year_start is not None:
                year_range["gte"] = str(year_start)
            if year_end is not None:
                year_range["lte"] = str(year_end)
            must_clauses.append({"range": {"year_published": year_range}})

        body: dict[str, Any] = {
            "query": {"bool": {"must": must_clauses}},
            "size": min(max_results, 100),
            "from": 0,
        }

        headers = self._auth_headers()
        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.SCHOLARLY_URL,
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

                total_results = data.get("total", 0)
                results = data.get("data", [])

                for work in results:
                    paper = self._parse_scholarly(work)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "Lens scholarly HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("Lens scholarly request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching Lens scholarly for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def _search_patents(
        self, query: str, max_results: int,
        year_start: int | None, year_end: int | None,
    ) -> SearchResult:
        must_clauses: list[dict[str, Any]] = [
            {"match": {"title": query}},
        ]

        if year_start is not None or year_end is not None:
            date_range: dict[str, Any] = {}
            if year_start is not None:
                date_range["gte"] = f"{year_start}-01-01"
            if year_end is not None:
                date_range["lte"] = f"{year_end}-12-31"
            must_clauses.append({"range": {"date_published": date_range}})

        body: dict[str, Any] = {
            "query": {"bool": {"must": must_clauses}},
            "size": min(max_results, 100),
            "from": 0,
        }

        headers = self._auth_headers()
        papers: list[Paper] = []
        total_results = 0

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.PATENT_URL,
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()

                total_results = data.get("total", 0)
                results = data.get("data", [])

                for pat in results:
                    paper = self._parse_patent(pat)
                    if paper is not None:
                        papers.append(paper)

        except httpx.HTTPStatusError as exc:
            self.logger.error(
                "Lens patent HTTP error %s for query %r: %s",
                exc.response.status_code, query, exc,
            )
        except httpx.RequestError as exc:
            self.logger.error("Lens patent request error for query %r: %s", query, exc)
        except Exception:
            self.logger.exception("Unexpected error searching Lens patents for query %r", query)

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    async def get_by_doi(self, doi: str) -> Paper | None:
        body: dict[str, Any] = {
            "query": {"match": {"doi": doi}},
            "size": 1,
        }
        headers = self._auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.SCHOLARLY_URL,
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("data", [])
                if results:
                    return self._parse_scholarly(results[0])
        except httpx.HTTPStatusError as exc:
            self.logger.error("Lens HTTP error %s for DOI %r: %s", exc.response.status_code, doi, exc)
        except httpx.RequestError as exc:
            self.logger.error("Lens request error for DOI %r: %s", doi, exc)
        except Exception:
            self.logger.exception("Unexpected error fetching DOI %r from Lens", doi)
        return None

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _parse_scholarly(self, work: dict[str, Any]) -> Paper | None:
        try:
            title = work.get("title", "")
            if not title:
                return None

            abstract = work.get("abstract", "") or None

            # Authors
            authors: list[str] = []
            for auth in work.get("authors", []) or []:
                name = auth.get("display_name") or auth.get("first_name", "")
                if auth.get("last_name"):
                    name = f"{auth.get('first_name', '')} {auth['last_name']}".strip()
                if name:
                    authors.append(name)

            year = work.get("year_published")
            doi = work.get("doi")

            # External IDs
            ext_ids = work.get("external_ids", []) or []
            if not doi:
                for eid in ext_ids:
                    if eid.get("type") == "doi":
                        doi = eid.get("value")
                        break

            url = work.get("source_url") or (f"https://doi.org/{doi}" if doi else None)

            # OA status
            oa = work.get("open_access", {}) or {}
            oa_status = None
            if oa.get("is_oa"):
                oa_colour = oa.get("colour", "").lower()
                if oa_colour == "gold":
                    oa_status = OAStatus.GOLD
                elif oa_colour == "green":
                    oa_status = OAStatus.GREEN
                elif oa_colour == "hybrid":
                    oa_status = OAStatus.HYBRID
                elif oa_colour == "bronze":
                    oa_status = OAStatus.BRONZE

            venue = None
            source = work.get("source", {})
            if isinstance(source, dict):
                venue = source.get("title") or source.get("publisher")

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                doi=doi,
                url=url,
                authors=authors,
                venue=venue,
                citation_count=work.get("scholarly_citations_count"),
                open_access_status=oa_status,
                source_type=SourceType.PAPER,
                raw_metadata=work,
            )
        except Exception:
            self.logger.exception("Failed to parse Lens scholarly work: %s", work.get("lens_id"))
            return None

    def _parse_patent(self, pat: dict[str, Any]) -> Paper | None:
        try:
            title = pat.get("title", "")
            if isinstance(title, list):
                # Lens may return title as list of language variants
                title = title[0].get("text", "") if title else ""
            if not title:
                return None

            abstract = pat.get("abstract", "") or None
            if isinstance(abstract, list):
                abstract = abstract[0].get("text", "") if abstract else None

            # Inventors as authors
            authors: list[str] = []
            for inv in pat.get("inventors", []) or []:
                name = inv.get("extracted_name", {})
                if isinstance(name, dict):
                    full = f"{name.get('first_name', '')} {name.get('last_name', '')}".strip()
                elif isinstance(name, str):
                    full = name
                else:
                    full = ""
                if full:
                    authors.append(full)

            # Date
            pub_date = pat.get("date_published", "")
            year = None
            if pub_date:
                try:
                    year = int(str(pub_date)[:4])
                except (ValueError, IndexError):
                    pass

            lens_id = pat.get("lens_id", "")
            url = f"https://www.lens.org/lens/patent/{lens_id}" if lens_id else None

            # Applicant/assignee as venue
            venue = None
            applicants = pat.get("applicants", []) or []
            if applicants:
                first_app = applicants[0]
                venue = first_app.get("extracted_name", {}).get("value") if isinstance(first_app.get("extracted_name"), dict) else None

            return self._make_paper(
                title=title,
                abstract=abstract,
                year=year,
                url=url,
                authors=authors,
                venue=venue,
                source_type=SourceType.PATENT,
                raw_metadata=pat,
            )
        except Exception:
            self.logger.exception("Failed to parse Lens patent: %s", pat.get("lens_id"))
            return None
