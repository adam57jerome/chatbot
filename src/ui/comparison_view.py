from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class AttemptComparisonView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.combo_a = QComboBox()
        self.combo_b = QComboBox()
        top.addWidget(QLabel("Passation A"))
        top.addWidget(self.combo_a)
        top.addWidget(QLabel("Passation B"))
        top.addWidget(self.combo_b)
        layout.addLayout(top)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Section", "A -> B", "Écart"])
        layout.addWidget(self.table)

        self.figure = Figure(figsize=(5, 3))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def set_section_deltas(self, deltas: dict[str, float]) -> None:
        items = list(deltas.items())
        self.table.setRowCount(len(items))
        for i, (sec, d) in enumerate(items):
            self.table.setItem(i, 0, QTableWidgetItem(sec))
            self.table.setItem(i, 1, QTableWidgetItem("A/B"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{d:+.2f}"))

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.bar([k for k, _ in items], [v for _, v in items])
        ax.axhline(0, color="black")
        ax.tick_params(axis="x", rotation=30)
        self.canvas.draw()
