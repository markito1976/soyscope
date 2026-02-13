"""Explorer tab -- main data table with filters and detail panel.

Top:    SearchBar for multi-column filtering.
Middle: QSplitter with QTableView (70 %) and DetailPanel (30 %).
Bottom: Status label showing "Showing X of Y findings".

The table uses FindingsTableModel + FindingsFilterProxy + MultiColumnDelegate.
Row selection updates the detail panel.  A context menu offers View Details,
Copy to Clipboard, Open DOI, and Export Selection.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, Qt, Slot
from PySide6.QtGui import QAction, QClipboard, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QSizePolicy,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ..models.filter_proxy import FindingsFilterProxy
from ..models.findings_model import (
    Col,
    FindingRow,
    FindingsTableModel,
    ROLE_FINDING,
    ROLE_LINK_URL,
)
from ..delegates.multi_delegate import MultiColumnDelegate
from ..widgets.detail_panel import DetailPanel
from ..widgets.search_bar import SearchBar
from ..workers.data_worker import FindingsLoadWorker

logger = logging.getLogger(__name__)


class ExplorerTab(QWidget):
    """Filterable findings table with detail panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._db_path: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # -- Search bar ------------------------------------------------------
        self._search_bar = SearchBar()
        root.addWidget(self._search_bar)

        # -- Model chain -----------------------------------------------------
        self._model = FindingsTableModel(self)
        self._proxy = FindingsFilterProxy(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setDynamicSortFilter(True)

        # -- Splitter: table + detail ----------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Table view
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setItemDelegate(MultiColumnDelegate(self._table))
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(Col.YEAR, Qt.SortOrder.DescendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.verticalHeader().hide()
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # Column widths
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(Col.ID, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(Col.TITLE, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(Col.YEAR, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(Col.DOI, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(Col.DOI, 160)
        hdr.setSectionResizeMode(Col.SOURCES, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(Col.SOURCES, 160)

        splitter.addWidget(self._table)

        # Detail panel
        self._detail = DetailPanel()
        splitter.addWidget(self._detail)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        root.addWidget(splitter, 1)

        # -- Status bar ------------------------------------------------------
        self._status = QLabel("No data loaded")
        self._status.setFont(QFont("Segoe UI", 9))
        self._status.setStyleSheet("color: #a0a0b0;")
        root.addWidget(self._status)

        # -- Signal wiring ---------------------------------------------------
        self._connect_signals()

    # =====================================================================
    # Signal wiring
    # =====================================================================

    def _connect_signals(self) -> None:
        # Search bar -> proxy
        self._search_bar.text_changed.connect(self._proxy.set_text_filter)
        self._search_bar.source_changed.connect(self._proxy.set_source_filter)
        self._search_bar.type_changed.connect(self._proxy.set_type_filter)
        self._search_bar.oa_changed.connect(self._proxy.set_oa_filter)
        self._search_bar.year_range_changed.connect(self._proxy.set_year_range)
        self._search_bar.filters_cleared.connect(self._proxy.clear_all_filters)

        # Table selection -> detail
        sel = self._table.selectionModel()
        sel.currentRowChanged.connect(self._on_row_changed)

        # Proxy row count change -> status update
        self._proxy.rowsInserted.connect(self._update_status)
        self._proxy.rowsRemoved.connect(self._update_status)
        self._proxy.modelReset.connect(self._update_status)
        self._proxy.layoutChanged.connect(self._update_status)

        # Context menu
        self._table.customContextMenuRequested.connect(self._show_context_menu)

    # =====================================================================
    # Public API
    # =====================================================================

    def load_data(self, db_path: str) -> None:
        """Start an async load of findings from *db_path*."""
        self._db_path = db_path
        worker = FindingsLoadWorker(db_path, limit=0)
        worker.signals.result.connect(self._on_findings_loaded)
        worker.signals.error.connect(
            lambda msg: logger.error("FindingsLoadWorker error: %s", msg)
        )
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(worker)

    def apply_source_filter(self, source: str) -> None:
        """Programmatically apply a source filter (used by other tabs)."""
        self._proxy.set_source_filter(source)

    def apply_text_filter(self, text: str) -> None:
        """Programmatically apply a text filter (used by other tabs)."""
        self._proxy.set_text_filter(text)

    def get_model(self) -> FindingsTableModel:
        """Return the underlying table model."""
        return self._model

    def get_proxy(self) -> FindingsFilterProxy:
        """Return the proxy model."""
        return self._proxy

    # =====================================================================
    # Private slots
    # =====================================================================

    @Slot(object)
    def _on_findings_loaded(self, result: dict) -> None:
        """Receive findings from the background worker."""
        findings_raw = result.get("findings", [])
        sources_map = result.get("sources_map", {})
        rows = [self._dict_to_row(f, sources_map) for f in findings_raw]
        self._model.load_data(rows)

        # Populate source combo in search bar
        sources = sorted({r.source_api for r in rows if r.source_api})
        self._search_bar.populate_sources(list(sources))

        self._update_status()

    @Slot(QModelIndex, QModelIndex)
    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self._detail.clear_detail()
            return

        # Map proxy index back to source model row
        source_idx = self._proxy.mapToSource(current)
        finding: FindingRow | None = self._model.get_finding(source_idx.row())
        if finding is None:
            self._detail.clear_detail()
            return

        data = self._finding_to_detail_dict(finding)
        self._detail.show_finding(data)

    @Slot()
    def _update_status(self) -> None:
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        self._status.setText(f"Showing {visible:,} of {total:,} findings")

    @Slot()
    def _show_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self._table)

        act_details = QAction("View Details", menu)
        act_details.triggered.connect(lambda: self._view_details(index))
        menu.addAction(act_details)

        act_copy = QAction("Copy to Clipboard", menu)
        act_copy.triggered.connect(lambda: self._copy_selection())
        menu.addAction(act_copy)

        # DOI link
        source_idx = self._proxy.mapToSource(index)
        finding = self._model.get_finding(source_idx.row())
        if finding and finding.doi:
            act_doi = QAction("Open DOI", menu)
            url = (
                finding.doi
                if finding.doi.startswith("http")
                else f"https://doi.org/{finding.doi}"
            )
            act_doi.triggered.connect(
                lambda: QDesktopServices.openUrl(__import__("PySide6").QtCore.QUrl(url))
            )
            menu.addAction(act_doi)

        menu.addSeparator()

        act_export = QAction("Export Selection...", menu)
        act_export.triggered.connect(self._export_selection)
        menu.addAction(act_export)

        menu.popup(self._table.viewport().mapToGlobal(pos))

    # =====================================================================
    # Context menu actions
    # =====================================================================

    def _view_details(self, proxy_index: QModelIndex) -> None:
        source_idx = self._proxy.mapToSource(proxy_index)
        finding = self._model.get_finding(source_idx.row())
        if finding:
            self._detail.show_finding(self._finding_to_detail_dict(finding))

    def _copy_selection(self) -> None:
        rows = set()
        for idx in self._table.selectionModel().selectedIndexes():
            source_idx = self._proxy.mapToSource(idx)
            rows.add(source_idx.row())

        lines: list[str] = []
        for row in sorted(rows):
            finding = self._model.get_finding(row)
            if finding:
                lines.append(
                    f"{finding.title}\t{finding.year}\t{finding.doi}\t"
                    f"{finding.source_api}\t{finding.venue}"
                )

        if lines:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText("\n".join(lines))

    def _export_selection(self) -> None:
        rows = set()
        for idx in self._table.selectionModel().selectedIndexes():
            source_idx = self._proxy.mapToSource(idx)
            rows.add(source_idx.row())

        if not rows:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Selection", "", "JSON Files (*.json);;CSV Files (*.csv)"
        )
        if not path:
            return

        findings_dicts = []
        for row in sorted(rows):
            finding = self._model.get_finding(row)
            if finding:
                findings_dicts.append(self._finding_to_detail_dict(finding))

        if path.endswith(".json"):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(findings_dicts, f, indent=2, ensure_ascii=False)
        elif path.endswith(".csv"):
            import csv

            fieldnames = [
                "id", "title", "year", "doi", "venue", "source",
                "type", "citation_count", "oa_status", "trl", "novelty_score",
            ]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(findings_dicts)

    # =====================================================================
    # Helpers
    # =====================================================================

    @staticmethod
    def _dict_to_row(d: dict[str, Any], sources_map: dict[int, list[str]] | None = None) -> FindingRow:
        """Convert a DB dict to a FindingRow dataclass."""
        fid = d.get("id", 0)
        sources_list = (sources_map or {}).get(fid, [])
        sources_str = ", ".join(sources_list) if sources_list else ""

        return FindingRow(
            id=fid,
            title=d.get("title", ""),
            year=d.get("year"),
            doi=d.get("doi", "") or "",
            url=d.get("url", "") or "",
            pdf_url=d.get("pdf_url", "") or "",
            authors=d.get("authors", "") or "",
            venue=d.get("venue", "") or "",
            source_api=d.get("source_api", "") or "",
            source_type=d.get("source_type", "") or "",
            citation_count=d.get("citation_count"),
            open_access_status=d.get("open_access_status", "") or "",
            trl=d.get("trl", 0) or 0,
            novelty_score=d.get("novelty_score", 0.0) or 0.0,
            abstract=d.get("abstract", "") or "",
            sources=sources_str,
        )

    @staticmethod
    def _finding_to_detail_dict(f: FindingRow) -> dict[str, Any]:
        """Convert a FindingRow into the dict format expected by DetailPanel."""
        authors = f.authors
        if isinstance(authors, str) and authors.startswith("["):
            try:
                authors = json.loads(authors)
            except (json.JSONDecodeError, ValueError):
                pass

        return {
            "id": f.id,
            "title": f.title,
            "year": f.year,
            "doi": f.doi,
            "venue": f.venue,
            "source": f.source_api,
            "type": f.source_type,
            "citation_count": f.citation_count,
            "oa_status": f.open_access_status,
            "trl": f.trl,
            "novelty_score": f.novelty_score,
            "abstract": f.abstract,
            "authors": authors,
            "url": f.url,
            "pdf_url": f.pdf_url,
        }
