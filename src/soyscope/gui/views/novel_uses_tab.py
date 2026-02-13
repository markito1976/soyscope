"""Novel Uses tab -- AI-enriched high-novelty findings.

Displays a table of findings sorted by novelty_score descending,
showing only enriched findings with novelty score, TRL badge, AI
summary, and soy advantage text.  Uses a lightweight internal model
rather than the full FindingsTableModel to keep things focused.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Slot,
)
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model for novel-use rows
# ---------------------------------------------------------------------------

class _NovelRow:
    """Minimal data container for one enriched finding."""

    __slots__ = (
        "finding_id", "title", "novelty_score", "trl", "ai_summary",
        "soy_advantage", "year", "source_api",
    )

    def __init__(
        self,
        finding_id: int,
        title: str,
        novelty_score: float,
        trl: int,
        ai_summary: str,
        soy_advantage: str,
        year: int | None,
        source_api: str,
    ):
        self.finding_id = finding_id
        self.title = title
        self.novelty_score = novelty_score
        self.trl = trl
        self.ai_summary = ai_summary
        self.soy_advantage = soy_advantage
        self.year = year
        self.source_api = source_api


_HEADERS = ["Title", "Novelty", "TRL", "Year", "Source", "AI Summary", "Soy Advantage"]

_COL_TITLE = 0
_COL_NOVELTY = 1
_COL_TRL = 2
_COL_YEAR = 3
_COL_SOURCE = 4
_COL_SUMMARY = 5
_COL_SOY_ADV = 6


class _NovelUsesModel(QAbstractTableModel):
    """Simple table model for enriched findings sorted by novelty."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[_NovelRow] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        r = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == _COL_TITLE:
                return r.title
            if col == _COL_NOVELTY:
                return f"{r.novelty_score:.0%}"
            if col == _COL_TRL:
                return f"TRL {r.trl}" if r.trl else ""
            if col == _COL_YEAR:
                return str(r.year) if r.year else ""
            if col == _COL_SOURCE:
                return r.source_api
            if col == _COL_SUMMARY:
                return r.ai_summary
            if col == _COL_SOY_ADV:
                return r.soy_advantage
            return ""

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == _COL_TITLE:
                return r.ai_summary or r.title
            if col == _COL_SUMMARY:
                return r.ai_summary
            if col == _COL_SOY_ADV:
                return r.soy_advantage
            return None

        # For sorting
        if role == Qt.ItemDataRole.UserRole:
            if col == _COL_NOVELTY:
                return r.novelty_score
            if col == _COL_TRL:
                return r.trl
            if col == _COL_YEAR:
                return r.year or 0
            return None

        # Background for novelty column (gradient green)
        if role == Qt.ItemDataRole.BackgroundRole and col == _COL_NOVELTY:
            # Green intensity proportional to novelty
            intensity = int(r.novelty_score * 200)
            return QColor(0, intensity, 0, 80)

        # TRL badge color
        if role == Qt.ItemDataRole.BackgroundRole and col == _COL_TRL:
            if 1 <= r.trl <= 3:
                return QColor("#e74c3c")
            if 4 <= r.trl <= 6:
                return QColor("#f39c12")
            if 7 <= r.trl <= 9:
                return QColor("#27ae60")
            return None

        if role == Qt.ItemDataRole.ForegroundRole and col == _COL_TRL:
            if r.trl >= 1:
                return QColor("white")
            return None

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (_COL_NOVELTY, _COL_TRL, _COL_YEAR):
                return Qt.AlignmentFlag.AlignCenter
            return None

        return None

    def flags(self, index):
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def load_data(self, rows: list[_NovelRow]) -> None:
        self.beginResetModel()
        self._data = rows
        self.endResetModel()


# ---------------------------------------------------------------------------
# Novelty progress-bar delegate
# ---------------------------------------------------------------------------

