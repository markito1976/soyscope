import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QScrollArea,
    QFrame, QHBoxLayout, QSizePolicy, QPushButton, QTextEdit)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl


class _Section(QFrame):
    """Collapsible section with a header and content area."""

    def __init__(self, title: str, collapsible: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._collapsed = False
        self._collapsible = collapsible

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self._header = QLabel(title)
        self._header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._header.setStyleSheet("color: #89b4fa;")
        header_layout.addWidget(self._header)

        if collapsible:
            self._toggle_btn = QPushButton("\u25bc")
            self._toggle_btn.setFixedSize(20, 20)
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #89b4fa;
                    border: none;
                    font-size: 10pt;
                }
            """)
            self._toggle_btn.clicked.connect(self._toggle)
            header_layout.addWidget(self._toggle_btn)

        header_layout.addStretch()
        outer.addLayout(header_layout)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(2)
        outer.addWidget(self._content)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        self._toggle_btn.setText("\u25b6" if self._collapsed else "\u25bc")

    def add_widget(self, widget):
        self._content_layout.addWidget(widget)

    def clear(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class DetailPanel(QWidget):
    """Right-side detail panel for a selected finding."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(500)

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area wrapping all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)

        # Title
        self._title = QLabel("Select a finding")
        self._title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title.setStyleSheet("color: #cdd6f4;")
        self._title.setWordWrap(True)
        self._layout.addWidget(self._title)

        # Metadata grid section
        self._meta_section = _Section("Details")
        self._layout.addWidget(self._meta_section)

        # Metadata labels (created once, updated on selection)
        self._meta_labels: dict[str, QLabel] = {}
        for field in ["Year", "Venue", "DOI", "Authors", "Source", "Type",
                       "OA Status", "Citations"]:
            row = QHBoxLayout()
            key_label = QLabel(f"{field}:")
            key_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            key_label.setStyleSheet("color: #a0a0b0;")
            key_label.setFixedWidth(70)
            val_label = QLabel("\u2014")
            val_label.setFont(QFont("Segoe UI", 9))
            val_label.setStyleSheet("color: #cdd6f4;")
            val_label.setWordWrap(True)
            val_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.LinksAccessibleByMouse)
            val_label.setOpenExternalLinks(True)
            self._meta_labels[field] = val_label
            row.addWidget(key_label)
            row.addWidget(val_label, 1)
            container = QWidget()
            container.setLayout(row)
            self._meta_section.add_widget(container)

        # Abstract section
        self._abstract_section = _Section("Abstract")
        self._abstract_text = QLabel("")
        self._abstract_text.setFont(QFont("Segoe UI", 9))
        self._abstract_text.setStyleSheet("color: #cdd6f4;")
        self._abstract_text.setWordWrap(True)
        self._abstract_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._abstract_section.add_widget(self._abstract_text)
        self._layout.addWidget(self._abstract_section)

        # AI Summary section
        self._summary_section = _Section("AI Summary")
        self._summary_text = QLabel("")
        self._summary_text.setFont(QFont("Segoe UI", 9))
        self._summary_text.setStyleSheet("color: #b4befe;")
        self._summary_text.setWordWrap(True)
        self._summary_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._summary_section.add_widget(self._summary_text)
        self._layout.addWidget(self._summary_section)

        # Raw metadata section (collapsible)
        self._raw_section = _Section("Raw Metadata", collapsible=True)
        self._raw_text = QTextEdit()
        self._raw_text.setReadOnly(True)
        self._raw_text.setFont(QFont("Consolas", 8))
        self._raw_text.setMaximumHeight(250)
        self._raw_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e2e;
                color: #a6adc8;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        self._raw_section.add_widget(self._raw_text)
        self._layout.addWidget(self._raw_section)

        self._layout.addStretch()
        scroll.setWidget(self._container)
        outer_layout.addWidget(scroll)

    @Slot(dict)
    def show_finding(self, data: dict):
        """Populate the panel with finding data."""
        self._title.setText(data.get("title", "Untitled"))

        # Metadata fields
        self._meta_labels["Year"].setText(str(data.get("year", "\u2014")))
        self._meta_labels["Venue"].setText(data.get("venue", "\u2014") or "\u2014")

        doi = data.get("doi", "")
        if doi:
            url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
            self._meta_labels["DOI"].setText(
                f'<a href="{url}" style="color:#89b4fa;">{doi}</a>')
        else:
            self._meta_labels["DOI"].setText("\u2014")

        authors = data.get("authors", [])
        if isinstance(authors, list):
            authors_str = ", ".join(authors[:5])
            if len(authors) > 5:
                authors_str += f" (+{len(authors) - 5} more)"
        else:
            authors_str = str(authors) if authors else "\u2014"
        self._meta_labels["Authors"].setText(authors_str)

        self._meta_labels["Source"].setText(data.get("source", "\u2014") or "\u2014")
        self._meta_labels["Type"].setText(data.get("type", "\u2014") or "\u2014")
        self._meta_labels["OA Status"].setText(
            data.get("oa_status", "\u2014") or "\u2014")
        citations = data.get("citation_count")
        self._meta_labels["Citations"].setText(
            str(citations) if citations is not None else "\u2014")

        # Abstract
        abstract = data.get("abstract", "")
        if abstract:
            self._abstract_text.setText(abstract)
            self._abstract_section.setVisible(True)
        else:
            self._abstract_section.setVisible(False)

        # AI Summary
        summary = data.get("ai_summary", "") or data.get("summary", "")
        if summary:
            self._summary_text.setText(summary)
            self._summary_section.setVisible(True)
        else:
            self._summary_section.setVisible(False)

        # Raw metadata
        try:
            raw = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            raw = str(data)
        self._raw_text.setPlainText(raw)

    def clear_detail(self):
        """Reset the panel to empty state."""
        self._title.setText("Select a finding")
        for label in self._meta_labels.values():
            label.setText("\u2014")
        self._abstract_text.setText("")
        self._abstract_section.setVisible(False)
        self._summary_text.setText("")
        self._summary_section.setVisible(False)
        self._raw_text.clear()
