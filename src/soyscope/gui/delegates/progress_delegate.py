"""Progress-bar delegate for novelty scores.

Draws a horizontal colored bar inside the cell representing a 0.0-1.0
value.  Bar color transitions: red (<0.33), amber (<0.66), green (>=0.66).
A percentage text overlay is drawn centered on the bar.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from soyscope.gui.models.findings_model import ROLE_PROGRESS_VALUE


class ProgressBarDelegate(QStyledItemDelegate):
    """In-cell progress bar for 0.0-1.0 float values (novelty scores)."""

    BAR_HEIGHT = 14
    MARGIN = 4

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()

        # Selection background
        if option.state & option.State_Selected:  # type: ignore[attr-defined]
            painter.fillRect(option.rect, option.palette.highlight())

        value = index.data(ROLE_PROGRESS_VALUE)
        text = index.data(Qt.ItemDataRole.DisplayRole)

        if value is not None:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = option.rect.adjusted(self.MARGIN, 0, -self.MARGIN, 0)

            # Bar background (dark track)
            bar_y = rect.center().y() - self.BAR_HEIGHT // 2
            bar_rect = QRect(rect.x(), bar_y, rect.width(), self.BAR_HEIGHT)
            painter.setBrush(QColor(60, 60, 60))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bar_rect, 4, 4)

            # Filled portion
            clamped = min(max(value, 0.0), 1.0)
            fill_width = int(bar_rect.width() * clamped)
            if fill_width > 0:
                fill_rect = QRect(
                    bar_rect.x(), bar_rect.y(), fill_width, self.BAR_HEIGHT
                )
                # Color based on value thresholds
                if value < 0.33:
                    color = QColor("#e74c3c")   # red
                elif value < 0.66:
                    color = QColor("#f39c12")   # amber
                else:
                    color = QColor("#27ae60")   # green
                painter.setBrush(color)
                painter.drawRoundedRect(fill_rect, 4, 4)

            # Text overlay
            if text:
                painter.setPen(QColor(Qt.GlobalColor.white))
                painter.drawText(
                    bar_rect, Qt.AlignmentFlag.AlignCenter, str(text)
                )
        else:
            super().paint(painter, option, index)

        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        return QSize(100, 28)
