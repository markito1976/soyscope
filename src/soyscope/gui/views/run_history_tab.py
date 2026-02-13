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
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QSpinBox,
    QLabel,
    QFileDialog,
    QSizePolicy,
    QMessageBox,
    QPlainTextEdit,
)

from ..widgets.progress_panel import ProgressPanel

logger = logging.getLogger(__name__)


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
        self._submit_task(task_name, worker, self._btn_build)

    def _launch_refresh(self) -> None:
        if not self._ensure_db_path():
            return
        task_name = "Incremental Refresh"
        if task_name in self._running_tasks:
            return

        # Refresh uses the same HistoricalBuildWorker with max_queries capped
        from ..workers.build_worker import HistoricalBuildWorker

        worker = HistoricalBuildWorker(self._db_path, concurrency=3, max_queries=20)
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
