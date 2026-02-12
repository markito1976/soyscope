"""Claude-based sector / derivative / TRL tagging for SoyScope findings."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import anthropic

from ..config import get_settings
from ..models import EnrichmentResult, Finding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are a research analyst specializing in industrial applications of "
    "soybeans. Classify each finding into relevant sectors and soy derivatives. "
    "Also estimate the Technology Readiness Level (TRL, 1-9) and "
    "commercialization status."
)

USER_PROMPT_TEMPLATE = """\
Below is a JSON array of research findings about industrial uses of soybeans.
For **each** finding, return a JSON object with the following fields:

- finding_id       (int)   -- the id of the finding
- sectors          (list[str]) -- matching sector names from the KNOWN SECTORS list
- derivatives      (list[str]) -- matching derivative names from the KNOWN DERIVATIVES list
- trl_estimate     (int, 1-9) -- Technology Readiness Level estimate
- commercialization_status (str) -- one of: research, pilot, scaling, commercial, mature
- novelty_score    (float, 0.0-1.0) -- how novel this application is
- summary          (str) -- 2-3 sentence summary of the finding
- new_sectors      (list[str]) -- any sectors you identify that are NOT in the known list
- new_derivatives  (list[str]) -- any derivatives you identify that are NOT in the known list
- tags             (list[str]) -- free-form tags (e.g. "PFAS-replacement", "bio-based", "carbon-negative")

Return ONLY a JSON array of these objects -- no markdown fences, no commentary.

### KNOWN SECTORS
{sectors_json}

### KNOWN DERIVATIVES
{derivatives_json}

### FINDINGS
{findings_json}
"""


class Classifier:
    """Wraps the Anthropic SDK to classify findings via Claude."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.model = model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_user_prompt(
        self,
        findings: list[dict[str, Any]],
        sectors: list[str],
        derivatives: list[str],
    ) -> str:
        return USER_PROMPT_TEMPLATE.format(
            sectors_json=json.dumps(sectors, indent=2),
            derivatives_json=json.dumps(derivatives, indent=2),
            findings_json=json.dumps(findings, indent=2),
        )

    def _call_api(self, user_prompt: str) -> str:
        """Synchronous Claude API call (meant to be run via *asyncio.to_thread*)."""
        if self.client is None:
            raise RuntimeError(
                "Anthropic client is not initialised -- provide an API key."
            )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # Extract text from the first content block
        return response.content[0].text

    @staticmethod
    def _parse_results(raw_json: str) -> list[EnrichmentResult]:
        """Parse the raw JSON string returned by Claude into EnrichmentResult objects."""
        # Strip possible markdown fences just in case
        text = raw_json.strip()
        if text.startswith("```"):
            # Remove opening fence (with optional language tag) and closing fence
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

        data: list[dict[str, Any]] = json.loads(text)
        results: list[EnrichmentResult] = []
        for item in data:
            try:
                result = EnrichmentResult(
                    finding_id=item["finding_id"],
                    sectors=item.get("sectors", []),
                    derivatives=item.get("derivatives", []),
                    trl_estimate=item.get("trl_estimate"),
                    commercialization_status=item.get("commercialization_status"),
                    novelty_score=item.get("novelty_score"),
                    summary=item.get("summary"),
                    new_sectors=item.get("new_sectors", []),
                    new_derivatives=item.get("new_derivatives", []),
                    tags=item.get("tags", []),
                )
                results.append(result)
            except Exception:
                logger.exception(
                    "Failed to parse enrichment result for item: %s", item
                )
        return results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def classify_batch(
        self,
        findings: list[dict],
        sectors: list[str],
        derivatives: list[str],
    ) -> list[EnrichmentResult]:
        """Classify a batch of findings (up to 20 at a time) via Claude.

        Parameters
        ----------
        findings:
            List of dicts, each with at least ``id``, ``title``, and ``abstract``.
        sectors:
            Known sector names for matching.
        derivatives:
            Known derivative names for matching.

        Returns
        -------
        list[EnrichmentResult]
            One result per successfully-parsed finding.
        """
        all_results: list[EnrichmentResult] = []
        # Process in chunks of 20
        for i in range(0, len(findings), 20):
            chunk = findings[i : i + 20]
            user_prompt = self._build_user_prompt(chunk, sectors, derivatives)
            try:
                raw_text = await asyncio.to_thread(self._call_api, user_prompt)
                results = self._parse_results(raw_text)
                all_results.extend(results)
            except json.JSONDecodeError:
                logger.exception(
                    "JSON parsing error for batch chunk starting at index %d", i
                )
            except Exception:
                logger.exception(
                    "API call failed for batch chunk starting at index %d", i
                )
        return all_results

    async def classify_single(
        self,
        finding: dict,
        sectors: list[str],
        derivatives: list[str],
    ) -> EnrichmentResult | None:
        """Classify a single finding.

        Returns ``None`` on any failure.
        """
        try:
            results = await self.classify_batch([finding], sectors, derivatives)
            return results[0] if results else None
        except Exception:
            logger.exception(
                "classify_single failed for finding %s",
                finding.get("id", "unknown"),
            )
            return None
