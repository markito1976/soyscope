"""Claude-based summary generation for SoyScope findings."""

from __future__ import annotations

import asyncio
import json
import logging

import anthropic

from ..models import Enrichment, EnrichmentTier

logger = logging.getLogger(__name__)


class Summarizer:
    """Generate AI summaries and deep analyses of soy-related findings."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20251001",
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else None
        self.model = model

    async def summarize(self, finding: dict) -> dict | None:
        """Produce a structured summary of a single finding.

        Parameters
        ----------
        finding:
            Dict containing *title*, *abstract*, *year*, *venue*, and
            *source_type* keys describing the item to summarise.

        Returns
        -------
        dict | None
            A dict with *summary*, *key_metrics*, *key_players*,
            *soy_advantage*, and *barriers* keys, or ``None`` on failure.
        """
        if self.client is None:
            logger.error("Anthropic client not initialised (no API key).")
            return None

        system_prompt = (
            "You are an expert analyst of industrial soybean applications. "
            "Generate a concise but comprehensive analysis."
        )

        user_prompt = (
            "Analyze the following research finding about industrial soybean "
            "applications and return a JSON object with exactly these keys:\n\n"
            "- summary: 2-3 sentence summary focused on the industrial soy application\n"
            "- key_metrics: a dict of any quantitative data (market size, growth rate, "
            "yield, efficiency, etc.)\n"
            "- key_players: a list of companies/institutions involved\n"
            "- soy_advantage: why soy is advantageous over alternatives (1-2 sentences)\n"
            "- barriers: commercialization barriers (1-2 sentences)\n\n"
            "Return ONLY valid JSON, no markdown fences or extra text.\n\n"
            f"Title: {finding.get('title', '')}\n"
            f"Abstract: {finding.get('abstract', '')}\n"
            f"Year: {finding.get('year', '')}\n"
            f"Venue: {finding.get('venue', '')}\n"
            f"Source type: {finding.get('source_type', '')}"
        )

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = response.content[0].text
            result = json.loads(raw_text)
            return result
        except json.JSONDecodeError:
            logger.exception("Failed to parse JSON from Claude response.")
            return None
        except Exception:
            logger.exception("Summarize call failed.")
            return None

    async def deep_analyze(
        self,
        finding: dict,
        model: str = "claude-sonnet-4-5-20250929",
    ) -> dict | None:
        """Perform a Tier-3 deep analysis using a more capable model.

        Parameters
        ----------
        finding:
            Dict containing *title*, *abstract*, *year*, *venue*, and
            *source_type* keys describing the item to analyse.
        model:
            The Claude model to use for deep analysis.

        Returns
        -------
        dict | None
            A dict with all summary fields plus *competitive_landscape*,
            *market_opportunity*, *ip_landscape*, and *recommendations*,
            or ``None`` on failure.
        """
        if self.client is None:
            logger.error("Anthropic client not initialised (no API key).")
            return None

        system_prompt = (
            "You are an expert analyst of industrial soybean applications. "
            "Generate a concise but comprehensive analysis."
        )

        user_prompt = (
            "Perform a deep analysis of the following research finding about "
            "industrial soybean applications and return a JSON object with "
            "exactly these keys:\n\n"
            "- summary: 2-3 sentence summary focused on the industrial soy application\n"
            "- key_metrics: a dict of any quantitative data (market size, growth rate, "
            "yield, efficiency, etc.)\n"
            "- key_players: a list of companies/institutions involved\n"
            "- soy_advantage: why soy is advantageous over alternatives (1-2 sentences)\n"
            "- barriers: commercialization barriers (1-2 sentences)\n"
            "- competitive_landscape: who else is doing this and how they compare\n"
            "- market_opportunity: estimated market size and growth potential\n"
            "- ip_landscape: patent activity and intellectual property considerations\n"
            "- recommendations: next steps for commercialization\n\n"
            "Return ONLY valid JSON, no markdown fences or extra text.\n\n"
            f"Title: {finding.get('title', '')}\n"
            f"Abstract: {finding.get('abstract', '')}\n"
            f"Year: {finding.get('year', '')}\n"
            f"Venue: {finding.get('venue', '')}\n"
            f"Source type: {finding.get('source_type', '')}"
        )

        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=model,
                max_tokens=2048,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = response.content[0].text
            result = json.loads(raw_text)
            return result
        except json.JSONDecodeError:
            logger.exception("Failed to parse JSON from Claude deep-analysis response.")
            return None
        except Exception:
            logger.exception("Deep analysis call failed.")
            return None
