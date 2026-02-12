"""SearchSource protocol and base adapter interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..models import Paper

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result from a search operation."""
    papers: list[Paper] = field(default_factory=list)
    total_results: int = 0
    query: str = ""
    api_source: str = ""
    raw_response: Any = None


@runtime_checkable
class SearchSource(Protocol):
    """Protocol for search source adapters."""

    @property
    def name(self) -> str:
        """API source name."""
        ...

    async def search(self, query: str, max_results: int = 100,
                     year_start: int | None = None,
                     year_end: int | None = None,
                     **kwargs: Any) -> SearchResult:
        """Search for papers/findings."""
        ...

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Retrieve a specific paper by DOI (if supported)."""
        ...


class BaseSource(ABC):
    """Base class for search source adapters with common functionality."""

    def __init__(self, api_key: str | None = None, email: str | None = None) -> None:
        self.api_key = api_key
        self.email = email
        self.logger = logging.getLogger(f"soyscope.sources.{self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def search(self, query: str, max_results: int = 100,
                     year_start: int | None = None,
                     year_end: int | None = None,
                     **kwargs: Any) -> SearchResult:
        ...

    async def get_by_doi(self, doi: str) -> Paper | None:
        """Default: not supported."""
        return None

    def _make_paper(self, **kwargs: Any) -> Paper:
        """Helper to create a Paper with source_api set."""
        return Paper(source_api=self.name, **kwargs)
