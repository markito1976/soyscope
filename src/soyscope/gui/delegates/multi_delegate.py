"""Column-aware delegate dispatcher for the findings table.

Routes paint/sizeHint/editorEvent calls to the appropriate
column-specific delegate:

- TRL and OA_STATUS columns  -> BadgeDelegate
- DOI column                 -> LinkDelegate
- NOVELTY column             -> ProgressBarDelegate
- All other columns          -> default QStyledItemDelegate rendering
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from soyscope.gui.delegates.badge_delegate import BadgeDelegate
from soyscope.gui.delegates.link_delegate import LinkDelegate
from soyscope.gui.delegates.progress_delegate import ProgressBarDelegate
from soyscope.gui.models.findings_model import Col


class MultiColumnDelegate(QStyledItemDelegate):
    """Routes painting to column-specific delegates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._badge = BadgeDelegate(parent)
        self._link = LinkDelegate(parent)
        self._progress = ProgressBarDelegate(parent)

    def _delegate_for(self, index: QModelIndex) -> QStyledItemDelegate:
        """Return the delegate responsible for *index*'s column."""
        col = index.column()
        if col in (Col.TRL, Col.OA_STATUS):
            return self._badge
        if col == Col.DOI:
            return self._link
        if col == Col.NOVELTY:
            return self._progress
        return self  # default rendering

    def paint(self, painter, option, index):
        delegate = self._delegate_for(index)
        if delegate is self:
            super().paint(painter, option, index)
        else:
            delegate.paint(painter, option, index)

    def sizeHint(self, option, index):
        delegate = self._delegate_for(index)
        if delegate is self:
            return super().sizeHint(option, index)
        return delegate.sizeHint(option, index)

    def editorEvent(self, event, model, option, index):
        delegate = self._delegate_for(index)
        if delegate is self:
            return super().editorEvent(event, model, option, index)
        return delegate.editorEvent(event, model, option, index)
