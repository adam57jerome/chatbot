from __future__ import annotations

import csv
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Question, Questionnaire, Section, Session as CohortSession, Trainee
from .services import (
    color_for_score,
    ensure_seed_data,
    export_chatgpt_payload,
    get_or_create_attempt,
    group_synthesis,
    parse_question_block,
    save_answer,
    section_stats_for_attempt,
)


class HelpDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Aide")
        self.resize(900, 600)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        help_file = Path(__file__).parent / "help" / "help.md"
        browser.setMarkdown(help_file.read_text(encoding="utf-8"))
        layout.addWidget(browser)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.db = SessionLocal()
        self.setWindowTitle("Questionnaire AC")
        self.resize(1280, 800)

        top = QWidget()
        root = QVBoxLayout(top)

        topbar = QHBoxLayout()
        self.session_combo = QComboBox()
        self.questionnaire_combo = QComboBox()
        self.reference_label = QLabel("Référence: -")
        self.session_combo.setToolTip("Choisir la session active")
        self.questionnaire_combo.setToolTip("Choisir le questionnaire")

        topbar.addWidget(QLabel("Session"))
        topbar.addWidget(self.session_combo)
        topbar.addWidget(QLabel("Questionnaire"))
        topbar.addWidget(self.questionnaire_combo)
        topbar.addWidget(self.reference_label)

        root.addLayout(topbar)

        body = QHBoxLayout()
        self.section_list = QListWidget()
        self.section_list.setToolTip("Sections du questionnaire")
        body.addWidget(self.section_list, 1)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_section_tab(), "Section")
        self.tabs.addTab(self._build_trainee_tab(), "Stagiaire")
        self.tabs.addTab(self._build_synthesis_tab(), "Synthèse groupe")
        self.tabs.addTab(self._build_compare_tab(), "Comparatifs sections")
        self.tabs.addTab(self._build_admin_tab(), "Admin")
        self.tabs.addTab(self._build_help_tab(), "Aide")
        body.addWidget(self.tabs, 4)

        root.addLayout(body)
        self.setCentralWidget(top)

        self._build_menu_help()
        QShortcut(QKeySequence(Qt.Key.Key_F1), self, activated=self.open_help)

        self.session_combo.currentIndexChanged.connect(self.refresh_all_views)
        self.questionnaire_combo.currentIndexChanged.connect(self.refresh_all_views)
        self.section_list.currentRowChanged.connect(self.refresh_section_grid)
        self.trainee_combo.currentIndexChanged.connect(self.refresh_section_grid)

        self.load_top_filters()

    def _build_menu_help(self) -> None:
        help_menu = self.menuBar().addMenu("Aide")
        action = QAction("Ouvrir l'aide", self)
        action.triggered.connect(self.open_help)
        help_menu.addAction(action)

    def _build_section_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        top = QHBoxLayout()
        self.trainee_combo = QComboBox()
        top.addWidget(QLabel("Stagiaire"))
        top.addWidget(self.trainee_combo)
        qmark = QPushButton("?")
        qmark.clicked.connect(lambda: QMessageBox.information(self, "Aide", "Saisissez les réponses ligne par ligne."))
        top.addWidget(qmark)
        layout.addLayout(top)

        self.grid = QTableWidget(0, 4)
        self.grid.setHorizontalHeaderLabels(["Numero", "Bonne réponse", "Réponse saisie", "Score"])
        self.grid.setToolTip("Grille de saisie des réponses")
        layout.addWidget(self.grid)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Enregistrer")
        save_btn.clicked.connect(self.save_grid)
        clear_btn = QPushButton("Effacer réponses")
        clear_btn.clicked.connect(self.clear_grid)
        copy_btn = QPushButton("Copier données pour ChatGPT")
        copy_btn.clicked.connect(self.copy_chatgpt)
        buttons.addWidget(save_btn)
        buttons.addWidget(clear_btn)
        buttons.addWidget(copy_btn)
        layout.addLayout(buttons)

        self.section_total = QLabel("Total: 0 | Note /20: 0")
        layout.addWidget(self.section_total)
        return widget

    def _build_trainee_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.trainee_stats_table = QTableWidget(0, 2)
        self.trainee_stats_table.setHorizontalHeaderLabels(["Section", "Note /20"])
        layout.addWidget(self.trainee_stats_table)
        self.figure = Figure(figsize=(4, 3))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        self.trainee_message = QLabel("")
        layout.addWidget(self.trainee_message)
        return widget

    def _build_synthesis_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.synthesis_table = QTableWidget(0, 3)
        self.synthesis_table.setHorizontalHeaderLabels(["Stagiaire", "Moyenne globale", "% >= référence"])
        layout.addWidget(self.synthesis_table)
        export_btn = QPushButton("Exporter synthèse groupe (CSV)")
        export_btn.clicked.connect(self.export_group_csv)
        layout.addWidget(export_btn)
        return widget

    def _build_compare_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.compare_table = QTableWidget(0, 3)
        self.compare_table.setHorizontalHeaderLabels(["Section", "Moyenne groupe", "Écart référence"])
        layout.addWidget(self.compare_table)
        export_sec_btn = QPushButton("Exporter notes par section (CSV)")
        export_sec_btn.clicked.connect(self.export_section_csv)
        layout.addWidget(export_sec_btn)
        return widget

    def _build_admin_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()
        self.admin_q_name = QLineEdit()
        self.admin_q_ref = QLineEdit("15")
        create_q_btn = QPushButton("Créer questionnaire")
        create_q_btn.clicked.connect(self.create_questionnaire)
        form.addRow("Nom", self.admin_q_name)
        form.addRow("Référence /20", self.admin_q_ref)
        form.addRow(create_q_btn)
        layout.addLayout(form)

        self.bulk_questions = QPlainTextEdit()
        self.bulk_questions.setPlaceholderText("1=a\n2=c")
        self.bulk_questions.setToolTip("Ajout en bloc: une ligne par question")
        add_bulk_btn = QPushButton("Ajouter questions en bloc dans section sélectionnée")
        add_bulk_btn.clicked.connect(self.add_bulk_questions)
        layout.addWidget(self.bulk_questions)
        layout.addWidget(add_bulk_btn)

        self.session_code = QLineEdit()
        self.session_label = QLineEdit()
        add_session_btn = QPushButton("Créer session")
        add_session_btn.clicked.connect(self.create_session)
        layout.addWidget(QLabel("Code session"))
        layout.addWidget(self.session_code)
        layout.addWidget(QLabel("Label session"))
        layout.addWidget(self.session_label)
        layout.addWidget(add_session_btn)

        self.trainees_block = QPlainTextEdit()
        self.trainees_block.setPlaceholderText("Dupont Alice\nDurand Bob")
        add_trainees_btn = QPushButton("Importer stagiaires (copier/coller)")
        add_trainees_btn.clicked.connect(self.import_trainees)
        layout.addWidget(self.trainees_block)
        layout.addWidget(add_trainees_btn)

        return widget

    def _build_help_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        browser = QTextBrowser()
        browser.setMarkdown((Path(__file__).parent / "help" / "help.md").read_text(encoding="utf-8"))
        layout.addWidget(browser)
        return widget

    def load_top_filters(self) -> None:
        self.session_combo.clear()
        self.questionnaire_combo.clear()
        sessions = self.db.scalars(select(CohortSession).order_by(CohortSession.code)).all()
        questionnaires = self.db.scalars(select(Questionnaire).order_by(Questionnaire.name)).all()
        for s in sessions:
            self.session_combo.addItem(f"{s.code} - {s.label}", s.id)
        for q in questionnaires:
            self.questionnaire_combo.addItem(q.name, q.id)
        self.refresh_all_views()

    def current_session_id(self) -> int | None:
        return self.session_combo.currentData()

    def current_questionnaire_id(self) -> int | None:
        return self.questionnaire_combo.currentData()

    def refresh_all_views(self) -> None:
        qid = self.current_questionnaire_id()
        sid = self.current_session_id()
        if not qid or not sid:
            return
        questionnaire = self.db.get(Questionnaire, qid)
        self.reference_label.setText(f"Référence: {questionnaire.reference_score_20:.1f}/20")

        self.section_list.clear()
        sections = self.db.scalars(select(Section).where(Section.questionnaire_id == qid).order_by(Section.ordre)).all()
        for sec in sections:
            self.section_list.addItem(sec.name)

        self.trainee_combo.clear()
        trainees = self.db.scalars(select(Trainee).where(Trainee.session_id == sid, Trainee.actif.is_(True))).all()
        for t in trainees:
            self.trainee_combo.addItem(f"{t.nom} {t.prenom}", t.id)

        if sections:
            self.section_list.setCurrentRow(0)

        self.refresh_synthesis()
        self.refresh_compare()

    def get_current_section(self) -> Section | None:
        qid = self.current_questionnaire_id()
        idx = self.section_list.currentRow()
        if qid is None or idx < 0:
            return None
        sections = self.db.scalars(select(Section).where(Section.questionnaire_id == qid).order_by(Section.ordre)).all()
        if idx >= len(sections):
            return None
        return sections[idx]

    def refresh_section_grid(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        tid = self.trainee_combo.currentData()
        section = self.get_current_section()
        if not all([sid, qid, tid, section]):
            return

        attempt = get_or_create_attempt(self.db, sid, qid, tid)
        questions = self.db.scalars(select(Question).where(Question.section_id == section.id).order_by(Question.numero)).all()
        self.grid.setRowCount(len(questions))
        for i, q in enumerate(questions):
            self.grid.setItem(i, 0, QTableWidgetItem(str(q.numero)))
            self.grid.setItem(i, 1, QTableWidgetItem(q.bonne_reponse))
            existing = next((a for a in attempt.answers if a.question_id == q.id), None)
            self.grid.setItem(i, 2, QTableWidgetItem(existing.reponse_texte if existing else ""))
            self.grid.setItem(i, 3, QTableWidgetItem(str(existing.score if existing else 0)))

        stats = section_stats_for_attempt(self.db, attempt.id, section.id)
        color = color_for_score(stats.note_sur_20, self.db.get(Questionnaire, qid).reference_score_20)
        self.section_total.setText(f"Total: {stats.total_points} | Note /20: {stats.note_sur_20}")
        self.section_total.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.refresh_trainee_tab()

    def save_grid(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        tid = self.trainee_combo.currentData()
        section = self.get_current_section()
        if not all([sid, qid, tid, section]):
            return
        attempt = get_or_create_attempt(self.db, sid, qid, tid)
        questions = self.db.scalars(select(Question).where(Question.section_id == section.id).order_by(Question.numero)).all()
        for i, q in enumerate(questions):
            response = self.grid.item(i, 2).text() if self.grid.item(i, 2) else ""
            answer = save_answer(self.db, attempt.id, q.id, response, q.bonne_reponse)
            self.grid.setItem(i, 3, QTableWidgetItem(str(answer.score)))
        self.refresh_section_grid()

    def clear_grid(self) -> None:
        for i in range(self.grid.rowCount()):
            self.grid.setItem(i, 2, QTableWidgetItem(""))
            self.grid.setItem(i, 3, QTableWidgetItem("0"))

    def copy_chatgpt(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            return
        QApplication.clipboard().setText(export_chatgpt_payload(self.db, sid, qid))
        QMessageBox.information(self, "Copié", "JSON copié dans le presse-papiers.")

    def refresh_trainee_tab(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        tid = self.trainee_combo.currentData()
        if not all([sid, qid, tid]):
            return
        attempt = get_or_create_attempt(self.db, sid, qid, tid)
        sections = self.db.scalars(select(Section).where(Section.questionnaire_id == qid).order_by(Section.ordre)).all()
        questionnaire = self.db.get(Questionnaire, qid)

        self.trainee_stats_table.setRowCount(len(sections))
        names, vals = [], []
        weak = []
        for i, sec in enumerate(sections):
            st = section_stats_for_attempt(self.db, attempt.id, sec.id)
            names.append(sec.name)
            vals.append(st.note_sur_20)
            if st.note_sur_20 < questionnaire.reference_score_20:
                weak.append(sec.name)
            self.trainee_stats_table.setItem(i, 0, QTableWidgetItem(sec.name))
            self.trainee_stats_table.setItem(i, 1, QTableWidgetItem(f"{st.note_sur_20:.2f}"))

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.bar(names, vals)
        ax.axhline(questionnaire.reference_score_20, color="red", linestyle="--")
        ax.set_ylim(0, 20)
        ax.tick_params(axis="x", rotation=30)
        self.canvas.draw()

        self.trainee_message.setText(
            "Points à renforcer: " + (", ".join(weak) if weak else "Aucun (au-dessus de la référence)")
        )

    def refresh_synthesis(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            return
        synth = group_synthesis(self.db, sid, qid)
        ref = self.db.get(Questionnaire, qid).reference_score_20
        rows = synth["trainees_stats"]
        self.synthesis_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            pct = 100 if row["global_note"] >= ref else 0
            self.synthesis_table.setItem(i, 0, QTableWidgetItem(row["trainee"]))
            self.synthesis_table.setItem(i, 1, QTableWidgetItem(str(row["global_note"])))
            self.synthesis_table.setItem(i, 2, QTableWidgetItem(str(pct)))

    def refresh_compare(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            return
        synth = group_synthesis(self.db, sid, qid)
        ref = self.db.get(Questionnaire, qid).reference_score_20
        stats = sorted(synth["section_stats"].items(), key=lambda x: x[1]["mean"], reverse=True)
        self.compare_table.setRowCount(len(stats))
        for i, (name, s) in enumerate(stats):
            self.compare_table.setItem(i, 0, QTableWidgetItem(name))
            self.compare_table.setItem(i, 1, QTableWidgetItem(str(s["mean"])))
            self.compare_table.setItem(i, 2, QTableWidgetItem(str(round(s["mean"] - ref, 2))))

    def create_questionnaire(self) -> None:
        name = self.admin_q_name.text().strip()
        if not name:
            return
        ref = float(self.admin_q_ref.text() or "15")
        self.db.add(Questionnaire(name=name, reference_score_20=ref, active=True))
        self.db.commit()
        self.load_top_filters()

    def add_bulk_questions(self) -> None:
        section = self.get_current_section()
        if not section:
            QMessageBox.warning(self, "Erreur", "Sélectionnez une section.")
            return
        try:
            rows = parse_question_block(self.bulk_questions.toPlainText())
        except ValueError as exc:
            QMessageBox.warning(self, "Format invalide", str(exc))
            return

        for numero, rep in rows:
            self.db.add(
                Question(
                    questionnaire_id=section.questionnaire_id,
                    section_id=section.id,
                    numero=numero,
                    bonne_reponse=rep,
                )
            )
        self.db.commit()
        self.refresh_section_grid()

    def create_session(self) -> None:
        code = self.session_code.text().strip()
        label = self.session_label.text().strip() or code
        if not code:
            return
        self.db.add(CohortSession(code=code, label=label, active=True))
        self.db.commit()
        self.load_top_filters()

    def import_trainees(self) -> None:
        sid = self.current_session_id()
        if not sid:
            return
        for line in self.trainees_block.toPlainText().splitlines():
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            nom = parts[0]
            prenom = " ".join(parts[1:])
            self.db.add(Trainee(session_id=sid, nom=nom, prenom=prenom, actif=True))
        self.db.commit()
        self.refresh_all_views()

    def export_group_csv(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter synthèse", "synthese.csv", "CSV (*.csv)")
        if not path:
            return
        synth = group_synthesis(self.db, sid, qid)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Stagiaire", "Note globale"])
            for row in synth["trainees_stats"]:
                writer.writerow([row["trainee"], row["global_note"]])

    def export_section_csv(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter sections", "sections.csv", "CSV (*.csv)")
        if not path:
            return
        synth = group_synthesis(self.db, sid, qid)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Section", "Moyenne", "Médiane", "Min", "Max"])
            for name, stat in synth["section_stats"].items():
                writer.writerow([name, stat["mean"], stat["median"], stat["min"], stat["max"]])

    def open_help(self) -> None:
        HelpDialog().exec()


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_seed_data(db)

    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
