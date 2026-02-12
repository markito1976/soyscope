"""Pydantic models and dataclasses for SoyScope."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    PAPER = "paper"
    PATENT = "patent"
    NEWS = "news"
    REPORT = "report"
    TRADE_PUB = "trade_pub"
    CONFERENCE = "conference"
    GOVT_REPORT = "govt_report"


class OAStatus(str, Enum):
    GOLD = "gold"
    GREEN = "green"
    HYBRID = "hybrid"
    BRONZE = "bronze"
    CLOSED = "closed"


class CommercializationStatus(str, Enum):
    RESEARCH = "research"
    PILOT = "pilot"
    SCALING = "scaling"
    COMMERCIAL = "commercial"
    MATURE = "mature"


class EnrichmentTier(str, Enum):
    CATALOG = "catalog"
    SUMMARY = "summary"
    DEEP = "deep"


class Paper(BaseModel):
    """Unified paper/finding model from any API source."""
    title: str
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    source_api: str = ""
    source_type: SourceType = SourceType.PAPER
    citation_count: int | None = None
    open_access_status: OAStatus | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def authors_json(self) -> str:
        return json.dumps(self.authors)

    @property
    def raw_metadata_json(self) -> str:
        return json.dumps(self.raw_metadata)


class Finding(BaseModel):
    """A finding stored in the database."""
    id: int | None = None
    title: str
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    source_api: str = ""
    source_type: str = "paper"
    citation_count: int | None = None
    open_access_status: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Sector(BaseModel):
    """Industry sector."""
    id: int | None = None
    name: str
    parent_id: int | None = None
    description: str | None = None
    is_ai_discovered: bool = False


class Derivative(BaseModel):
    """Soy derivative."""
    id: int | None = None
    name: str
    parent_id: int | None = None
    description: str | None = None
    is_ai_discovered: bool = False


class Enrichment(BaseModel):
    """AI enrichment result."""
    id: int | None = None
    finding_id: int
    tier: EnrichmentTier = EnrichmentTier.CATALOG
    trl_estimate: int | None = None
    commercialization_status: CommercializationStatus | None = None
    novelty_score: float | None = None
    ai_summary: str | None = None
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    key_players: list[str] = Field(default_factory=list)
    soy_advantage: str | None = None
    barriers: str | None = None
    enriched_at: datetime | None = None
    model_used: str | None = None


class SearchRun(BaseModel):
    """Track a search run."""
    id: int | None = None
    run_type: str = "manual"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    queries_executed: int = 0
    findings_added: int = 0
    findings_updated: int = 0
    api_costs_json: dict[str, float] = Field(default_factory=dict)
    status: str = "running"


class SearchQuery(BaseModel):
    """Track a query within a run."""
    id: int | None = None
    run_id: int | None = None
    query_text: str = ""
    api_source: str = ""
    results_returned: int = 0
    new_findings: int = 0
    executed_at: datetime | None = None


class CheckoffProject(BaseModel):
    """Soybean Checkoff Research DB project."""
    id: int | None = None
    year: str | None = None
    title: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    lead_pi: str | None = None
    institution: str | None = None
    funding: float | None = None
    summary: str | None = None
    objectives: str | None = None
    url: str | None = None
    imported_at: datetime | None = None


class EnrichmentRequest(BaseModel):
    """Request to enrich a batch of findings."""
    findings: list[Finding]
    tier: EnrichmentTier = EnrichmentTier.SUMMARY


class EnrichmentResult(BaseModel):
    """Result from AI enrichment of a single finding."""
    finding_id: int
    sectors: list[str] = Field(default_factory=list)
    derivatives: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    trl_estimate: int | None = None
    commercialization_status: str | None = None
    novelty_score: float | None = None
    summary: str | None = None
    new_sectors: list[str] = Field(default_factory=list)
    new_derivatives: list[str] = Field(default_factory=list)
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    key_players: list[str] = Field(default_factory=list)
    soy_advantage: str | None = None
    barriers: str | None = None
