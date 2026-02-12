"""Tests for OpenAlex source adapter (mocked)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from soyscope.sources.openalex_source import OpenAlexSource


class TestOpenAlexSource:
    def test_name(self):
        source = OpenAlexSource(email="test@example.com")
        assert source.name == "openalex"

    @pytest.mark.asyncio
    async def test_search_empty(self):
        source = OpenAlexSource(email="test@example.com")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "meta": {"count": 0}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("nonexistent query")
            assert result.papers == [] or len(result.papers) == 0

    @pytest.mark.asyncio
    async def test_search_with_results(self):
        source = OpenAlexSource(email="test@example.com")

        mock_work = {
            "id": "https://openalex.org/W12345",
            "doi": "https://doi.org/10.1234/test",
            "display_name": "Soy adhesive for plywood",
            "title": "Soy adhesive for plywood",
            "publication_year": 2022,
            "cited_by_count": 10,
            "type": "journal-article",
            "open_access": {"oa_status": "gold", "is_oa": True},
            "authorships": [
                {"author": {"display_name": "John Smith"}},
            ],
            "primary_location": {
                "source": {"display_name": "Journal of Wood Science"}
            },
            "abstract_inverted_index": {
                "Soy": [0],
                "adhesive": [1],
                "for": [2],
                "plywood": [3],
            },
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [mock_work],
            "meta": {"count": 1},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy adhesive")
            assert len(result.papers) == 1
            assert "soy" in result.papers[0].title.lower() or "adhesive" in result.papers[0].title.lower()
