from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QProgressBar, QPushButton, QPlainTextEdit, QScrollArea)
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool, QRunnable, QObject
from PySide6.QtGui import QFont, QTextCursor
from datetime import datetime


class TaskEntry(QFrame):
    """One row per running task with name, progress bar, status, and cancel button."""

    cancel_requested = Signal(str)  # task name

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("TaskEntry")
        self.setStyleSheet("""
            #TaskEntry {
                background: #2d2d3f;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._name_label = QLabel(name)
        self._name_label.setFont(QFont("Segoe UI", 9))
        self._name_label.setStyleSheet("color: #cdd6f4;")
        self._name_label.setMinimumWidth(120)
        layout.addWidget(self._name_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setMinimumWidth(150)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 3px;
                text-align: center;
                color: #cdd6f4;
                height: 18px;
            }
            QProgressBar::chunk {
                background: #89b4fa;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self._progress, 1)

        self._status = QLabel("Pending")
        self._status.setFont(QFont("Segoe UI", 8))
        self._status.setStyleSheet("color: #a0a0b0;")
        self._status.setMinimumWidth(80)
        layout.addWidget(self._status)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedWidth(60)
        self._cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background: #c0392b; }
            QPushButton:disabled { background: #555; }
        """)
        self._cancel_btn.clicked.connect(lambda: self.cancel_requested.emit(self.name))
        layout.addWidget(self._cancel_btn)

    @Slot(int)
    def set_progress(self, value: int):
        self._progress.setValue(value)

    @Slot(str)
    def set_status(self, status: str):
        self._status.setText(status)
        if status == "Done":
            self._status.setStyleSheet("color: #27ae60;")
            self._cancel_btn.setEnabled(False)
        elif status == "Error":
            self._status.setStyleSheet("color: #e74c3c;")
            self._cancel_btn.setEnabled(False)
        elif status == "Cancelled":
            self._status.setStyleSheet("color: #f39c12;")
            self._cancel_btn.setEnabled(False)


class ProgressPanel(QWidget):
    """Manages a list of TaskEntry widgets and a log viewer."""

    MAX_LOG_LINES = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: dict[str, TaskEntry] = {}
        self._log_line_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header
        header = QLabel("Task Queue")
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        # Scrollable area for task entries
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMaximumHeight(200)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._task_container = QWidget()
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 0, 0, 0)
        self._task_layout.setSpacing(2)
        self._task_layout.addStretch()
        self._scroll.setWidget(self._task_container)
        layout.addWidget(self._scroll)

        # Log viewer
        log_header = QLabel("Log")
        log_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        log_header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(log_header)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setMaximumBlockCount(self.MAX_LOG_LINES)
        self._log.setStyleSheet("""
            QPlainTextEdit {
                background: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        layout.addWidget(self._log, 1)

    def submit_task(self, name: str, worker: QRunnable):
        """Add a task entry, connect signals, and start the worker on the thread pool."""
        entry = TaskEntry(name)
        self._entries[name] = entry
        # Insert before the stretch
        self._task_layout.insertWidget(self._task_layout.count() - 1, entry)

        # Connect worker signals if worker has a signals object
        if hasattr(worker, "signals"):
            signals = worker.signals
            if hasattr(signals, "progress"):
                signals.progress.connect(entry.set_progress)
            if hasattr(signals, "status"):
                signals.status.connect(entry.set_status)
            if hasattr(signals, "log"):
                signals.log.connect(self.append_log)
            if hasattr(signals, "finished"):
                signals.finished.connect(lambda: entry.set_status("Done"))
            if hasattr(signals, "error"):
                signals.error.connect(lambda msg: self._on_task_error(name, msg))

        entry.cancel_requested.connect(self._on_cancel)
        entry.set_status("Running")
        self.append_log(f"[{name}] Started")

        QThreadPool.globalInstance().start(worker)

    def _on_cancel(self, name: str):
        """Handle cancel request for a task."""
        entry = self._entries.get(name)
        if entry:
            entry.set_status("Cancelled")
            self.append_log(f"[{name}] Cancelled by user")

    def _on_task_error(self, name: str, message: str):
        """Handle task error."""
        entry = self._entries.get(name)
        if entry:
            entry.set_status("Error")
        self.append_log(f"[{name}] ERROR: {message}")

    @Slot(str)
    def append_log(self, message: str):
        """Append a timestamped message to the log viewer."""
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.appendPlainText(f"[{ts}] {message}")
        # Auto-scroll to bottom
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def clear_completed(self):
        """Remove all completed, errored, or cancelled task entries."""
        to_remove = []
        for name, entry in self._entries.items():
            status = entry._status.text()
            if status in ("Done", "Error", "Cancelled"):
                to_remove.append(name)
        for name in to_remove:
            entry = self._entries.pop(name)
            self._task_layout.removeWidget(entry)
            entry.deleteLater()
