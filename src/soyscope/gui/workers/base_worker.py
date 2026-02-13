"""Base class for all SoyScope background workers."""

from __future__ import annotations

import traceback

from PySide6.QtCore import QRunnable, Slot

from .signals import WorkerSignals


class BaseWorker(QRunnable):
    """Thread-pool-friendly runnable with standard signal plumbing.

    Subclasses implement :meth:`execute` and return a result object.
    The base class handles started/finished/error/result signals
    automatically.
    """

    def __init__(self) -> None:
        super().__init__()
        self.signals = WorkerSignals()
        self.setAutoDelete(True)
        self._cancelled = False

    # -- Cancellation --------------------------------------------------------

    def cancel(self) -> None:
        """Request cooperative cancellation.

        Workers should periodically check :attr:`is_cancelled` and
        exit early when ``True``.
        """
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Return ``True`` if cancellation has been requested."""
        return self._cancelled

    # -- Convenience emitters -----------------------------------------------

    def emit_progress(self, current: int, total: int, msg: str = "") -> None:
        """Emit a progress update (current, total, message)."""
        self.signals.progress.emit(current, total, msg)

    def emit_log(self, msg: str) -> None:
        """Emit a log line to the GUI console."""
        self.signals.log.emit(msg)

    # -- QRunnable entry point ----------------------------------------------

    @Slot()
    def run(self) -> None:
        """Entry point called by QThreadPool.  Do not override."""
        self.signals.started.emit()
        try:
            result = self.execute()
        except Exception:
            self.signals.error.emit(traceback.format_exc())
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

    # -- Subclass contract --------------------------------------------------

    def execute(self):
        """Perform the actual work.  Must be overridden by subclasses.

        Returns:
            Arbitrary result object that will be emitted via
            ``signals.result``.
        """
        raise NotImplementedError
