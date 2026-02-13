"""Hyperlink delegate for DOI columns.

Renders text as blue underlined link.  Clicking the cell opens the URL
in the system default browser via QDesktopServices.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from soyscope.gui.models.findings_model import ROLE_LINK_URL


class LinkDelegate(QStyledItemDelegate):
    """Draws blue underlined text for DOI/URL cells and opens on click."""

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

        text = index.data(Qt.ItemDataRole.DisplayRole)
        url = index.data(ROLE_LINK_URL)

        if text and url:
            font = QFont(option.font)
            font.setUnderline(True)
            painter.setFont(font)
            painter.setPen(QColor("#3498db"))
            text_rect = option.rect.adjusted(4, 0, -4, 0)
            elided = painter.fontMetrics().elidedText(
                str(text), Qt.TextElideMode.ElideRight, text_rect.width()
            )
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided,
            )
        else:
            super().paint(painter, option, index)

        painter.restore()

    def editorEvent(self, event, model, option, index) -> bool:
        if event.type() == QEvent.Type.MouseButtonRelease:
            url = index.data(ROLE_LINK_URL)
            if url:
                QDesktopServices.openUrl(QUrl(url))
                return True
        return False
