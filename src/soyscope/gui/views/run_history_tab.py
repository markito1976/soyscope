"""Run History / Task Launcher tab -- the primary control panel.

Provides buttons to trigger ALL SoyScope backend operations from the
GUI, a ProgressPanel showing running/completed tasks with progress
bars, and a live log viewer.

Action buttons:
- Historical Build          -- launches HistoricalBuildWorker
- Import Checkoff           -- file dialog for JSON, launches CheckoffImportWorker
- Import USB Deliverables   -- file dialog for CSV, launches USBDeliverablesImportWorker
- Resolve OA Links          -- launches OA resolution via HistoricalBuildWorker variant
- Run AI Enrichment         -- tier selector (1/2/3/all) + limit spinbox
- Refresh                   -- launches incremental update

Each button is disabled while its task is running and re-enabled on
completion.  Worker result/error signals update the status and
re-enable buttons.

Build Dashboard:
    When a Historical Build or Incremental Refresh is active, a
    dashboard section expands between the action buttons and the
    progress/log panel showing:
    - API Source Health Grid (14 sources with status indicators)
    - Build Progress Panel (query counter, progress bar, stats, timing)
    - Live Findings Feed (last ~50 findings as they arrive)
    - Per-Source Stats Table (queries, results, errors per API)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Slot, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QSpinBox,
    QLabel,
    QFileDialog,
    QSizePolicy,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
)

from ..widgets.progress_panel import ProgressPanel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# All 14 API source names in display order
# ---------------------------------------------------------------------------
ALL_SOURCES = [
    "OpenAlex", "Semantic Scholar", "Crossref", "PubMed",
    "EXA", "Tavily", "CORE", "Unpaywall",
    "OSTI", "PatentsView", "SBIR", "AGRIS",
    "Lens.org", "USDA ERS",
]

# Map display names to internal keys used in build_progress dicts
_SOURCE_KEY_MAP = {
    "OpenAlex": "openalex",
    "Semantic Scholar": "semantic_scholar",
    "Crossref": "crossref",
    "PubMed": "pubmed",
    "EXA": "exa",
    "Tavily": "tavily",
    "CORE": "core",
    "Unpaywall": "unpaywall",
    "OSTI": "osti",
    "PatentsView": "patentsview",
    "SBIR": "sbir",
    "AGRIS": "agris",
    "Lens.org": "lens",
    "USDA ERS": "usda_ers",
}


# ---------------------------------------------------------------------------
# Stylesheet fragments
# ---------------------------------------------------------------------------
_BTN_STYLE = """
    QPushButton {
        background: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 6px;
        padding: 8px 16px;
        font-size: 10pt;
        font-weight: bold;
        min-width: 140px;
    }
    QPushButton:hover {
        background: #45475a;
        border-color: #89b4fa;
    }
    QPushButton:pressed {
        background: #585b70;
    }
    QPushButton:disabled {
        background: #1e1e2e;
        color: #585b70;
        border-color: #313244;
    }
