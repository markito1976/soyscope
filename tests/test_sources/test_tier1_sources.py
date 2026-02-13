"""Tests for Tier 1 source adapters (OSTI, PatentsView, SBIR, AGRIS, Lens, USDA ERS).

All tests use mocked HTTP responses — no real API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── OSTI ──────────────────────────────────────────────────────────────

class TestOSTISource:
    def test_name(self):
        from soyscope.sources.osti_source import OSTISource
        source = OSTISource()
        assert source.name == "osti"

    @pytest.mark.asyncio
    async def test_search_returns_papers(self):
        from soyscope.sources.osti_source import OSTISource
        source = OSTISource()

        mock_records = [
            {
                "osti_id": "12345",
                "title": "Soy-Based Biofuel Production from DOE Pilot",
                "description": "A study on soy-based biofuel production.",
                "authors": "Smith, J; Jones, K",
                "publication_date": "2022-06-15",
                "doi": "10.2172/12345",
                "link": "https://www.osti.gov/biblio/12345",
                "journal_name": "DOE Technical Reports",
                "product_type": "Technical Report",
                "access_type": "Open",
            }
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_records
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy biofuel")
            assert len(result.papers) == 1
            assert "biofuel" in result.papers[0].title.lower()
            assert result.papers[0].source_api == "osti"
            assert result.papers[0].year == 2022
            assert len(result.papers[0].authors) == 2

    @pytest.mark.asyncio
    async def test_search_empty(self):
        from soyscope.sources.osti_source import OSTISource
        source = OSTISource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("nonexistent")
            assert len(result.papers) == 0


# ── PatentsView ───────────────────────────────────────────────────────

class TestPatentsViewSource:
    def test_name(self):
        from soyscope.sources.patentsview_source import PatentsViewSource
        source = PatentsViewSource()
        assert source.name == "patentsview"

    @pytest.mark.asyncio
    async def test_search_returns_patents(self):
        from soyscope.sources.patentsview_source import PatentsViewSource
        source = PatentsViewSource(api_key="test-key")

        mock_data = {
            "patents": [
                {
                    "patent_number": "US12345678",
                    "patent_title": "Soy-Based Polyurethane Foam Composition",
                    "patent_abstract": "A novel soy-based polyurethane foam.",
                    "patent_date": "2023-03-15",
                    "patent_type": "utility",
                    "inventors": [
                        {"inventor_first_name": "John", "inventor_last_name": "Doe"},
                        {"inventor_first_name": "Jane", "inventor_last_name": "Roe"},
                    ],
                    "assignees": [
                        {"assignee_organization": "SoyTech Inc."}
                    ],
                }
            ],
            "total_patent_count": 1,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy polyurethane")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_api == "patentsview"
            assert p.source_type.value == "patent"
            assert p.year == 2023
            assert len(p.authors) == 2


# ── SBIR ──────────────────────────────────────────────────────────────

class TestSBIRSource:
    def test_name(self):
        from soyscope.sources.sbir_source import SBIRSource
        source = SBIRSource()
        assert source.name == "sbir"

    @pytest.mark.asyncio
    async def test_search_returns_awards(self):
        from soyscope.sources.sbir_source import SBIRSource
        source = SBIRSource()

        mock_data = {
            "totalCount": 1,
            "results": [
                {
                    "award_title": "Novel Soy Adhesive for Wood Products",
                    "abstract": "Development of soy-based adhesive for wood composites.",
                    "award_year": 2021,
                    "pi_name": "Dr. Alice Chen",
                    "firm": "BioGlue LLC",
                    "agency": "USDA",
                    "award_link": "https://www.sbir.gov/award/12345",
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy adhesive")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_api == "sbir"
            assert "adhesive" in p.title.lower()
            assert p.year == 2021
            assert p.source_type.value == "govt_report"


# ── AGRIS ─────────────────────────────────────────────────────────────

class TestAGRISSource:
    def test_name(self):
        from soyscope.sources.agris_source import AGRISSource
        source = AGRISSource()
        assert source.name == "agris"

    @pytest.mark.asyncio
    async def test_search_returns_papers(self):
        from soyscope.sources.agris_source import AGRISSource
        source = AGRISSource()

        mock_data = {
            "totalCount": 1,
            "results": [
                {
                    "title": "Industrial Uses of Soybean in Brazil",
                    "abstract": "Overview of industrial soy applications in Brazil.",
                    "authors": ["Silva, M.A.", "Santos, J.B."],
                    "date": "2020",
                    "url": "https://agris.fao.org/record/BR202012345",
                    "source": "Brazilian Journal of Agriculture",
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soybean industrial")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_api == "agris"
            assert p.year == 2020
            assert len(p.authors) == 2


# ── Lens.org ──────────────────────────────────────────────────────────

class TestLensSource:
    def test_name(self):
        from soyscope.sources.lens_source import LensSource
        source = LensSource(api_key="test-token")
        assert source.name == "lens"

    @pytest.mark.asyncio
    async def test_scholarly_search(self):
        from soyscope.sources.lens_source import LensSource
        source = LensSource(api_key="test-token")

        mock_data = {
            "total": 1,
            "data": [
                {
                    "lens_id": "001-234-567-890",
                    "title": "Soy Protein-Based Biodegradable Polymers",
                    "abstract": "Review of soy protein polymer applications.",
                    "year_published": 2023,
                    "doi": "10.1234/lens.test",
                    "authors": [
                        {"first_name": "Emily", "last_name": "Park"},
                    ],
                    "source": {"title": "Green Chemistry"},
                    "scholarly_citations_count": 15,
                    "open_access": {"is_oa": True, "colour": "gold"},
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy polymer")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_api == "lens"
            assert p.year == 2023
            assert p.doi == "10.1234/lens.test"
            assert p.citation_count == 15

    @pytest.mark.asyncio
    async def test_patent_search(self):
        from soyscope.sources.lens_source import LensSource
        source = LensSource(api_key="test-token")

        mock_data = {
            "total": 1,
            "data": [
                {
                    "lens_id": "patent-001-234",
                    "title": "Soy-Based Lubricant Composition",
                    "abstract": "A lubricant comprising soy oil derivatives.",
                    "date_published": "2022-09-10",
                    "inventors": [
                        {"extracted_name": {"first_name": "Bob", "last_name": "Miller"}},
                    ],
                    "applicants": [
                        {"extracted_name": {"value": "GreenLube Corp."}}
                    ],
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soy lubricant", search_type="patent")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_type.value == "patent"
            assert p.year == 2022


# ── USDA ERS ──────────────────────────────────────────────────────────

class TestUSDAERSSource:
    def test_name(self):
        from soyscope.sources.usda_ers_source import USDAERSSource
        source = USDAERSSource()
        assert source.name == "usda_ers"

    @pytest.mark.asyncio
    async def test_search_returns_papers(self):
        from soyscope.sources.usda_ers_source import USDAERSSource
        source = USDAERSSource(api_key="test-key")

        mock_data = {
            "numFound": 1,
            "result": [
                {
                    "title": "Economic Impact of Soybean Oil in Industrial Markets",
                    "abstract": "Analysis of soybean oil's role in industrial applications.",
                    "authors": [{"name": "USDA ERS Staff"}],
                    "publicationYear": 2024,
                    "doi": "10.32747/ers.2024.001",
                    "url": "https://www.ers.usda.gov/publications/12345",
                    "journal": "USDA ERS Reports",
                    "documentType": "Report",
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("soybean oil industrial")
            assert len(result.papers) == 1
            p = result.papers[0]
            assert p.source_api == "usda_ers"
            assert p.year == 2024
            assert p.source_type.value == "govt_report"
            assert p.doi == "10.32747/ers.2024.001"

    @pytest.mark.asyncio
    async def test_search_empty(self):
        from soyscope.sources.usda_ers_source import USDAERSSource
        source = USDAERSSource()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"numFound": 0, "result": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await source.search("nonexistent")
            assert len(result.papers) == 0


# ── Integration: all sources importable ───────────────────────────────

class TestAllSourcesImportable:
    def test_import_osti(self):
        from soyscope.sources.osti_source import OSTISource
        assert OSTISource is not None

    def test_import_patentsview(self):
        from soyscope.sources.patentsview_source import PatentsViewSource
        assert PatentsViewSource is not None

    def test_import_sbir(self):
        from soyscope.sources.sbir_source import SBIRSource
        assert SBIRSource is not None

    def test_import_agris(self):
        from soyscope.sources.agris_source import AGRISSource
        assert AGRISSource is not None

    def test_import_lens(self):
        from soyscope.sources.lens_source import LensSource
        assert LensSource is not None

    def test_import_usda_ers(self):
        from soyscope.sources.usda_ers_source import USDAERSSource
        assert USDAERSSource is not None
