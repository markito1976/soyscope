from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class KPICard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("KPICard")
        self.setStyleSheet("""
            #KPICard {
                background: #2d2d3f;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.setMinimumSize(160, 90)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        self._title = QLabel(title)
        self._title.setFont(QFont("Segoe UI", 9))
        self._title.setStyleSheet("color: #a0a0b0;")
        self._value = QLabel("—")
        self._value.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self._value.setStyleSheet("color: #cdd6f4;")
        self._trend = QLabel("")
        self._trend.setFont(QFont("Segoe UI", 9))
        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addWidget(self._trend)

    def set_value(self, value: str, trend: str = "", trend_positive: bool = True):
        self._value.setText(value)
        if trend:
            color = "#27ae60" if trend_positive else "#e74c3c"
            arrow = "\u25b2" if trend_positive else "\u25bc"
            self._trend.setText(f"{arrow} {trend}")
            self._trend.setStyleSheet(f"color: {color};")
