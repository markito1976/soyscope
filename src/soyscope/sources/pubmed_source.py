"""PubMed/Entrez API adapter for SoyScope."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from Bio import Entrez

from ..models import Paper, SourceType
from .base import BaseSource, SearchResult

logger = logging.getLogger(__name__)


class PubMedSource(BaseSource):
    """Adapter for the PubMed/NCBI Entrez API.

    Uses Biopython's ``Bio.Entrez`` module which is synchronous, so every call
    is wrapped with ``asyncio.to_thread`` to avoid blocking the event loop.
    """

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
    ) -> None:
        super().__init__(api_key=api_key, email=email)
        if email:
            Entrez.email = email
        if api_key:
            Entrez.api_key = api_key

    # ------------------------------------------------------------------
    # BaseSource interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "pubmed"

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
        **kwargs: Any,
    ) -> SearchResult:
        """Search PubMed for articles matching *query*.

        Parameters
        ----------
        query:
            The search query string (PubMed search syntax is supported).
        max_results:
            Maximum number of results to return (capped at 10 000).
        year_start:
            Filter results published on or after this year.
        year_end:
            Filter results published on or before this year.

        Returns
        -------
        SearchResult with papers converted from PubMed XML records.
        """
        try:
            return await asyncio.to_thread(
                self._search_sync, query, max_results, year_start, year_end
            )
        except Exception:
            self.logger.exception("PubMed search failed for query: %s", query)
            return SearchResult(
                papers=[], total_results=0, query=query, api_source=self.name
            )

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Look up a single paper on PubMed by its DOI."""
        try:
            result = await self.search(query=f"{doi}[DOI]", max_results=1)
            if result.papers:
                return result.papers[0]
        except Exception:
            self.logger.exception("PubMed DOI lookup failed for: %s", doi)
        return None

    # ------------------------------------------------------------------
    # Synchronous helpers (run inside asyncio.to_thread)
    # ------------------------------------------------------------------

    def _search_sync(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> SearchResult:
        """Execute PubMed esearch + efetch synchronously."""

        # Step 1 -- esearch to get PMIDs -----------------------------------
        esearch_kwargs: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": min(max_results, 10_000),
        }
        if year_start is not None:
            esearch_kwargs["mindate"] = f"{year_start}/01/01"
        if year_end is not None:
            esearch_kwargs["maxdate"] = f"{year_end}/12/31"
        if year_start is not None or year_end is not None:
            esearch_kwargs["datetype"] = "pdat"

        handle = Entrez.esearch(**esearch_kwargs)
        search_results = Entrez.read(handle)
        handle.close()

        id_list: list[str] = search_results.get("IdList", [])
        total_results = int(search_results.get("Count", 0))

        if not id_list:
            return SearchResult(
                papers=[],
                total_results=total_results,
                query=query,
                api_source=self.name,
            )

        # Step 2 -- efetch full records ------------------------------------
        handle = Entrez.efetch(
            db="pubmed", id=id_list, rettype="xml", retmode="xml"
        )
        fetch_results = Entrez.read(handle)
        handle.close()

        papers: list[Paper] = []
        for article in fetch_results.get("PubmedArticle", []):
            try:
                paper = self._parse_article(article)
                papers.append(paper)
            except Exception:
                self.logger.debug(
                    "Failed to parse a PubMed article record", exc_info=True
                )

        return SearchResult(
            papers=papers,
            total_results=total_results,
            query=query,
            api_source=self.name,
        )

    # ------------------------------------------------------------------
    # Article parsing
    # ------------------------------------------------------------------

    def _parse_article(self, article: dict[str, Any]) -> Paper:
        """Convert a single PubmedArticle dict into a :class:`Paper`."""

        medline = article.get("MedlineCitation", {})
        article_data = medline.get("Article", {})
        pubmed_data = article.get("PubmedData", {})

        # Title --------------------------------------------------------
        title = str(article_data.get("ArticleTitle", ""))

        # Abstract -----------------------------------------------------
        abstract: str | None = None
        abstract_block = article_data.get("Abstract", {})
        abstract_texts = abstract_block.get("AbstractText", [])
        if abstract_texts:
            abstract = " ".join(str(part) for part in abstract_texts)

        # Year ---------------------------------------------------------
        year: int | None = None
        try:
            pub_date = (
                article_data.get("Journal", {})
                .get("JournalIssue", {})
                .get("PubDate", {})
            )
            year = int(pub_date["Year"])
        except (KeyError, TypeError, ValueError):
            # Fall back to MedlineDate or ArticleDate if Year is absent
            pass

        # PMID ---------------------------------------------------------
        pmid = str(medline.get("PMID", ""))

        # DOI ----------------------------------------------------------
        doi = self._extract_doi(article_data, pubmed_data)

        # URL ----------------------------------------------------------
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None

        # Authors ------------------------------------------------------
        authors = self._extract_authors(article_data)

        # Venue --------------------------------------------------------
        venue: str | None = None
        journal = article_data.get("Journal", {})
        if journal:
            venue = str(journal.get("Title", "")) or None

        return Paper(
            title=title,
            abstract=abstract,
            year=year,
            doi=doi,
            url=url,
            authors=authors,
            venue=venue,
            source_api="pubmed",
            source_type=SourceType.PAPER,
            raw_metadata={"pmid": pmid},
        )

    # ------------------------------------------------------------------
    # Field-level extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_doi(
        article_data: dict[str, Any],
        pubmed_data: dict[str, Any],
    ) -> str | None:
        """Try several locations for a DOI string."""

        # 1) ELocationID list on the article
        for eloc in article_data.get("ELocationID", []):
            attrs = getattr(eloc, "attributes", {})
            if attrs.get("EIdType") == "doi":
                return str(eloc)

        # 2) ArticleIdList in PubmedData
        for aid in pubmed_data.get("ArticleIdList", []):
            attrs = getattr(aid, "attributes", {})
            if attrs.get("IdType") == "doi":
                return str(aid)

        return None

    @staticmethod
    def _extract_authors(article_data: dict[str, Any]) -> list[str]:
        """Build a list of author name strings."""

        authors: list[str] = []
        author_list = article_data.get("AuthorList", [])
        for author in author_list:
            last = author.get("LastName", "")
            initials = author.get("Initials", "")
            forename = author.get("ForeName", "")

            if last and initials:
                authors.append(f"{last} {initials}")
            elif last and forename:
                authors.append(f"{forename} {last}")
            elif last:
                authors.append(str(last))
            else:
                # CollectiveName or other edge-case
                collective = author.get("CollectiveName", "")
                if collective:
                    authors.append(str(collective))

        return authors