class _NoveltyBarDelegate(QStyledItemDelegate):
    """Renders a progress bar for the novelty score column."""

    def paint(self, painter, option: QStyleOptionViewItem, index: QModelIndex):
        painter.save()

        # Selection highlight
        if option.state & option.State_Selected:  # type: ignore[attr-defined]
            painter.fillRect(option.rect, option.palette.highlight())

        raw = index.data(Qt.ItemDataRole.UserRole)
        if raw is not None and isinstance(raw, (int, float)):
            score = max(0.0, min(1.0, float(raw)))
            rect = option.rect.adjusted(4, 4, -4, -4)

            # Background track
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2d2d3f"))
            painter.drawRoundedRect(rect, 3, 3)

            # Filled portion
            fill_width = int(rect.width() * score)
            fill_rect = rect.adjusted(0, 0, -(rect.width() - fill_width), 0)

            # Color from red (low) to green (high)
            r_val = int(255 * (1 - score))
            g_val = int(255 * score)
            painter.setBrush(QColor(r_val, g_val, 80, 200))
            painter.drawRoundedRect(fill_rect, 3, 3)

            # Text overlay
            text = f"{score:.0%}"
            painter.setPen(QColor("#cdd6f4"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        else:
            super().paint(painter, option, index)

        painter.restore()


# ---------------------------------------------------------------------------
# The tab widget
# ---------------------------------------------------------------------------

class NovelUsesTab(QWidget):
    """Table of AI-enriched high-novelty findings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._db_path: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        header = QLabel("Novel Industrial Soy Uses")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        root.addWidget(header)

        subtitle = QLabel(
            "AI-enriched findings ranked by novelty score.  "
            "Only findings with enrichment data are shown."
        )
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #a0a0b0;")
        root.addWidget(subtitle)

        # Table
        self._model = _NovelUsesModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self._proxy.setDynamicSortFilter(True)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.sortByColumn(_COL_NOVELTY, Qt.SortOrder.DescendingOrder)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setDefaultSectionSize(32)
        self._table.verticalHeader().hide()

        # Column sizing
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(_COL_TITLE, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(_COL_NOVELTY, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(_COL_NOVELTY, 100)
        hdr.setSectionResizeMode(_COL_TRL, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_YEAR, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_SOURCE, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(_COL_SUMMARY, QHeaderView.ResizeMode.Interactive)
        hdr.resizeSection(_COL_SUMMARY, 300)

        # Custom delegate for novelty bar
        self._bar_delegate = _NoveltyBarDelegate(self._table)
        self._table.setItemDelegateForColumn(_COL_NOVELTY, self._bar_delegate)

        root.addWidget(self._table, 1)

        # Status
        self._status = QLabel("No enriched findings loaded")
        self._status.setFont(QFont("Segoe UI", 9))
        self._status.setStyleSheet("color: #a0a0b0;")
        root.addWidget(self._status)

    # -- Public API ----------------------------------------------------------

    def load_data(self, db_path: str) -> None:
        """Load enriched findings from the database on a background thread."""
        self._db_path = db_path

        wrapper = _EnrichedFindingsWorker(db_path)
        wrapper.signals.result.connect(self._on_data_loaded)
        wrapper.signals.error.connect(
            lambda msg: logger.error("EnrichedFindingsWorker error: %s", msg)
        )
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(wrapper._worker)

    def refresh(self, stats: dict | None = None) -> None:
        """Reload data.  If db_path is set, trigger a fresh load."""
        if self._db_path:
            self.load_data(self._db_path)

    # -- Private slots -------------------------------------------------------

    @Slot(object)
    def _on_data_loaded(self, result: dict) -> None:
        rows_data = result.get("enriched_findings", [])
        rows: list[_NovelRow] = []
        for d in rows_data:
            rows.append(
                _NovelRow(
                    finding_id=d.get("id", 0),
                    title=d.get("title", ""),
                    novelty_score=d.get("novelty_score", 0.0) or 0.0,
                    trl=d.get("trl_estimate", 0) or 0,
                    ai_summary=d.get("ai_summary", "") or "",
                    soy_advantage=d.get("soy_advantage", "") or "",
                    year=d.get("year"),
                    source_api=d.get("source_api", "") or "",
                )
            )

        # Sort by novelty descending before loading
        rows.sort(key=lambda r: r.novelty_score, reverse=True)
        self._model.load_data(rows)
        self._status.setText(f"Showing {len(rows)} enriched findings")


# ---------------------------------------------------------------------------
# Dedicated worker for enriched findings
# ---------------------------------------------------------------------------

class _EnrichedFindingsWorker:
    """Lightweight worker that queries enriched findings.

    Uses the BaseWorker pattern but as a standalone class to avoid
    circular imports.
    """

    def __init__(self, db_path: str):
        from ..workers.base_worker import BaseWorker

        class _Worker(BaseWorker):
            def __init__(self, path: str):
                super().__init__()
                self._path = path

            def execute(self) -> dict[str, Any]:
                from soyscope.db import Database

                db = Database(self._path)
                db.init_schema()

                with db.connect() as conn:
                    rows = conn.execute(
                        """SELECT f.id, f.title, f.year, f.source_api,
                                  e.novelty_score, e.trl_estimate,
                                  e.ai_summary, e.soy_advantage
                           FROM findings f
                           JOIN enrichments e ON f.id = e.finding_id
                           WHERE e.novelty_score IS NOT NULL
                           ORDER BY e.novelty_score DESC
                           LIMIT 500"""
                    ).fetchall()
                    enriched = [dict(r) for r in rows]

                return {"enriched_findings": enriched}

        self._worker = _Worker(db_path)

    @property
    def signals(self):
        return self._worker.signals

    def __getattr__(self, name):
        return getattr(self._worker, name)