"""

_GROUP_STYLE = """
    QGroupBox {
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 8px;
        margin-top: 12px;
        padding: 16px 12px 12px 12px;
        font-size: 11pt;
        font-weight: bold;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
"""

_DASHBOARD_GROUP_STYLE = """
    QGroupBox {
        color: #89b4fa;
        border: 1px solid #45475a;
        border-radius: 8px;
        margin-top: 12px;
        padding: 16px 12px 12px 12px;
        font-size: 11pt;
        font-weight: bold;
        background: #181825;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
"""

_SOURCE_TILE_STYLE = """
    QFrame {{
        background: {bg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 4px 6px;
    }}
"""

_PROGRESS_BAR_STYLE = """
    QProgressBar {
        background: #1e1e2e;
        border: 1px solid #45475a;
        border-radius: 5px;
        text-align: center;
        color: #cdd6f4;
        height: 24px;
        font-size: 10pt;
        font-weight: bold;
    }
    QProgressBar::chunk {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #89b4fa, stop:1 #74c7ec);
        border-radius: 4px;
    }
"""

_STATS_TABLE_STYLE = """
    QTableWidget {
        background: #181825;
        alternate-background-color: #1e1e2e;
        gridline-color: #313244;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        font-size: 9pt;
    }
    QHeaderView::section {
        background: #313244;
        color: #89b4fa;
        padding: 4px 8px;
        border: 1px solid #45475a;
        font-weight: bold;
        font-size: 9pt;
    }
    QTableWidget::item {
        padding: 2px 6px;
    }
"""

_FINDINGS_LIST_STYLE = """
    QListWidget {
        background: #181825;
        color: #cdd6f4;
        border: 1px solid #45475a;
        border-radius: 4px;
        font-family: 'Cascadia Code', 'Consolas', monospace;
        font-size: 9pt;
    }
    QListWidget::item {
        padding: 2px 4px;
        border-bottom: 1px solid #232336;
    }
    QListWidget::item:selected {
        background: #313244;
    }
"""


# ---------------------------------------------------------------------------
# Helper: format seconds to HH:MM:SS
# ---------------------------------------------------------------------------
def _fmt_time(seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class RunHistoryTab(QWidget):
    """Task launcher, progress tracker, and live log viewer.

    Signals:
        data_changed:
            Emitted after any task completes successfully that might
            have modified the database, so other tabs can refresh.
    """

    data_changed = Signal()

    def __init__(self, db_path: str | None = None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._db_path = db_path or ""
        self._running_tasks: set[str] = set()

        # Build dashboard state
        self._build_start_time: float | None = None
        self._source_stats: dict[str, dict] = {}
        self._findings_count = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # -- Header ----------------------------------------------------------
        header = QLabel("Task Launcher")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        root.addWidget(header)

        # -- Launch Tasks group ----------------------------------------------
        self._build_action_group(root)

        # -- Build Dashboard (hidden by default) -----------------------------
        self._build_dashboard_section(root)

        # -- Progress panel --------------------------------------------------
        self._progress_panel = ProgressPanel()
        root.addWidget(self._progress_panel, 1)

    # =====================================================================
    # Public API
    # =====================================================================

    def set_db_path(self, db_path: str) -> None:
        """Update the database path (called by the main window)."""
        self._db_path = db_path

    def refresh(self) -> None:
        """No-op for this tab (tasks are user-triggered)."""
        pass

    def append_log(self, message: str) -> None:
        """Convenience: forward a log message to the embedded ProgressPanel."""
        self._progress_panel.append_log(message)

    # =====================================================================
    # Layout construction
    # =====================================================================

    def _build_action_group(self, parent_layout: QVBoxLayout) -> None:
        group = QGroupBox("Launch Tasks")
        group.setStyleSheet(_GROUP_STYLE)

        grid = QVBoxLayout(group)
        grid.setSpacing(10)

        # -- Row 1: Historical Build + Refresh ------------------------------
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self._btn_build = QPushButton("Historical Build")
        self._btn_build.setStyleSheet(_BTN_STYLE)
        self._btn_build.setToolTip(
            "Run the full 25-year historical database build across all API sources."
        )
        self._btn_build.clicked.connect(self._launch_historical_build)
        row1.addWidget(self._btn_build)

        self._btn_refresh = QPushButton("Refresh (Incremental)")
        self._btn_refresh.setStyleSheet(_BTN_STYLE)
        self._btn_refresh.setToolTip(
            "Run an incremental update fetching only new findings since the last run."
        )
        self._btn_refresh.clicked.connect(self._launch_refresh)
        row1.addWidget(self._btn_refresh)

        row1.addStretch()
        grid.addLayout(row1)

        # -- Row 2: Import buttons ------------------------------------------
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        self._btn_checkoff = QPushButton("Import Checkoff")
        self._btn_checkoff.setStyleSheet(_BTN_STYLE)
        self._btn_checkoff.setToolTip(
            "Import Soybean Checkoff Research DB projects from a JSON file."
        )
        self._btn_checkoff.clicked.connect(self._launch_checkoff_import)
        row2.addWidget(self._btn_checkoff)

        self._btn_usb = QPushButton("Import USB Deliverables")
        self._btn_usb.setStyleSheet(_BTN_STYLE)
        self._btn_usb.setToolTip(
            "Import USB-funded research deliverables from a CSV file."
        )
        self._btn_usb.clicked.connect(self._launch_usb_import)
        row2.addWidget(self._btn_usb)

        self._btn_oa = QPushButton("Resolve OA Links")
        self._btn_oa.setStyleSheet(_BTN_STYLE)
        self._btn_oa.setToolTip(
            "Resolve Open Access links via Unpaywall for findings with DOIs."
        )
        self._btn_oa.clicked.connect(self._launch_oa_resolve)
        row2.addWidget(self._btn_oa)

        row2.addStretch()
        grid.addLayout(row2)

        # -- Row 3: AI Enrichment -------------------------------------------
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        self._btn_enrich = QPushButton("Run AI Enrichment")
        self._btn_enrich.setStyleSheet(_BTN_STYLE)
        self._btn_enrich.setToolTip(
            "Run Claude AI enrichment on un-enriched findings."
        )
        self._btn_enrich.clicked.connect(self._launch_enrichment)
        row3.addWidget(self._btn_enrich)

        # Tier selector
        tier_label = QLabel("Tier:")
        tier_label.setFont(QFont("Segoe UI", 9))
        tier_label.setStyleSheet("color: #a0a0b0;")
        row3.addWidget(tier_label)

        self._tier_combo = QComboBox()
        self._tier_combo.addItem("All Tiers", 0)
        self._tier_combo.addItem("Tier 1 (Catalog)", 1)
        self._tier_combo.addItem("Tier 2 (Summary)", 2)
        self._tier_combo.addItem("Tier 3 (Deep)", 3)
        self._tier_combo.setMinimumWidth(140)
        row3.addWidget(self._tier_combo)

        # Limit spinbox
        limit_label = QLabel("Limit:")
        limit_label.setFont(QFont("Segoe UI", 9))
        limit_label.setStyleSheet("color: #a0a0b0;")
        row3.addWidget(limit_label)

        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 10000)
        self._limit_spin.setValue(100)
        self._limit_spin.setSpecialValueText("Default")
        self._limit_spin.setToolTip(
            "Maximum findings to enrich per tier.  0 = use default limits."
        )
        self._limit_spin.setMinimumWidth(80)
        row3.addWidget(self._limit_spin)

        row3.addStretch()
        grid.addLayout(row3)

        parent_layout.addWidget(group)

    # =====================================================================
    # Build Dashboard construction
    # =====================================================================

    def _build_dashboard_section(self, parent_layout: QVBoxLayout) -> None:
        """Create the collapsible Build Dashboard section.

        Contains four sub-panels:
        1. API Source Health Grid
        2. Build Progress Panel
        3. Live Findings Feed
        4. Per-Source Stats Table

        The entire section is hidden when no build is active.
        """
        self._dashboard_group = QGroupBox("Build Dashboard")
        self._dashboard_group.setStyleSheet(_DASHBOARD_GROUP_STYLE)
        self._dashboard_group.setVisible(False)

        dash_layout = QVBoxLayout(self._dashboard_group)
        dash_layout.setSpacing(10)
        dash_layout.setContentsMargins(8, 16, 8, 8)

        # ---- 1. API Source Health Grid ----
        self._build_source_health_grid(dash_layout)

        # ---- 2. Build Progress Panel ----
        self._build_progress_panel(dash_layout)

        # ---- 3. Live Findings Feed ----
        self._build_findings_feed(dash_layout)

        # ---- 4. Per-Source Stats Table ----
        self._build_source_stats_table(dash_layout)

        parent_layout.addWidget(self._dashboard_group)

    def _build_source_health_grid(self, parent_layout: QVBoxLayout) -> None:
        """Create a 4-column grid of all 14 API sources with status dots."""
        section_label = QLabel("API Source Status")
        section_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        section_label.setStyleSheet("color: #89b4fa;")
        parent_layout.addWidget(section_label)

        grid_frame = QFrame()
        grid_frame.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #313244; "
            "border-radius: 6px; padding: 8px; }"
        )
        grid = QGridLayout(grid_frame)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)

        self._source_tiles: dict[str, dict[str, QLabel]] = {}

        for idx, source_name in enumerate(ALL_SOURCES):
            row = idx // 4
            col = idx % 4

            tile = QFrame()
            tile.setMinimumWidth(160)
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(6, 4, 6, 4)
            tile_layout.setSpacing(2)

            # Top row: dot + name
            name_row = QHBoxLayout()
            name_row.setSpacing(4)

            dot_label = QLabel("\u25cf")  # filled circle
            dot_label.setFont(QFont("Segoe UI", 10))
            dot_label.setStyleSheet("color: #585b70;")  # grey = idle
            dot_label.setFixedWidth(14)
            name_row.addWidget(dot_label)

            name_label = QLabel(source_name)
            name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_label.setStyleSheet("color: #cdd6f4;")
            name_row.addWidget(name_label)
            name_row.addStretch()

            tile_layout.addLayout(name_row)

            # Bottom row: stats
            stats_label = QLabel("--")
            stats_label.setFont(QFont("Segoe UI", 8))
            stats_label.setStyleSheet("color: #6c7086;")
            tile_layout.addWidget(stats_label)

            tile.setStyleSheet(
                "QFrame { background: #232336; border: 1px solid #313244; "
                "border-radius: 4px; }"
            )

            grid.addWidget(tile, row, col)

            self._source_tiles[source_name] = {
                "dot": dot_label,
                "name": name_label,
                "stats": stats_label,
                "frame": tile,
            }

        parent_layout.addWidget(grid_frame)

    def _build_progress_panel(self, parent_layout: QVBoxLayout) -> None:
        """Create the detailed build progress panel with bar and stats."""
        progress_frame = QFrame()
        progress_frame.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #313244; "
            "border-radius: 6px; padding: 8px; }"
        )
        pf_layout = QVBoxLayout(progress_frame)
        pf_layout.setSpacing(6)
        pf_layout.setContentsMargins(12, 8, 12, 8)

        # Large query counter text
        self._query_counter_label = QLabel("Waiting for build to start...")
        self._query_counter_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._query_counter_label.setStyleSheet("color: #cdd6f4;")
        self._query_counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pf_layout.addWidget(self._query_counter_label)

        # Progress bar
        self._build_progress_bar = QProgressBar()
        self._build_progress_bar.setRange(0, 1000)  # use 1000 for 0.1% resolution
        self._build_progress_bar.setValue(0)
        self._build_progress_bar.setTextVisible(False)
        self._build_progress_bar.setFixedHeight(24)
        self._build_progress_bar.setStyleSheet(_PROGRESS_BAR_STYLE)
        pf_layout.addWidget(self._build_progress_bar)

        # Stats row: new | updated | errors
        stats_row = QHBoxLayout()
        stats_row.setSpacing(24)

        self._stat_new = QLabel("New findings: 0")
        self._stat_new.setFont(QFont("Segoe UI", 9))
        self._stat_new.setStyleSheet("color: #27ae60;")
        stats_row.addWidget(self._stat_new)

        self._stat_updated = QLabel("Updated: 0")
        self._stat_updated.setFont(QFont("Segoe UI", 9))
        self._stat_updated.setStyleSheet("color: #89b4fa;")
        stats_row.addWidget(self._stat_updated)

        self._stat_errors = QLabel("Errors: 0")
        self._stat_errors.setFont(QFont("Segoe UI", 9))
        self._stat_errors.setStyleSheet("color: #6c7086;")
        stats_row.addWidget(self._stat_errors)

        stats_row.addStretch()
        pf_layout.addLayout(stats_row)

        # Timing row: elapsed | ETA | rate
        timing_row = QHBoxLayout()
        timing_row.setSpacing(24)

        self._stat_elapsed = QLabel("Elapsed: 00:00:00")
        self._stat_elapsed.setFont(QFont("Segoe UI", 9))
        self._stat_elapsed.setStyleSheet("color: #a6adc8;")
        timing_row.addWidget(self._stat_elapsed)

        self._stat_eta = QLabel("ETA: --")
        self._stat_eta.setFont(QFont("Segoe UI", 9))
        self._stat_eta.setStyleSheet("color: #a6adc8;")
        timing_row.addWidget(self._stat_eta)

        self._stat_rate = QLabel("Rate: -- queries/sec")
        self._stat_rate.setFont(QFont("Segoe UI", 9))
        self._stat_rate.setStyleSheet("color: #a6adc8;")
        timing_row.addWidget(self._stat_rate)

        timing_row.addStretch()
        pf_layout.addLayout(timing_row)

        # Current query line
        self._current_query_label = QLabel("Current: --")
        self._current_query_label.setFont(QFont("Cascadia Code", 9))
        self._current_query_label.setStyleSheet("color: #74c7ec;")
        self._current_query_label.setWordWrap(True)
        pf_layout.addWidget(self._current_query_label)

        parent_layout.addWidget(progress_frame)

    def _build_findings_feed(self, parent_layout: QVBoxLayout) -> None:
        """Create a scrolling list showing the last ~50 findings as they arrive."""
        section_label = QLabel("Live Findings Feed")
        section_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        section_label.setStyleSheet("color: #89b4fa;")
        parent_layout.addWidget(section_label)

        self._findings_list = QListWidget()
        self._findings_list.setMaximumHeight(150)
        self._findings_list.setStyleSheet(_FINDINGS_LIST_STYLE)
        self._findings_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._findings_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Placeholder text shown when list is empty
        self._findings_list.addItem(
            QListWidgetItem("  Waiting for findings...")
        )
        parent_layout.addWidget(self._findings_list)

    def _build_source_stats_table(self, parent_layout: QVBoxLayout) -> None:
        """Create the per-source statistics table."""
        section_label = QLabel("Per-Source Breakdown")
        section_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        section_label.setStyleSheet("color: #89b4fa;")
        parent_layout.addWidget(section_label)

        self._stats_table = QTableWidget(len(ALL_SOURCES), 5)
        self._stats_table.setHorizontalHeaderLabels(
            ["Source", "Queries", "Results", "Errors", "Status"]
        )
        self._stats_table.setMaximumHeight(220)
        self._stats_table.setStyleSheet(_STATS_TABLE_STYLE)
        self._stats_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._stats_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._stats_table.setAlternatingRowColors(True)
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.setShowGrid(True)

        # Column widths
        h_header = self._stats_table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            h_header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            self._stats_table.setColumnWidth(col, 80)

        # Populate with source names and defaults
        for row, source_name in enumerate(ALL_SOURCES):
            name_item = QTableWidgetItem(source_name)
            name_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            self._stats_table.setItem(row, 0, name_item)

            for col in range(1, 4):
                item = QTableWidgetItem("0")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._stats_table.setItem(row, col, item)

            status_item = QTableWidgetItem("Idle")
            status_item.setForeground(QColor("#6c7086"))
            self._stats_table.setItem(row, 4, status_item)

        parent_layout.addWidget(self._stats_table)

    # =====================================================================
    # Dashboard visibility
    # =====================================================================

    def _show_dashboard(self) -> None:
        """Show the Build Dashboard and reset all widgets to initial state."""
        self._build_start_time = time.monotonic()
        self._source_stats = {}
        self._findings_count = 0

        # Reset progress panel
        self._query_counter_label.setText("Waiting for build to start...")
        self._build_progress_bar.setValue(0)
        self._stat_new.setText("New findings: 0")
        self._stat_updated.setText("Updated: 0")
        self._stat_errors.setText("Errors: 0")
        self._stat_errors.setStyleSheet("color: #6c7086;")
        self._stat_elapsed.setText("Elapsed: 00:00:00")
        self._stat_eta.setText("ETA: --")
        self._stat_rate.setText("Rate: -- queries/sec")
        self._current_query_label.setText("Current: --")

        # Reset source tiles
        for source_name, tiles in self._source_tiles.items():
            tiles["dot"].setStyleSheet("color: #585b70;")  # grey
            tiles["stats"].setText("--")

        # Reset findings feed
        self._findings_list.clear()

        # Reset stats table
        for row in range(len(ALL_SOURCES)):
            for col in range(1, 4):
                item = self._stats_table.item(row, col)
                if item:
                    item.setText("0")
            status_item = self._stats_table.item(row, 4)
            if status_item:
                status_item.setText("Idle")
                status_item.setForeground(QColor("#6c7086"))

        self._dashboard_group.setVisible(True)

    def _hide_dashboard(self) -> None:
        """Hide the Build Dashboard when no build is active."""
        self._dashboard_group.setVisible(False)
        self._build_start_time = None

    # =====================================================================
    # Build progress handler
    # =====================================================================

    @Slot(dict)
    def _on_build_progress(self, data: dict) -> None:
        """Update all dashboard widgets from a build_progress signal.

        Expected dict keys (all optional -- absent keys are simply skipped):
            event: str           -- e.g. "query_complete", "finding_new", "source_status"
            completed: int       -- queries completed so far
            total: int           -- total queries planned
            query: str           -- current query text
            query_type: str      -- e.g. "academic", "patent", "government"
            source: str          -- source key for this event
            sources: list[str]   -- source keys targeted by this query
            new_findings: int    -- new findings from this query
            updated_findings: int-- updated findings from this query
            total_new: int       -- cumulative new findings
            total_updated: int   -- cumulative updated findings
            errors: int          -- cumulative error count
            elapsed_seconds: float -- seconds since build start
            source_stats: dict   -- per-source breakdown:
                {source_key: {"queries": int, "results": int, "errors": int,
                              "status": str}}
            finding: dict        -- single finding just discovered:
                {"year": int, "title": str, "doi": str, "source": str}
            findings: list[dict] -- batch of findings just discovered
        """
        event = data.get("event", "")

        # -- Update query counter and progress bar --------------------------
        completed = data.get("completed")
        total = data.get("total")
        if completed is not None and total is not None and total > 0:
            pct = completed / total * 100
            self._query_counter_label.setText(
                f"Query {completed:,} of {total:,} ({pct:.1f}%)"
            )
            # Map to 0-1000 range for 0.1% resolution
            self._build_progress_bar.setValue(int(pct * 10))

        # -- Update stats row -----------------------------------------------
        total_new = data.get("total_new")
        if total_new is not None:
            self._stat_new.setText(f"New findings: {total_new:,}")

        total_updated = data.get("total_updated")
        if total_updated is not None:
            self._stat_updated.setText(f"Updated: {total_updated:,}")

        errors = data.get("errors")
        if errors is not None:
            self._stat_errors.setText(f"Errors: {errors:,}")
            if errors > 0:
                self._stat_errors.setStyleSheet("color: #e74c3c;")
            else:
                self._stat_errors.setStyleSheet("color: #6c7086;")

        # -- Update timing row ----------------------------------------------
        elapsed = data.get("elapsed_seconds")
        if elapsed is None and self._build_start_time is not None:
            elapsed = time.monotonic() - self._build_start_time

        if elapsed is not None:
            self._stat_elapsed.setText(f"Elapsed: {_fmt_time(elapsed)}")

            if (
                completed is not None
                and total is not None
                and completed > 0
                and total > 0
            ):
                rate = completed / elapsed if elapsed > 0 else 0
                self._stat_rate.setText(f"Rate: {rate:.1f} queries/sec")

                remaining = total - completed
                if rate > 0:
                    eta_seconds = remaining / rate
                    self._stat_eta.setText(f"ETA: ~{_fmt_time(eta_seconds)}")
                else:
                    self._stat_eta.setText("ETA: --")

        # -- Update current query -------------------------------------------
        query_text = data.get("query")
        if query_text:
            query_type = data.get("query_type", "")
            sources_list = data.get("sources", [])
            source_str = ", ".join(sources_list) if sources_list else ""
            type_str = f" [{query_type}]" if query_type else ""
            target_str = f" -> {source_str}" if source_str else ""
            self._current_query_label.setText(
                f"Searching: '{query_text}'{type_str}{target_str}"
            )

        # -- Update per-source stats ----------------------------------------
        source_stats = data.get("source_stats")
        if source_stats:
            self._source_stats = source_stats
            self._update_source_displays(source_stats)

        # If we got a per-event source update instead of bulk source_stats
        source_key = data.get("source")
        if source_key and not source_stats:
            # Accumulate into our local tracking dict
            if source_key not in self._source_stats:
                self._source_stats[source_key] = {
                    "queries": 0,
                    "results": 0,
                    "errors": 0,
                    "status": "Active",
                }
            ss = self._source_stats[source_key]
            ss["queries"] = ss.get("queries", 0) + 1
            new_f = data.get("new_findings", 0)
            ss["results"] = ss.get("results", 0) + new_f
            if data.get("error"):
                ss["errors"] = ss.get("errors", 0) + 1
            self._update_source_displays(self._source_stats)

        # -- Update findings feed -------------------------------------------
        self._process_findings(data)

    def _update_source_displays(self, source_stats: dict) -> None:
        """Update both the source health grid tiles and the stats table."""
        for display_name, tiles in self._source_tiles.items():
            key = _SOURCE_KEY_MAP.get(display_name, display_name.lower())
            ss = source_stats.get(key, {})

            queries = ss.get("queries", 0)
            results = ss.get("results", 0)
            error_count = ss.get("errors", 0)
            status = ss.get("status", "idle").lower()

            # Update dot color
            if status in ("active", "ok", "running"):
                tiles["dot"].setStyleSheet("color: #27ae60;")  # green
            elif status in ("error", "circuit_open", "circuit open", "failed"):
                tiles["dot"].setStyleSheet("color: #e74c3c;")  # red
            elif status in ("disabled", "no_key", "no key"):
                tiles["dot"].setStyleSheet("color: #585b70;")  # grey
            elif queries > 0:
                tiles["dot"].setStyleSheet("color: #27ae60;")  # green (active)
            else:
                tiles["dot"].setStyleSheet("color: #585b70;")  # grey (idle)

            # Update stats text
            if queries > 0 or results > 0:
                tiles["stats"].setText(
                    f"{queries:,} queries, {results:,} results"
                )
                tiles["stats"].setStyleSheet("color: #a6adc8;")
            else:
                tiles["stats"].setText("--")
                tiles["stats"].setStyleSheet("color: #6c7086;")

        # Update stats table rows
        for row, display_name in enumerate(ALL_SOURCES):
            key = _SOURCE_KEY_MAP.get(display_name, display_name.lower())
            ss = source_stats.get(key, {})

            queries = ss.get("queries", 0)
            results = ss.get("results", 0)
            error_count = ss.get("errors", 0)
            status = ss.get("status", "Idle")

            q_item = self._stats_table.item(row, 1)
            if q_item:
                q_item.setText(f"{queries:,}")

            r_item = self._stats_table.item(row, 2)
            if r_item:
                r_item.setText(f"{results:,}")

            e_item = self._stats_table.item(row, 3)
            if e_item:
                e_item.setText(f"{error_count:,}")
                if error_count > 0:
                    e_item.setForeground(QColor("#e74c3c"))
                else:
                    e_item.setForeground(QColor("#cdd6f4"))

            s_item = self._stats_table.item(row, 4)
            if s_item:
                status_display = status.replace("_", " ").title()
                s_item.setText(status_display)
                status_lower = status.lower()
                if status_lower in ("active", "ok", "running"):
                    s_item.setForeground(QColor("#27ae60"))
                elif status_lower in (
                    "error",
                    "circuit_open",
                    "circuit open",
                    "failed",
                ):
                    s_item.setForeground(QColor("#e74c3c"))
                elif status_lower in ("disabled", "no_key", "no key"):
                    s_item.setForeground(QColor("#585b70"))
                else:
                    s_item.setForeground(QColor("#6c7086"))

    def _process_findings(self, data: dict) -> None:
        """Add new findings to the live findings feed."""
        findings_to_add: list[dict] = []

        # Single finding
        finding = data.get("finding")
        if finding:
            findings_to_add.append(finding)

        # Batch of findings
        findings_batch = data.get("findings")
        if findings_batch:
            findings_to_add.extend(findings_batch)

        if not findings_to_add:
            return

        # Remove placeholder text on first real finding
        if self._findings_count == 0:
            self._findings_list.clear()

        for f in findings_to_add:
            year = f.get("year", "????")
            title = f.get("title", "Untitled")
            doi = f.get("doi", "")
            source = f.get("source", "unknown")

            # Truncate title for display
            if len(title) > 70:
                title = title[:67] + "..."

            doi_str = f"  DOI: {doi}" if doi else ""
            line = f"[{year}] {title}{doi_str}  via: {source}"

            item = QListWidgetItem(line)
            item.setFont(QFont("Cascadia Code", 8))

            # Color by source type
            if source in ("openalex", "crossref", "pubmed", "semantic_scholar"):
                item.setForeground(QColor("#89b4fa"))  # blue for academic
            elif source in ("patentsview", "lens"):
                item.setForeground(QColor("#f9e2af"))  # yellow for patents
            elif source in ("osti", "sbir", "usda_ers", "agris"):
                item.setForeground(QColor("#a6e3a1"))  # green for government
            else:
                item.setForeground(QColor("#cdd6f4"))  # default

            self._findings_list.insertItem(0, item)  # newest at top
            self._findings_count += 1

        # Keep only the last 50 findings displayed
        while self._findings_list.count() > 50:
            self._findings_list.takeItem(self._findings_list.count() - 1)

        # Scroll to top to show newest
        self._findings_list.scrollToTop()

    # =====================================================================
    # Task launchers
    # =====================================================================

    def _ensure_db_path(self) -> bool:
        """Check that a DB path is configured.  Return True if OK."""
        if self._db_path:
            return True
        QMessageBox.warning(
            self, "No Database",
            "No database path is configured.  Open or create a database first.",
        )
        return False

    def _launch_historical_build(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "Historical Build"
        if task_name in self._running_tasks:
            return

        from ..workers.build_worker import HistoricalBuildWorker

        worker = HistoricalBuildWorker(self._db_path, concurrency=3)

        # Connect build_progress signal if available
        if hasattr(worker.signals, 'build_progress'):
            worker.signals.build_progress.connect(self._on_build_progress)

        # Show dashboard and hide on completion
        self._show_dashboard()
        worker.signals.finished.connect(self._on_build_finished_dashboard)

        self._submit_task(task_name, worker, self._btn_build)

    def _launch_refresh(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "Incremental Refresh"
        if task_name in self._running_tasks:
            return

        from ..workers.refresh_worker import RefreshWorker

        worker = RefreshWorker(self._db_path, concurrency=3)

        # Connect build_progress signal if available
        if hasattr(worker.signals, 'build_progress'):
            worker.signals.build_progress.connect(self._on_build_progress)

        # Show dashboard and hide on completion
        self._show_dashboard()
        worker.signals.finished.connect(self._on_build_finished_dashboard)

        self._submit_task(task_name, worker, self._btn_refresh)

    def _launch_checkoff_import(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "Checkoff Import"
        if task_name in self._running_tasks:
            return

        json_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Checkoff JSON file",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not json_path:
            return

        from ..workers.import_worker import CheckoffImportWorker

        worker = CheckoffImportWorker(self._db_path, json_path)
        self._submit_task(task_name, worker, self._btn_checkoff)

    def _launch_usb_import(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "USB Deliverables Import"
        if task_name in self._running_tasks:
            return

        csv_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select USB Deliverables CSV file",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not csv_path:
            return

        from ..workers.import_worker import USBDeliverablesImportWorker

        worker = USBDeliverablesImportWorker(self._db_path, csv_path)
        self._submit_task(task_name, worker, self._btn_usb)

    def _launch_oa_resolve(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "OA Resolution"
        if task_name in self._running_tasks:
            return

        from ..workers.base_worker import BaseWorker

        class OAResolveWorker(BaseWorker):
            """Resolve Open Access links for findings with DOIs."""

            def __init__(self, db_path: str):
                super().__init__()
                self._db_path = db_path

            def execute(self) -> dict[str, Any]:
                import asyncio
                from soyscope.config import get_settings
                from soyscope.db import Database

                self.emit_log("Resolving Open Access links...")
                settings = get_settings()
                db = Database(self._db_path)
                db.init_schema()

                email = None
                if settings.apis.get("unpaywall", {}).email:  # type: ignore[union-attr]
                    email = settings.apis["unpaywall"].email

                if not email:
                    self.emit_log("No Unpaywall email configured -- skipping OA resolution")
                    return {"resolved": 0}

                from soyscope.collectors.oa_resolver import OAResolver

                resolver = OAResolver(db=db, email=email)
                count = asyncio.run(resolver.resolve_all())

                self.emit_log(f"OA resolution complete: {count} DOIs resolved")
                return {"resolved": count}

        worker = OAResolveWorker(self._db_path)
        self._submit_task(task_name, worker, self._btn_oa)

    def _launch_enrichment(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "AI Enrichment"
        if task_name in self._running_tasks:
            return

        tier = self._tier_combo.currentData()
        limit = self._limit_spin.value()

        from ..workers.enrich_worker import EnrichmentWorker

        worker = EnrichmentWorker(self._db_path, tier=tier, limit=limit)
        self._submit_task(task_name, worker, self._btn_enrich)

    # =====================================================================
    # Task management
    # =====================================================================

    def _submit_task(
        self,
        name: str,
        worker: Any,
        button: QPushButton,
    ) -> None:
        """Submit a worker to the progress panel and wire up lifecycle signals."""
        self._running_tasks.add(name)
        button.setEnabled(False)

        # Connect lifecycle signals for button re-enable and data refresh
        worker.signals.finished.connect(lambda: self._on_task_finished(name, button))
        worker.signals.error.connect(
            lambda msg: self._on_task_error(name, button, msg)
        )
        worker.signals.result.connect(
            lambda _result: self._on_task_result(name)
        )

        self._progress_panel.submit_task(name, worker)

    @Slot()
    def _on_task_finished(self, name: str, button: QPushButton) -> None:
        """Re-enable the button and remove from running set."""
        self._running_tasks.discard(name)
        button.setEnabled(True)

    @Slot(str)
    def _on_task_error(self, name: str, button: QPushButton, message: str) -> None:
        """Handle task error: log it and re-enable button."""
        self._running_tasks.discard(name)
        button.setEnabled(True)
        logger.error("[%s] Error: %s", name, message)

    @Slot(object)
    def _on_task_result(self, name: str) -> None:
        """Emit data_changed so other tabs can refresh."""
        self._progress_panel.append_log(f"[{name}] Completed successfully")
        self.data_changed.emit()

    @Slot()
    def _on_build_finished_dashboard(self) -> None:
        """Update the dashboard to show completion state.

        The dashboard remains visible for 30 seconds after build finishes
        so the user can review final stats, then hides itself.
        """
        # Update the query counter to show completion
        self._query_counter_label.setText("Build Complete")
        self._query_counter_label.setStyleSheet("color: #27ae60;")
        self._build_progress_bar.setValue(1000)
        self._current_query_label.setText("Done")

        # Update final elapsed time
        if self._build_start_time is not None:
            elapsed = time.monotonic() - self._build_start_time
            self._stat_elapsed.setText(f"Elapsed: {_fmt_time(elapsed)}")
            self._stat_eta.setText("ETA: Done")
            self._stat_rate.setText("")

        # Auto-hide after 30 seconds
        QTimer.singleShot(30000, self._hide_dashboard)
