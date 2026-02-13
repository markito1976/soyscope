"""Qt table model for SoyScope findings data.

Provides FindingRow dataclass, column enum, custom roles, color maps,
and FindingsTableModel (QAbstractTableModel) for use with QTableView.
Adapted to the actual SoyScope DB schema (findings + enrichments tables).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor


# ---------------------------------------------------------------------------
# Data row
# ---------------------------------------------------------------------------

@dataclass
class FindingRow:
    """Flat row combining findings + enrichments for table display."""

    id: int
    title: str
    year: int | None
    doi: str
    url: str
    pdf_url: str
    authors: str          # JSON string from DB
    venue: str
    source_api: str
    source_type: str
    citation_count: int | None
    open_access_status: str
    trl: int = 0          # from enrichments.trl_estimate
    novelty_score: float = 0.0  # from enrichments.novelty_score
    abstract: str = ""
    sources: str = ""     # comma-separated source_api values from finding_sources


# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------

class Col(IntEnum):
    """Column indices -- single source of truth for table layout."""

    ID = 0
    TITLE = 1
    YEAR = 2
    DOI = 3
    VENUE = 4
    SOURCE_API = 5
    SOURCE_TYPE = 6
    CITATION_COUNT = 7
    OA_STATUS = 8
    TRL = 9
    NOVELTY = 10
    SOURCES = 11


# ---------------------------------------------------------------------------
# Custom data roles (beyond Qt built-ins)
# ---------------------------------------------------------------------------

ROLE_FINDING = Qt.ItemDataRole.UserRole + 1        # Full FindingRow object
ROLE_SORT_VALUE = Qt.ItemDataRole.UserRole + 2     # Raw typed sortable value
ROLE_LINK_URL = Qt.ItemDataRole.UserRole + 3       # URL string for hyperlink delegate
ROLE_BADGE_COLOR = Qt.ItemDataRole.UserRole + 4    # QColor for badge background
ROLE_PROGRESS_VALUE = Qt.ItemDataRole.UserRole + 5 # float 0.0-1.0 for progress bar


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

HEADERS: list[str] = [
    "ID", "Title", "Year", "DOI", "Venue",
    "Source", "Type", "Citations", "OA", "TRL", "Novelty", "Sources",
]


# ---------------------------------------------------------------------------
# Color maps
# ---------------------------------------------------------------------------

TRL_COLORS: dict[range, QColor] = {
    range(1, 4): QColor("#e74c3c"),   # red: basic research (TRL 1-3)
    range(4, 7): QColor("#f39c12"),   # amber: development (TRL 4-6)
    range(7, 10): QColor("#27ae60"),  # green: deployment ready (TRL 7-9)
}

OA_COLORS: dict[str, QColor] = {
    "gold": QColor("#f1c40f"),
    "green": QColor("#2ecc71"),
    "hybrid": QColor("#8e44ad"),
    "bronze": QColor("#e67e22"),
    "closed": QColor("#95a5a6"),
}


# ---------------------------------------------------------------------------
# Table model
# ---------------------------------------------------------------------------

class FindingsTableModel(QAbstractTableModel):
    """High-performance table model for SoyScope findings.

    Designed for virtual scrolling with QTableView -- only visible cells
    are rendered.  Supports custom roles for delegates (badges, links,
    progress bars) and typed sort values via ROLE_SORT_VALUE.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[FindingRow] = []

    # -- Required overrides --------------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        f = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(f, col)

        if role == ROLE_FINDING:
            return f

        if role == ROLE_SORT_VALUE:
            return self._sort_value(f, col)

        if role == ROLE_LINK_URL and col == Col.DOI:
            if f.doi:
                return (
                    f"https://doi.org/{f.doi}"
                    if not f.doi.startswith("http")
                    else f.doi
                )
            return None

        if role == ROLE_BADGE_COLOR:
            if col == Col.TRL:
                for rng, color in TRL_COLORS.items():
                    if f.trl in rng:
                        return color
                return None
            if col == Col.OA_STATUS:
                return OA_COLORS.get(f.open_access_status.lower() if f.open_access_status else "")
            return None

        if role == ROLE_PROGRESS_VALUE:
            if col == Col.NOVELTY:
                return f.novelty_score  # 0.0 - 1.0
            return None

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == Col.TITLE:
                text = f.abstract or ""
                if len(text) > 200:
                    return text[:200] + "..."
                return text if text else None
            if col == Col.DOI and f.doi:
                return f"Click to open: {f.doi}"
            if col == Col.TRL and f.trl:
                return f"Technology Readiness Level {f.trl}"
            if col == Col.NOVELTY:
                return f"Novelty score: {f.novelty_score:.2f}"
            return None

        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    # -- Display / sort helpers ----------------------------------------------

    def _display_value(self, f: FindingRow, col: int) -> str:
        match col:
            case Col.ID:
                return str(f.id)
            case Col.TITLE:
                return f.title
            case Col.YEAR:
                return str(f.year) if f.year else ""
            case Col.DOI:
                return f.doi if f.doi else ""
            case Col.VENUE:
                return f.venue if f.venue else ""
            case Col.SOURCE_API:
                return f.source_api if f.source_api else ""
            case Col.SOURCE_TYPE:
                return f.source_type if f.source_type else ""
            case Col.CITATION_COUNT:
                return str(f.citation_count) if f.citation_count is not None else ""
            case Col.OA_STATUS:
                return f.open_access_status.upper() if f.open_access_status else ""
            case Col.TRL:
                return f"TRL {f.trl}" if f.trl else ""
            case Col.NOVELTY:
                return f"{f.novelty_score:.0%}" if f.novelty_score else "0%"
            case Col.SOURCES:
                return f.sources if f.sources else f.source_api
        return ""

    def _sort_value(self, f: FindingRow, col: int) -> Any:
        match col:
            case Col.ID:
                return f.id
            case Col.YEAR:
                return f.year or 0
            case Col.CITATION_COUNT:
                return f.citation_count or 0
            case Col.TRL:
                return f.trl
            case Col.NOVELTY:
                return f.novelty_score
            case Col.SOURCES:
                return (f.sources or f.source_api or "").lower()
            case _:
                return self._display_value(f, col).lower()

    # -- Data manipulation ---------------------------------------------------

    def load_data(self, findings: list[FindingRow]) -> None:
        """Replace all data (full reset)."""
        self.beginResetModel()
        self._data = findings
        self.endResetModel()

    def append_data(self, findings: list[FindingRow]) -> None:
        """Append rows without resetting the model."""
        if not findings:
            return
        start = len(self._data)
        self.beginInsertRows(QModelIndex(), start, start + len(findings) - 1)
        self._data.extend(findings)
        self.endInsertRows()

    def get_finding(self, row: int) -> FindingRow | None:
        """Return the FindingRow at *row*, or None if out of range."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def get_all_data(self) -> list[FindingRow]:
        """Return the full backing list (not a copy)."""
        return self._data
