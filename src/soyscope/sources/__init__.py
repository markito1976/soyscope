"""API source adapters for SoyScope.

Each adapter implements the SearchSource protocol from base.py.
Import individual sources as needed - they have different dependencies.
"""

from .base import BaseSource, SearchResult, SearchSource

__all__ = ["BaseSource", "SearchResult", "SearchSource"]
