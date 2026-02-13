import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Signal

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class HeatmapWidget(QWidget):
    """Matplotlib heatmap for sector x derivative matrix.

    Emits cell_clicked(sector, derivative) when a cell is clicked.
    Supports hover tooltip showing the count value.
    """

    cell_clicked = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Matplotlib figure with dark background
        self._fig = Figure(facecolor="#1e1e2e")
        self._canvas = FigureCanvas(self._fig)
        self._canvas.setStyleSheet("background: #1e1e2e;")
        layout.addWidget(self._canvas)

        self._ax = self._fig.add_subplot(111)
        self._sectors: list[str] = []
        self._derivatives: list[str] = []
        self._matrix: np.ndarray | None = None
        self._annot = None

        # Connect mouse events
        self._canvas.mpl_connect("button_press_event", self._on_click)
        self._canvas.mpl_connect("motion_notify_event", self._on_hover)

        # Tooltip annotation (invisible by default)
        self._tooltip = self._ax.annotate(
            "", xy=(0, 0), xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", fc="#45475a", ec="#89b4fa", alpha=0.9),
            color="#cdd6f4", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#89b4fa"),
            visible=False, zorder=10
        )

    def update_heatmap(self, matrix: list[list[int]] | np.ndarray,
                       sectors: list[str], derivatives: list[str]):
        """Redraw the heatmap with new data.

        Args:
            matrix: 2D array of shape (len(sectors), len(derivatives)).
            sectors: Row labels (y-axis).
            derivatives: Column labels (x-axis).
        """
        self._sectors = list(sectors)
        self._derivatives = list(derivatives)
        self._matrix = np.array(matrix, dtype=float)

        self._ax.clear()
        self._ax.set_facecolor("#1e1e2e")

        if self._matrix.size == 0:
            self._ax.text(0.5, 0.5, "No data", transform=self._ax.transAxes,
                          ha="center", va="center", color="#a0a0b0", fontsize=12)
            self._canvas.draw_idle()
            return

        im = self._ax.imshow(self._matrix, cmap="YlOrRd", aspect="auto",
                             interpolation="nearest")

        # Axis labels
        self._ax.set_xticks(range(len(self._derivatives)))
        self._ax.set_xticklabels(self._derivatives, rotation=45, ha="right",
                                 fontsize=8, color="#cdd6f4")
        self._ax.set_yticks(range(len(self._sectors)))
        self._ax.set_yticklabels(self._sectors, fontsize=8, color="#cdd6f4")

        # Cell text annotations
        for i in range(len(self._sectors)):
            for j in range(len(self._derivatives)):
                val = int(self._matrix[i, j])
                if val > 0:
                    text_color = "white" if val > self._matrix.max() * 0.6 else "#1e1e2e"
                    self._ax.text(j, i, str(val), ha="center", va="center",
                                  fontsize=8, color=text_color, fontweight="bold")

        # Colorbar
        if hasattr(self, "_cbar") and self._cbar is not None:
            self._cbar.remove()
        self._cbar = self._fig.colorbar(im, ax=self._ax, shrink=0.8)
        self._cbar.ax.tick_params(colors="#cdd6f4", labelsize=8)

        # Recreate tooltip after clear
        self._tooltip = self._ax.annotate(
            "", xy=(0, 0), xytext=(10, 10),
            textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.3", fc="#45475a", ec="#89b4fa", alpha=0.9),
            color="#cdd6f4", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#89b4fa"),
            visible=False, zorder=10
        )

        self._ax.tick_params(colors="#cdd6f4")
        self._fig.tight_layout()
        self._canvas.draw_idle()

    def _get_cell(self, event) -> tuple[int, int] | None:
        """Return (row, col) indices for a mouse event, or None if outside."""
        if event.inaxes != self._ax or self._matrix is None:
            return None
        col = int(round(event.xdata))
        row = int(round(event.ydata))
        if 0 <= row < len(self._sectors) and 0 <= col < len(self._derivatives):
            return row, col
        return None

    def _on_click(self, event):
        """Emit cell_clicked signal when a cell is clicked."""
        cell = self._get_cell(event)
        if cell is not None:
            row, col = cell
            self.cell_clicked.emit(self._sectors[row], self._derivatives[col])

    def _on_hover(self, event):
        """Show tooltip on hover."""
        cell = self._get_cell(event)
        if cell is not None:
            row, col = cell
            val = int(self._matrix[row, col])
            sector = self._sectors[row]
            derivative = self._derivatives[col]
            self._tooltip.xy = (col, row)
            self._tooltip.set_text(f"{sector} / {derivative}\nCount: {val}")
            self._tooltip.set_visible(True)
            self._canvas.draw_idle()
        else:
            if self._tooltip.get_visible():
                self._tooltip.set_visible(False)
                self._canvas.draw_idle()
