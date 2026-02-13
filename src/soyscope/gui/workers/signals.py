"""Shared Qt signals for background workers."""

from PySide6.QtCore import QObject, Signal


class WorkerSignals(QObject):
    """Signals emitted by all background workers.

    Attributes:
        started: Emitted when the worker begins execution.
        finished: Emitted when the worker completes (success or failure).
        error: Emitted with a traceback string on unhandled exception.
        result: Emitted with the return value of execute() on success.
        progress: Emitted with (current, total, message) for progress tracking.
        log: Emitted with a human-readable log message.
    """

    started = Signal()
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int, int, str)  # current, total, message
    log = Signal(str)
