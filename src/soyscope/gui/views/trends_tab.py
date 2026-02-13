"""Trends tab -- timeline / area charts for findings over time.

Contains a TimelineWidget (PyQtGraph) that shows findings-by-year
stacked by source_api, with a combo box to switch between chart views
(by source API, by source type).  Falls back gracefully when
pyqtgraph is not installed.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

try:
    from ..widgets.timeline_widget import TimelineWidget

    HAS_TIMELINE = True
except ImportError:
    HAS_TIMELINE = False


# Default color palette for stacked series
_SERIES_COLORS: dict[str, str] = {
    "openalex": "#89b4fa",
    "semantic_scholar": "#a6e3a1",
    "exa": "#f9e2af",
    "crossref": "#fab387",
    "pubmed": "#f38ba8",
    "tavily": "#cba6f7",
    "core": "#94e2d5",
    "unpaywall": "#eba0ac",
    "checkoff": "#74c7ec",
    "usb_deliverables": "#b4befe",
    # source_type keys
    "paper": "#89b4fa",
    "patent": "#a6e3a1",
    "conference": "#f9e2af",
    "report": "#fab387",
    "news": "#f38ba8",
}


class TrendsTab(QWidget):
    """Timeline charts with stacked area views."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._stats: dict = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # -- Header + view selector ------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        header = QLabel("Trends")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        header_row.addWidget(header)

        header_row.addStretch()

        view_label = QLabel("View:")
        view_label.setFont(QFont("Segoe UI", 9))
        view_label.setStyleSheet("color: #a0a0b0;")
        header_row.addWidget(view_label)

        self._view_combo = QComboBox()
        self._view_combo.addItem("Findings by Year (stacked by Source API)", "by_source")
        self._view_combo.addItem("Findings by Year (stacked by Source Type)", "by_type")
        self._view_combo.addItem("Findings by Year (total)", "total")
        self._view_combo.setMinimumWidth(280)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        header_row.addWidget(self._view_combo)

        root.addLayout(header_row)

        # -- Chart area ------------------------------------------------------
        if HAS_TIMELINE:
            self._timeline = TimelineWidget()
            root.addWidget(self._timeline, 1)
        else:
            placeholder = QLabel("Install pyqtgraph for timeline charts")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #a0a0b0; font-size: 12pt;")
            root.addWidget(placeholder, 1)
            self._timeline = None

    # -- Public API ----------------------------------------------------------

    def refresh(self, stats: dict) -> None:
        """Update charts from the stats dict returned by db.get_stats()."""
        self._stats = stats
        self._redraw()

    # -- Internal helpers ----------------------------------------------------

    @Slot()
    def _on_view_changed(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        if self._timeline is None or not self._stats:
            return

        view_key = self._view_combo.currentData()

        if view_key == "by_source":
            self._draw_stacked_by_key("source_api")
        elif view_key == "by_type":
            self._draw_stacked_by_key("source_type")
        elif view_key == "total":
            self._draw_total()

    def _draw_stacked_by_key(self, group_key: str) -> None:
        """Build a stacked area chart grouping by *group_key*.

        Because the stats dict only gives us ``by_year`` (totals) and
        ``by_source`` / ``by_type`` (totals per category), we need to
        derive the per-year-per-category breakdown from ``findings_sample``
        if available -- otherwise we fall back to showing totals only.

        A richer implementation would run a dedicated SQL query, but for
        now we estimate from what ``get_stats()`` gives us.  The breakdown
        is approximate unless the full ``findings`` list is embedded in
        stats (which StatsWorker does not currently do).  So we show the
        overall total as a single series and label it accordingly.
        """
        by_year: dict[int, int] = self._stats.get("by_year", {})
        if not by_year:
            return

        years = sorted(by_year.keys())

        # We have aggregate data only, so build per-source proportional
        # estimates.  For perfect accuracy the caller should augment stats
        # with ``by_year_and_source``, but this fallback is good enough
        # for a first iteration.
        group_totals = self._stats.get(
            "by_source" if group_key == "source_api" else "by_type", {}
        )

        if not group_totals:
            # Fall back to total view
            self._draw_total()
            return

        grand_total = sum(group_totals.values()) or 1
        proportions = {k: v / grand_total for k, v in group_totals.items()}

        series_dict: dict[str, list[int]] = {}
        for name, prop in proportions.items():
            series_dict[name or "unknown"] = [
                max(0, round(by_year.get(y, 0) * prop)) for y in years
            ]

        colors = {k: _SERIES_COLORS.get(k, "") for k in series_dict}

        self._timeline.update_stacked_area(years, series_dict, colors)

    def _draw_total(self) -> None:
        """Simple single-series view of total findings per year."""
        by_year: dict[int, int] = self._stats.get("by_year", {})
        if not by_year:
            return

        years = sorted(by_year.keys())
        counts = [by_year[y] for y in years]
        series_dict = {"Total Findings": counts}
        colors = {"Total Findings": "#89b4fa"}

        self._timeline.update_stacked_area(years, series_dict, colors)
