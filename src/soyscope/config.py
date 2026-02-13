"""Settings management for SoyScope."""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


@dataclass
class APIConfig:
    """Configuration for a single API source."""
    name: str
    api_key: str | None = None
    email: str | None = None
    base_url: str | None = None
    rate_limit_qps: float = 1.0
    enabled: bool = True


@dataclass
class Settings:
    """Global application settings."""

    # Paths
    project_root: Path = field(default_factory=lambda: _PROJECT_ROOT)
    db_path: Path = field(default_factory=lambda: _PROJECT_ROOT / os.getenv("SOYSCOPE_DB_PATH", "data/soyscope.db"))
    cache_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / os.getenv("SOYSCOPE_CACHE_DIR", "cache"))
    exports_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "exports")
    logs_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "logs")
    data_dir: Path = field(default_factory=lambda: _PROJECT_ROOT / "data")

    # Logging
    log_level: str = field(default_factory=lambda: os.getenv("SOYSCOPE_LOG_LEVEL", "INFO"))

    # Search settings
    search_year_start: int = 2000
    search_year_end: int = 2026
    time_windows: list[tuple[int, int]] = field(default_factory=lambda: [
        (2000, 2004), (2005, 2009), (2010, 2014), (2015, 2019), (2020, 2026)
    ])
    max_results_per_query: int = 100

    # Enrichment settings
    enrichment_batch_size: int = 20
    novelty_threshold: float = 0.7

    # API configurations
    apis: dict[str, APIConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Ensure directories exist
        for d in [self.cache_dir, self.exports_dir, self.logs_dir, self.data_dir]:
            d.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Build API configs
        self.apis = {
            "exa": APIConfig(
                name="exa",
                api_key=os.getenv("EXA_API_KEY"),
                rate_limit_qps=5.0,
                enabled=bool(os.getenv("EXA_API_KEY")),
            ),
            "openalex": APIConfig(
                name="openalex",
                email=os.getenv("OPENALEX_EMAIL"),
                base_url="https://api.openalex.org",
                rate_limit_qps=10.0,
                enabled=True,
            ),
            "semantic_scholar": APIConfig(
                name="semantic_scholar",
                api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
                rate_limit_qps=1.0,
                enabled=True,
            ),
            "crossref": APIConfig(
                name="crossref",
                email=os.getenv("CROSSREF_EMAIL"),
                rate_limit_qps=50.0,
                enabled=True,
            ),
            "pubmed": APIConfig(
                name="pubmed",
                api_key=os.getenv("PUBMED_API_KEY"),
                email=os.getenv("PUBMED_EMAIL"),
                rate_limit_qps=10.0,
                enabled=bool(os.getenv("PUBMED_EMAIL")),
            ),
            "tavily": APIConfig(
                name="tavily",
                api_key=os.getenv("TAVILY_API_KEY"),
                rate_limit_qps=5.0,
                enabled=bool(os.getenv("TAVILY_API_KEY")),
            ),
            "core": APIConfig(
                name="core",
                api_key=os.getenv("CORE_API_KEY"),  # Optional: higher rate limits with key
                base_url="https://api.core.ac.uk/v3",
                rate_limit_qps=0.5,  # 5 req/10 sec without key
                enabled=True,  # Works without API key
            ),
            "unpaywall": APIConfig(
                name="unpaywall",
                email=os.getenv("UNPAYWALL_EMAIL"),
                base_url="https://api.unpaywall.org/v2",
                rate_limit_qps=10.0,
                enabled=bool(os.getenv("UNPAYWALL_EMAIL")),
            ),
            "claude": APIConfig(
                name="claude",
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                rate_limit_qps=5.0,
                enabled=bool(os.getenv("ANTHROPIC_API_KEY")),
            ),
            # --- Tier 1 sources (free, no/light auth) ---
            "osti": APIConfig(
                name="osti",
                base_url="https://www.osti.gov/api/v1/records",
                rate_limit_qps=1.0,
                enabled=True,  # Free, no auth
            ),
            "patentsview": APIConfig(
                name="patentsview",
                api_key=os.getenv("PATENTSVIEW_API_KEY"),
                base_url="https://search.patentsview.org/api/v1/patent/",
                rate_limit_qps=0.75,  # 45/min
                enabled=True,  # Works without key too
            ),
            "sbir": APIConfig(
                name="sbir",
                base_url="https://api.www.sbir.gov/public/api/awards",
                rate_limit_qps=1.0,
                enabled=True,  # Free, no auth
            ),
            "agris": APIConfig(
                name="agris",
                base_url="https://agris.fao.org/search",
                rate_limit_qps=1.0,
                enabled=True,  # Free, no auth
            ),
            "lens": APIConfig(
                name="lens",
                api_key=os.getenv("LENS_API_KEY"),
                base_url="https://api.lens.org",
                rate_limit_qps=0.83,  # 50/min
                enabled=bool(os.getenv("LENS_API_KEY")),
            ),
            "usda_ers": APIConfig(
                name="usda_ers",
                api_key=os.getenv("USDA_ERS_API_KEY"),
                base_url="https://api.nal.usda.gov/pubag/rest/search",
                rate_limit_qps=1.0,
                enabled=True,  # Works without key
            ),
        }


def get_settings() -> Settings:
    """Get the global settings instance."""
    return Settings()
