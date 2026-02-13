from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QComboBox,
    QSpinBox, QLabel, QPushButton)
from PySide6.QtCore import Signal, QTimer

class SearchBar(QWidget):
    text_changed = Signal(str)
    source_changed = Signal(str)
    type_changed = Signal(str)
    oa_changed = Signal(str)
    year_range_changed = Signal(int, int)
    filters_cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search text with debounce
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search titles, abstracts, DOIs...")
        self._search.setClearButtonEnabled(True)
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(lambda: self.text_changed.emit(self._search.text()))
        self._search.textChanged.connect(lambda: self._debounce.start())
        layout.addWidget(self._search, 2)

        # Source filter
        self._source = QComboBox()
        self._source.addItem("All Sources", "")
        self._source.setMinimumWidth(120)
        self._source.currentIndexChanged.connect(
            lambda: self.source_changed.emit(self._source.currentData()))
        layout.addWidget(self._source)

        # Type filter
        self._type = QComboBox()
        self._type.addItem("All Types", "")
        for t in ["paper", "patent", "conference", "report", "news"]:
            self._type.addItem(t.title(), t)
        self._type.setMinimumWidth(100)
        self._type.currentIndexChanged.connect(
            lambda: self.type_changed.emit(self._type.currentData()))
        layout.addWidget(self._type)

        # OA filter
        self._oa = QComboBox()
        self._oa.addItem("All OA", "")
        for oa in ["gold", "green", "hybrid", "bronze", "closed"]:
            self._oa.addItem(oa.title(), oa)
        self._oa.setMinimumWidth(90)
        self._oa.currentIndexChanged.connect(
            lambda: self.oa_changed.emit(self._oa.currentData()))
        layout.addWidget(self._oa)

        # Year range
        layout.addWidget(QLabel("Year:"))
        self._year_start = QSpinBox()
        self._year_start.setRange(1990, 2030)
        self._year_start.setValue(2000)
        self._year_start.valueChanged.connect(self._emit_year_range)
        layout.addWidget(self._year_start)
        layout.addWidget(QLabel("-"))
        self._year_end = QSpinBox()
        self._year_end.setRange(1990, 2030)
        self._year_end.setValue(2026)
        self._year_end.valueChanged.connect(self._emit_year_range)
        layout.addWidget(self._year_end)

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_all)
        layout.addWidget(clear_btn)

    def _emit_year_range(self):
        self.year_range_changed.emit(self._year_start.value(), self._year_end.value())

    def clear_all(self):
        self._search.clear()
        self._source.setCurrentIndex(0)
        self._type.setCurrentIndex(0)
        self._oa.setCurrentIndex(0)
        self._year_start.setValue(2000)
        self._year_end.setValue(2026)
        self.filters_cleared.emit()

    def populate_sources(self, sources: list[str]):
        self._source.clear()
        self._source.addItem("All Sources", "")
        for s in sorted(sources):
            self._source.addItem(s, s)
