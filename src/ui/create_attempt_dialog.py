from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QCheckBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout


class CreateAttemptDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Créer une nouvelle passation")
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Entrée / Mi-parcours / Sortie")
        self.label_edit.setToolTip("Nom de la passation")

        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)

        self.duplicate_cb = QCheckBox("Dupliquer les réponses de la passation précédente")
        self.duplicate_cb.setToolTip("Copie les réponses puis recalcule les scores")

        form.addRow("Label", self.label_edit)
        form.addRow("Date", self.date_edit)
        form.addRow("", self.duplicate_cb)
        layout.addLayout(form)

        hlp = QLabel("F1: aide section passations")
        layout.addWidget(hlp)

        btns = QHBoxLayout()
        ok = QPushButton("Créer")
        cancel = QPushButton("Annuler")
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        QShortcut(QKeySequence(Qt.Key.Key_F1), self, activated=self._show_help)

    def _show_help(self) -> None:
        QMessageBox.information(self, "Aide", "Voir help.md - section Passations.")

    def values(self) -> tuple[str, datetime, bool]:
        label = self.label_edit.text().strip() or "Passation"
        qd = self.date_edit.date()
        dt = datetime(qd.year(), qd.month(), qd.day())
        return label, dt, self.duplicate_cb.isChecked()
