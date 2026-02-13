"""Overview / Dashboard tab — KPI cards and summary charts.

Displays a row of KPI cards (Total Findings, USB Deliverables,
Checkoff Projects, Enriched, Tags, Sources) and two side-by-side
charts: findings-by-year bar chart and findings-by-source pie chart,
rendered via matplotlib embedded in FigureCanvasQTAgg.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ..widgets.kpi_card import KPICard

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ---------------------------------------------------------------------------
# Dark-theme palette (Catppuccin Mocha inspired)
# ---------------------------------------------------------------------------
_BG = "#1e1e2e"
_FG = "#cdd6f4"
_MUTED = "#a0a0b0"

_CHART_COLORS = [
    "#89b4fa", "#a6e3a1", "#f9e2af", "#fab387", "#f38ba8",
    "#cba6f7", "#94e2d5", "#eba0ac", "#74c7ec", "#b4befe",
]


class OverviewTab(QWidget):
    """Dashboard KPI cards and summary charts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # -- Header ----------------------------------------------------------
        header = QLabel("Dashboard")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {_FG};")
        root.addWidget(header)

        # -- KPI row ---------------------------------------------------------
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        self._kpi_total = KPICard("Total Findings")
        self._kpi_usb = KPICard("USB Deliverables")
        self._kpi_checkoff = KPICard("Checkoff Projects")
        self._kpi_enriched = KPICard("Enriched")
        self._kpi_tags = KPICard("Tags")
        self._kpi_sources = KPICard("Sources")

        for card in (
            self._kpi_total,
            self._kpi_usb,
            self._kpi_checkoff,
            self._kpi_enriched,
            self._kpi_tags,
            self._kpi_sources,
        ):
            kpi_row.addWidget(card)

        root.addLayout(kpi_row)

        # -- Charts row ------------------------------------------------------
        charts_row = QHBoxLayout()
        charts_row.setSpacing(16)

        if HAS_MATPLOTLIB:
            # Bar chart: findings by year
            self._year_fig = Figure(figsize=(6, 3.5), facecolor=_BG)
            self._year_canvas = FigureCanvas(self._year_fig)
            self._year_canvas.setStyleSheet(f"background: {_BG};")
            self._year_canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._year_ax = self._year_fig.add_subplot(111)
            charts_row.addWidget(self._year_canvas, 3)

            # Pie chart: findings by source
            self._source_fig = Figure(figsize=(4, 3.5), facecolor=_BG)
            self._source_canvas = FigureCanvas(self._source_fig)
            self._source_canvas.setStyleSheet(f"background: {_BG};")
            self._source_canvas.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            self._source_ax = self._source_fig.add_subplot(111)
            charts_row.addWidget(self._source_canvas, 2)
        else:
            placeholder = QLabel("Install matplotlib for charts")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(f"color: {_MUTED}; font-size: 12pt;")
            charts_row.addWidget(placeholder)

        root.addLayout(charts_row, 1)

    # -- Public API ----------------------------------------------------------

    def refresh(self, stats: dict) -> None:
        """Update KPI cards and charts from a stats dict (db.get_stats())."""
        self._update_kpis(stats)
        if HAS_MATPLOTLIB:
            self._draw_year_chart(stats.get("by_year", {}))
            self._draw_source_chart(stats.get("by_source", {}))

    # -- Internal helpers ----------------------------------------------------

    def _update_kpis(self, stats: dict) -> None:
        self._kpi_total.set_value(f"{stats.get('total_findings', 0):,}")
        self._kpi_usb.set_value(f"{stats.get('total_usb_deliverables', 0):,}")
        self._kpi_checkoff.set_value(f"{stats.get('total_checkoff', 0):,}")
        self._kpi_enriched.set_value(f"{stats.get('total_enriched', 0):,}")
        self._kpi_tags.set_value(f"{stats.get('total_tags', 0):,}")

        source_count = len(stats.get("by_source", {}))
        self._kpi_sources.set_value(str(source_count))

    def _draw_year_chart(self, by_year: dict[int, int]) -> None:
        """Render a bar chart of findings per year."""
        ax = self._year_ax
        ax.clear()
        ax.set_facecolor(_BG)

        if not by_year:
            ax.text(
                0.5, 0.5, "No data",
                transform=ax.transAxes,
                ha="center", va="center",
                color=_MUTED, fontsize=12,
            )
            self._year_canvas.draw_idle()
            return

        years = sorted(by_year.keys())
        counts = [by_year[y] for y in years]

        ax.bar(years, counts, color=_CHART_COLORS[0], edgecolor="none", width=0.8)
        ax.set_xlabel("Year", color=_MUTED, fontsize=9)
        ax.set_ylabel("Findings", color=_MUTED, fontsize=9)
        ax.set_title("Findings by Year", color=_FG, fontsize=11, fontweight="bold")
        ax.tick_params(colors=_FG, labelsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")

        # Integer x-ticks if few years, otherwise let matplotlib decide
        if len(years) <= 30:
            ax.set_xticks(years)
            ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right", fontsize=7)

        self._year_fig.tight_layout()
        self._year_canvas.draw_idle()

    def _draw_source_chart(self, by_source: dict[str, int]) -> None:
        """Render a pie chart of findings by source API."""
        ax = self._source_ax
        ax.clear()
        ax.set_facecolor(_BG)

        if not by_source:
            ax.text(
                0.5, 0.5, "No data",
                transform=ax.transAxes,
                ha="center", va="center",
                color=_MUTED, fontsize=12,
            )
            self._source_canvas.draw_idle()
            return

        labels = list(by_source.keys())
        sizes = list(by_source.values())
        colors = _CHART_COLORS[: len(labels)]

        # Handle case where there are more sources than colors
        while len(colors) < len(labels):
            colors.extend(_CHART_COLORS)
        colors = colors[: len(labels)]

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            startangle=90,
            textprops={"color": _FG, "fontsize": 8},
        )
        for txt in autotexts:
            txt.set_fontsize(7)
            txt.set_color("white")

        ax.set_title(
            "Findings by Source", color=_FG, fontsize=11, fontweight="bold"
        )

        self._source_fig.tight_layout()
        self._source_canvas.draw_idle()
