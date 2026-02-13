"""Multi-column filter proxy model for the findings table.

Wraps FindingsTableModel and provides text search, source API filter,
OA status filter, source type filter, and year range filter.
All filter setters call invalidateFilter() to refresh the view.
Sorting uses ROLE_SORT_VALUE for typed comparisons.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from .findings_model import ROLE_SORT_VALUE, FindingRow


class FindingsFilterProxy(QSortFilterProxyModel):
    """Proxy that applies multiple simultaneous filters on FindingsTableModel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text_filter: str = ""
        self._source_filter: str = ""       # source_api value
        self._oa_filter: str = ""           # open_access_status value
        self._type_filter: str = ""         # source_type value
        self._year_range: tuple[int, int] = (0, 9999)
        self.setSortRole(ROLE_SORT_VALUE)

    # -- Filter setters (each invalidates) -----------------------------------

    def set_text_filter(self, text: str) -> None:
        """Free-text search across title, abstract, DOI, and venue."""
        self._text_filter = text.lower()
        self.invalidateFilter()

    def set_source_filter(self, source: str) -> None:
        """Filter by source_api (e.g. 'openalex', 'exa'). Empty = all."""
        self._source_filter = source.lower()
        self.invalidateFilter()

    def set_oa_filter(self, status: str) -> None:
        """Filter by open_access_status (e.g. 'gold', 'closed'). Empty = all."""
        self._oa_filter = status.lower()
        self.invalidateFilter()

    def set_type_filter(self, source_type: str) -> None:
        """Filter by source_type (e.g. 'paper', 'patent'). Empty = all."""
        self._type_filter = source_type.lower()
        self.invalidateFilter()

    def set_year_range(self, start: int, end: int) -> None:
        """Show only findings whose year falls within [start, end]."""
        self._year_range = (start, end)
        self.invalidateFilter()

    def clear_all_filters(self) -> None:
        """Reset every filter to its default (show all)."""
        self._text_filter = ""
        self._source_filter = ""
        self._oa_filter = ""
        self._type_filter = ""
        self._year_range = (0, 9999)
        self.invalidateFilter()

    # -- Core overrides ------------------------------------------------------

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        f: FindingRow | None = model.get_finding(source_row)
        if f is None:
            return False

        # Free-text filter (title, abstract, DOI, venue)
        if self._text_filter:
            haystack = " ".join(
                s.lower()
                for s in (f.title, f.abstract or "", f.doi or "", f.venue or "")
            )
            if self._text_filter not in haystack:
                return False

        # Source API filter
        if self._source_filter:
            if (f.source_api or "").lower() != self._source_filter:
                return False

        # Open access status filter
        if self._oa_filter:
            if (f.open_access_status or "").lower() != self._oa_filter:
                return False

        # Source type filter
        if self._type_filter:
            if (f.source_type or "").lower() != self._type_filter:
                return False

        # Year range filter
        if f.year is not None:
            if f.year < self._year_range[0] or f.year > self._year_range[1]:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_val = self.sourceModel().data(left, ROLE_SORT_VALUE)
        right_val = self.sourceModel().data(right, ROLE_SORT_VALUE)
        if left_val is None:
            return True
        if right_val is None:
            return False
        try:
            return left_val < right_val
        except TypeError:
            return str(left_val) < str(right_val)
