"""Matrix tab -- Sector x Derivative heatmap.

Wraps the existing HeatmapWidget (matplotlib-based) and provides:
- ``refresh(stats)`` to rebuild the matrix from the
  ``sector_derivative_matrix`` list inside the stats dict.
- Click-to-filter: clicking a cell emits a signal that the main
  window can use to switch to the Explorer tab with sector+derivative
  filters pre-applied.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

try:
    from ..widgets.heatmap_widget import HeatmapWidget

    HAS_HEATMAP = True
except ImportError:
    HAS_HEATMAP = False


class MatrixTab(QWidget):
    """Sector x Derivative heatmap with click-to-filter support.

    Signals:
        cell_filter_requested(sector, derivative):
            Emitted when the user clicks a heatmap cell.  The main
            window should switch to the Explorer tab and apply the
            appropriate filter.
    """

    cell_filter_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        header = QLabel("Sector / Derivative Matrix")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        root.addWidget(header)

        subtitle = QLabel(
            "Click a cell to filter the Explorer tab by that sector and derivative."
        )
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: #a0a0b0;")
        root.addWidget(subtitle)

        if HAS_HEATMAP:
            self._heatmap = HeatmapWidget()
            self._heatmap.cell_clicked.connect(self._on_cell_clicked)
            root.addWidget(self._heatmap, 1)
        else:
            placeholder = QLabel("HeatmapWidget requires matplotlib + numpy")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color: #a0a0b0; font-size: 12pt;")
            root.addWidget(placeholder, 1)
            self._heatmap = None

    # -- Public API ----------------------------------------------------------

    def refresh(self, stats: dict) -> None:
        """Rebuild the heatmap from *stats['sector_derivative_matrix']*.

        The matrix data is a list of dicts with keys:
        ``sector``, ``derivative``, ``count``.
        """
        if self._heatmap is None:
            return

        raw = stats.get("sector_derivative_matrix", [])
        if not raw:
            self._heatmap.update_heatmap([], [], [])
            return

        # Build the matrix structure expected by HeatmapWidget
        sectors_set: set[str] = set()
        derivatives_set: set[str] = set()
        counts: dict[tuple[str, str], int] = {}

        for entry in raw:
            s = entry.get("sector", "")
            d = entry.get("derivative", "")
            c = entry.get("count", 0)
            if s and d:
                sectors_set.add(s)
                derivatives_set.add(d)
                counts[(s, d)] = c

        sectors = sorted(sectors_set)
        derivatives = sorted(derivatives_set)

        # Build 2-D list[list[int]]
        matrix: list[list[int]] = []
        for s in sectors:
            row = [counts.get((s, d), 0) for d in derivatives]
            matrix.append(row)

        self._heatmap.update_heatmap(matrix, sectors, derivatives)

    # -- Private slots -------------------------------------------------------

    def _on_cell_clicked(self, sector: str, derivative: str) -> None:
        """Forward the heatmap cell click as a filter request."""
        logger.debug("Matrix cell clicked: sector=%s, derivative=%s", sector, derivative)
        self.cell_filter_requested.emit(sector, derivative)
