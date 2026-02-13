"""Badge delegate for TRL levels and open-access status.

Draws a colored rounded-rectangle badge centered in the cell.
Text color (white or black) is auto-selected based on background
brightness using the W3C luminance formula.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from soyscope.gui.models.findings_model import ROLE_BADGE_COLOR


class BadgeDelegate(QStyledItemDelegate):
    """Renders a colored pill/badge for categorical values (TRL, OA status)."""

    PADDING_H = 8
    PADDING_V = 3
    RADIUS = 6

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        painter.save()

        # Draw selection background first
        if option.state & option.State_Selected:  # type: ignore[attr-defined]
            painter.fillRect(option.rect, option.palette.highlight())

        text = index.data(Qt.ItemDataRole.DisplayRole)
        bg_color: QColor | None = index.data(ROLE_BADGE_COLOR)

        if text and bg_color:
            font = QFont("Segoe UI", 8, QFont.Weight.Bold)
            painter.setFont(font)
            fm = QFontMetrics(font)
            text_rect = fm.boundingRect(str(text))

            # Centre badge in cell
            badge_w = text_rect.width() + self.PADDING_H * 2
            badge_h = text_rect.height() + self.PADDING_V * 2
            x = option.rect.center().x() - badge_w // 2
            y = option.rect.center().y() - badge_h // 2
            badge_rect = QRect(x, y, badge_w, badge_h)

            # Draw rounded-rect background
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(badge_rect, self.RADIUS, self.RADIUS)

            # Auto-pick white or black text based on brightness
            brightness = (
                bg_color.red() * 0.299
                + bg_color.green() * 0.587
                + bg_color.blue() * 0.114
            )
            text_color = (
                QColor(Qt.GlobalColor.black)
                if brightness > 150
                else QColor(Qt.GlobalColor.white)
            )
            painter.setPen(text_color)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, str(text))
        else:
            # Fallback to default rendering
            super().paint(painter, option, index)

        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        return QSize(80, 28)
