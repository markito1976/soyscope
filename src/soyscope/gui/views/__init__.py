"""SoyScope GUI view tabs for the main QTabWidget.

Each tab is a QWidget subclass with a ``refresh()`` or ``load_data()``
method that can be called when the underlying data changes.
"""

from .overview_tab import OverviewTab
from .explorer_tab import ExplorerTab
from .matrix_tab import MatrixTab
from .trends_tab import TrendsTab
from .novel_uses_tab import NovelUsesTab
from .run_history_tab import RunHistoryTab

__all__ = [
    "OverviewTab",
    "ExplorerTab",
    "MatrixTab",
    "TrendsTab",
    "NovelUsesTab",
    "RunHistoryTab",
]
