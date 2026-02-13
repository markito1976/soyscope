import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor


class TimelineWidget(QWidget):
    """PyQtGraph stacked area chart for findings over time.

    Emits year_clicked(int) when a bar/area is clicked.
    """

    year_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Configure dark theme for pyqtgraph
        pg.setConfigOptions(antialias=True)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground("#1e1e2e")
        self._plot_widget.showGrid(x=False, y=True, alpha=0.15)

        # Axis styling
        for axis_name in ("bottom", "left"):
            axis = self._plot_widget.getAxis(axis_name)
            axis.setPen(pg.mkPen(color="#45475a"))
            axis.setTextPen(pg.mkPen(color="#cdd6f4"))
            axis.setStyle(tickFont=pg.QtGui.QFont("Segoe UI", 8))

        self._plot_widget.setLabel("bottom", "Year", color="#a0a0b0",
                                   **{"font-size": "9pt"})
        self._plot_widget.setLabel("left", "Findings", color="#a0a0b0",
                                   **{"font-size": "9pt"})

        layout.addWidget(self._plot_widget)

        self._years: list[int] = []
        self._items: list[pg.PlotDataItem] = []

        # Connect click event
        self._plot_widget.scene().sigMouseClicked.connect(self._on_click)

    def update_stacked_area(self, years: list[int],
                            series_dict: dict[str, list[int]],
                            colors: dict[str, str] | None = None):
        """Redraw the stacked area chart.

        Args:
            years: List of year values for the x-axis.
            series_dict: Mapping of series name to list of counts per year.
            colors: Optional mapping of series name to hex color string.
        """
        self._plot_widget.clear()
        self._items.clear()
        self._years = list(years)

        if not years or not series_dict:
            return

        default_colors = [
            "#89b4fa", "#a6e3a1", "#f9e2af", "#fab387", "#f38ba8",
            "#cba6f7", "#94e2d5", "#eba0ac", "#74c7ec", "#b4befe"
        ]

        if colors is None:
            colors = {}

        x = np.array(years, dtype=float)
        cumulative = np.zeros(len(years), dtype=float)
        series_names = list(series_dict.keys())

        # Legend
        legend = self._plot_widget.addLegend(
            offset=(10, 10),
            brush=pg.mkBrush("#2d2d3f"),
            pen=pg.mkPen("#45475a"),
            labelTextColor="#cdd6f4",
            labelTextSize="8pt"
        )

        for i, name in enumerate(series_names):
            values = np.array(series_dict[name], dtype=float)
            prev_cumulative = cumulative.copy()
            cumulative = cumulative + values

            color_hex = colors.get(name, default_colors[i % len(default_colors)])
            color = QColor(color_hex)
            fill_color = QColor(color)
            fill_color.setAlpha(150)

            # Create filled area between prev_cumulative and cumulative
            fill = pg.FillBetweenItem(
                pg.PlotDataItem(x, cumulative, pen=pg.mkPen(color_hex, width=1.5)),
                pg.PlotDataItem(x, prev_cumulative, pen=pg.mkPen(color_hex, width=0)),
                brush=pg.mkBrush(fill_color)
            )
            self._plot_widget.addItem(fill)

            # Add a visible line on top for the legend
            line = self._plot_widget.plot(
                x, cumulative,
                pen=pg.mkPen(color_hex, width=1.5),
                name=name
            )
            self._items.append(line)

        # Set x-axis to integer ticks
        x_axis = self._plot_widget.getAxis("bottom")
        if len(years) <= 30:
            ticks = [(float(y), str(y)) for y in years]
            x_axis.setTicks([ticks])
        else:
            # For many years, show every 5th year
            ticks = [(float(y), str(y)) for y in years if y % 5 == 0]
            x_axis.setTicks([ticks])

    def _on_click(self, event):
        """Handle click to emit year_clicked signal."""
        if not self._years:
            return

        # Map scene position to data coordinates
        vb = self._plot_widget.plotItem.vb
        pos = event.scenePos()
        mouse_point = vb.mapSceneToView(pos)
        clicked_x = mouse_point.x()

        # Find the nearest year
        nearest_year = min(self._years, key=lambda y: abs(y - clicked_x))
        # Only emit if reasonably close
        if abs(nearest_year - clicked_x) < 0.7:
            self.year_clicked.emit(nearest_year)
