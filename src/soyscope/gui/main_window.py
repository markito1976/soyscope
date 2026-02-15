"""SoyScope Main Window — PySide6 desktop application."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QStatusBar,
    QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut

from soyscope.config import get_settings
from soyscope.db import Database

from .workers.stats_worker import StatsWorker
from .workers.data_worker import FindingsLoadWorker


class SoyScopeMainWindow(QMainWindow):
    """Main application window with tabbed interface."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SoyScope — Industrial Soy Research Dashboard")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # Core state
        self._settings = get_settings()
        self._db_path = self._settings.db_path
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(4)

        # Initialize DB schema
        db = Database(self._db_path)
        db.init_schema()

        # Build UI
        self._build_menu_bar()
        self._build_tabs()
        self._build_status_bar()
        self._setup_shortcuts()

        # Load theme
        self._apply_theme("dark")

        # Initial data load
        QTimer.singleShot(100, self._refresh_all)

    # ── UI Construction ──

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        import_csv_action = QAction("Import USB Deliverables CSV...", self)
        import_csv_action.setShortcut(QKeySequence("Ctrl+I"))
        import_csv_action.triggered.connect(self._import_usb_csv_dialog)
        file_menu.addAction(import_csv_action)

        import_checkoff_action = QAction("Import Checkoff JSON...", self)
        import_checkoff_action.triggered.connect(self._import_checkoff_dialog)
        file_menu.addAction(import_checkoff_action)

        file_menu.addSeparator()

        export_excel_action = QAction("Export to Excel...", self)
        export_excel_action.setShortcut(QKeySequence("Ctrl+E"))
        export_excel_action.triggered.connect(self._export_excel)
        file_menu.addAction(export_excel_action)

        export_word_action = QAction("Export to Word...", self)
        export_word_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_word_action.triggered.connect(self._export_word)
        file_menu.addAction(export_word_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menu_bar.addMenu("&View")

        refresh_action = QAction("Refresh Data", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._refresh_all)
        view_menu.addAction(refresh_action)

        view_menu.addSeparator()

        dark_action = QAction("Dark Theme", self)
        dark_action.triggered.connect(lambda: self._apply_theme("dark"))
        view_menu.addAction(dark_action)

        light_action = QAction("Light Theme", self)
        light_action.triggered.connect(lambda: self._apply_theme("light"))
        view_menu.addAction(light_action)

        # Tasks menu
        tasks_menu = menu_bar.addMenu("&Tasks")

        build_action = QAction("Historical Build...", self)
        build_action.triggered.connect(self._launch_build)
        tasks_menu.addAction(build_action)

        enrich_action = QAction("Run AI Enrichment...", self)
        enrich_action.triggered.connect(self._launch_enrichment)
        tasks_menu.addAction(enrich_action)

        oa_action = QAction("Resolve OA Links...", self)
        oa_action.triggered.connect(self._launch_oa_resolution)
        tasks_menu.addAction(oa_action)

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        about_action = QAction("About SoyScope", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_tabs(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setFont(QFont("Segoe UI Variable", 10))
        self.setCentralWidget(self._tabs)

        from .views.overview_tab import OverviewTab
        from .views.explorer_tab import ExplorerTab
        from .views.matrix_tab import MatrixTab
        from .views.trends_tab import TrendsTab
        from .views.novel_uses_tab import NovelUsesTab
        from .views.run_history_tab import RunHistoryTab

        # Tabs take parent=None or (db_path) — match their actual constructors
        self._overview = OverviewTab()
        self._explorer = ExplorerTab()
        self._matrix = MatrixTab()
        self._trends = TrendsTab()
        self._novel = NovelUsesTab()
        self._run_history = RunHistoryTab(db_path=str(self._db_path))

        self._tabs.addTab(self._overview, "Overview")
        self._tabs.addTab(self._explorer, "Explorer")
        self._tabs.addTab(self._matrix, "Matrix")
        self._tabs.addTab(self._trends, "Trends")
        self._tabs.addTab(self._novel, "Novel Uses")
        self._tabs.addTab(self._run_history, "Run History")

        # When run_history completes a task, refresh data
        self._run_history.data_changed.connect(self._refresh_all)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._tabs.setCurrentIndex(0))
        QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._tabs.setCurrentIndex(1))
        QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self._tabs.setCurrentIndex(2))
        QShortcut(QKeySequence("Ctrl+4"), self, activated=lambda: self._tabs.setCurrentIndex(3))
        QShortcut(QKeySequence("Ctrl+5"), self, activated=lambda: self._tabs.setCurrentIndex(4))
        QShortcut(QKeySequence("Ctrl+6"), self, activated=lambda: self._tabs.setCurrentIndex(5))

    # ── Data Loading ──

    def _refresh_all(self) -> None:
        self._status.showMessage("Refreshing data...")
        db_path = str(self._db_path)

        # Load stats for overview, matrix, trends
        stats_worker = StatsWorker(db_path)
        stats_worker.signals.result.connect(self._on_stats_loaded)
        stats_worker.signals.error.connect(lambda e: self._status.showMessage(f"Error: {e[:80]}"))
        self._pool.start(stats_worker)

        # Load findings for explorer table
        self._explorer.load_data(db_path)

        # Load enriched findings for novel uses
        self._novel.load_data(db_path)

    def _on_stats_loaded(self, stats: object) -> None:
        if not isinstance(stats, dict):
            return
        self._overview.refresh(stats)
        self._matrix.refresh(stats)
        self._trends.refresh(stats)
        total = stats.get("total_findings", 0)
        self._status.showMessage(f"Loaded — {total:,} findings in database")

    # ── Actions ──

    def _import_usb_csv_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select USB Deliverables CSV", "", "CSV Files (*.csv)")
        if path:
            self._run_history.launch_usb_import(path)
            self._tabs.setCurrentWidget(self._run_history)

    def _import_checkoff_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Checkoff JSON", "", "JSON Files (*.json)")
        if path:
            self._run_history.launch_checkoff_import(path)
            self._tabs.setCurrentWidget(self._run_history)

    def _launch_build(self) -> None:
        self._run_history.launch_historical_build()
        self._tabs.setCurrentWidget(self._run_history)

    def _launch_enrichment(self) -> None:
        self._run_history.launch_enrichment()
        self._tabs.setCurrentWidget(self._run_history)

    def _launch_oa_resolution(self) -> None:
        self._run_history.launch_oa_resolution()
        self._tabs.setCurrentWidget(self._run_history)

    def _export_excel(self) -> None:
        from .workers.base_worker import BaseWorker

        class ExcelWorker(BaseWorker):
            def __init__(self, db_path):
                super().__init__()
                self._db_path = db_path

            def execute(self):
                from soyscope.db import Database as DB
                from soyscope.config import get_settings as gs
                from soyscope.outputs.excel_export import ExcelExporter
                s = gs()
                db = DB(self._db_path)
                db.init_schema()
                exporter = ExcelExporter(db=db, output_dir=s.exports_dir)
                return exporter.export()

        worker = ExcelWorker(str(self._db_path))
        worker.signals.result.connect(
            lambda path: QMessageBox.information(self, "Export", f"Excel saved to:\n{path}"))
        worker.signals.error.connect(
            lambda e: QMessageBox.warning(self, "Export Error", str(e)[:500]))
        self._pool.start(worker)
        self._status.showMessage("Exporting to Excel...")

    def _export_word(self) -> None:
        from .workers.base_worker import BaseWorker

        class WordWorker(BaseWorker):
            def __init__(self, db_path):
                super().__init__()
                self._db_path = db_path

            def execute(self):
                from soyscope.db import Database as DB
                from soyscope.config import get_settings as gs
                from soyscope.outputs.word_export import WordExporter
                s = gs()
                db = DB(self._db_path)
                db.init_schema()
                exporter = WordExporter(db=db, output_dir=s.exports_dir)
                return exporter.export()

        worker = WordWorker(str(self._db_path))
        worker.signals.result.connect(
            lambda path: QMessageBox.information(self, "Export", f"Word saved to:\n{path}"))
        worker.signals.error.connect(
            lambda e: QMessageBox.warning(self, "Export Error", str(e)[:500]))
        self._pool.start(worker)
        self._status.showMessage("Exporting to Word...")

    def _focus_search(self) -> None:
        self._tabs.setCurrentWidget(self._explorer)

    def _apply_theme(self, theme: str) -> None:
        theme_path = Path(__file__).parent / "resources" / "themes" / f"{theme}.qss"
        if theme_path.exists():
            QApplication.instance().setStyleSheet(theme_path.read_text())

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About SoyScope",
            "SoyScope — Industrial Soy Research Dashboard\n\n"
            "Builds and maintains a comprehensive database of\n"
            "industrial uses of soy over the past 25 years.\n\n"
            "14 search APIs + Claude AI enrichment\n"
            "SQLite + Excel + Word + PySide6 GUI\n\n"
            "United Soybean Board",
        )


def launch_gui() -> int:
    """Launch the SoyScope GUI application."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SoyScope")
    app.setOrganizationName("UnitedSoybeanBoard")
    app.setFont(QFont("Segoe UI Variable", 10))

    window = SoyScopeMainWindow()
    window.show()
    return app.exec()
