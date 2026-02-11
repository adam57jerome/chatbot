from __future__ import annotations

import csv
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
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

from .database import SessionLocal, initialize_database
from .assignment_service import can_start_saisie, get_assigned_questionnaire_id
from .attempt_service import compare_attempts_section_delta, create_attempt, list_attempts, save_answer_for_attempt
from .excel_importer import parse_excel_preview
from .import_service import import_excel_to_db
from .models import Answer, Question, Questionnaire, Section, Session as CohortSession, Trainee
from .ui.wizard_setup import SetupWizardDialog
from .ui.create_attempt_dialog import CreateAttemptDialog
from .ui.comparison_view import AttemptComparisonView
from .services import (
    color_for_score,
    ensure_seed_data,
    export_chatgpt_payload,
    group_synthesis,
    parse_question_block,
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


class ExcelImportDialog(QDialog):
    def __init__(self, db, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.preview = None
        self._section_checks: dict[str, QCheckBox] = {}
        self._trainee_answer_checks: dict[str, QCheckBox] = {}
        self._trainee_new_checks: dict[str, QCheckBox] = {}
        self._trainee_existing_state: dict[str, bool] = {}

        self.setWindowTitle("Importer Excel")
        self.resize(980, 760)

        layout = QVBoxLayout(self)

        choose_btn = QPushButton("Choisir un fichier .xlsx…")
        choose_btn.clicked.connect(self.choose_file)
        choose_btn.setToolTip("Sélectionne le fichier Excel source")
        layout.addWidget(choose_btn)

        self.file_label = QLabel("Aucun fichier sélectionné")
        layout.addWidget(self.file_label)

        form = QFormLayout()
        self.questionnaire_name = QLineEdit()
        self.questionnaire_name.textChanged.connect(self.refresh_preview_tables)

        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self.refresh_preview_tables)

        self.import_answers_cb = QCheckBox("Importer les réponses existantes des stagiaires")
        self.import_answers_cb.setChecked(True)
        self.import_new_trainees_cb = QCheckBox("Importer les nouveaux stagiaires")
        self.import_new_trainees_cb.setChecked(True)

        form.addRow("Questionnaire", self.questionnaire_name)
        form.addRow("Session", self.session_combo)
        form.addRow("", self.import_answers_cb)
        form.addRow("", self.import_new_trainees_cb)
        layout.addLayout(form)

        q_conflict_box = QGroupBox("Conflit questionnaire (si même nom)")
        q_conflict_layout = QVBoxLayout(q_conflict_box)
        self.q_conflict_label = QLabel("Aucun conflit détecté pour le moment.")
        q_conflict_layout.addWidget(self.q_conflict_label)

        self.q_conflict_group = QButtonGroup(self)
        self.q_cancel_radio = QRadioButton("Ne pas importer ce questionnaire (annuler)")
        self.q_copy_radio = QRadioButton("Importer en créant une copie")
        self.q_copy_radio.setChecked(True)
        self.q_conflict_group.addButton(self.q_cancel_radio)
        self.q_conflict_group.addButton(self.q_copy_radio)
        q_conflict_layout.addWidget(self.q_cancel_radio)
        q_conflict_layout.addWidget(self.q_copy_radio)
        layout.addWidget(q_conflict_box)

        self.sections_table = QTableWidget(0, 4)
        self.sections_table.setHorizontalHeaderLabels(["Section", "Nb questions", "État", "Importer"])
        layout.addWidget(self.sections_table)

        self.trainees_table = QTableWidget(0, 4)
        self.trainees_table.setHorizontalHeaderLabels(["Stagiaire", "État", "Utiliser réponses", "Importer nouveau"])
        layout.addWidget(self.trainees_table)

        self.summary = QTextBrowser()
        layout.addWidget(self.summary)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Journal / Diagnostics")
        layout.addWidget(self.log_box)

        action_row = QHBoxLayout()
        launch_btn = QPushButton("Lancer l'import")
        launch_btn.clicked.connect(self.run_import)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        action_row.addWidget(launch_btn)
        action_row.addWidget(cancel_btn)
        layout.addLayout(action_row)

        self.reload_sessions()

    def _append_log(self, text: str) -> None:
        self.log_box.appendPlainText(text)

    def reload_sessions(self) -> None:
        self.session_combo.clear()
        self.session_combo.addItem("Créer session depuis nom du fichier", "__auto__")
        sessions = self.db.scalars(select(CohortSession).order_by(CohortSession.code)).all()
        for s in sessions:
            self.session_combo.addItem(f"{s.code} - {s.label}", s.code)

    def _target_questionnaire_exists(self) -> tuple[bool, set[str]]:
        name = self.questionnaire_name.text().strip()
        if not name:
            return False, set()
        q = self.db.scalar(select(Questionnaire).where(Questionnaire.name == name).limit(1))
        if not q:
            return False, set()
        sections = self.db.scalars(select(Section).where(Section.questionnaire_id == q.id)).all()
        return True, {s.name for s in sections}

    def _session_code(self) -> str:
        code = self.session_combo.currentData()
        if code == "__auto__" and self.preview is not None:
            return Path(self.preview.source_path).stem.upper().replace(" ", "_")[:30]
        return code or "AUTO"

    def _existing_trainees_in_session(self) -> set[str]:
        code = self._session_code()
        session = self.db.scalar(select(CohortSession).where(CohortSession.code == code).limit(1))
        if not session:
            return set()
        rows = self.db.scalars(select(Trainee).where(Trainee.session_id == session.id)).all()
        return {f"{r.nom} {r.prenom}".strip() for r in rows}

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Sélectionner fichier Excel", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            self.preview = parse_excel_preview(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Excel", f"Analyse impossible: {exc}")
            return

        self.file_label.setText(path)
        self.questionnaire_name.setText(self.preview.questionnaire_name)
        self.refresh_preview_tables()

    def refresh_preview_tables(self) -> None:
        if self.preview is None:
            return

        q_exists, existing_sections = self._target_questionnaire_exists()
        self.q_conflict_label.setText(
            f"Le questionnaire '{self.questionnaire_name.text().strip()}' existe déjà. Que voulez-vous faire ?"
            if q_exists
            else "Aucun questionnaire existant avec ce nom."
        )

        self.sections_table.setRowCount(0)
        self._section_checks.clear()
        for i, section in enumerate(self.preview.sections_data):
            self.sections_table.insertRow(i)
            self.sections_table.setItem(i, 0, QTableWidgetItem(section.name))
            self.sections_table.setItem(i, 1, QTableWidgetItem(str(len(section.questions))))
            state = "EXISTE" if section.name in existing_sections else "NOUVELLE"
            self.sections_table.setItem(i, 2, QTableWidgetItem(state))
            cb = QCheckBox()
            cb.setChecked(state == "NOUVELLE")
            self.sections_table.setCellWidget(i, 3, cb)
            self._section_checks[section.name] = cb

        existing_trainees = self._existing_trainees_in_session()
        self.trainees_table.setRowCount(0)
        self._trainee_answer_checks.clear()
        self._trainee_new_checks.clear()
        self._trainee_existing_state.clear()
        for i, trainee in enumerate(self.preview.trainees):
            self.trainees_table.insertRow(i)
            self.trainees_table.setItem(i, 0, QTableWidgetItem(trainee))
            is_existing = trainee in existing_trainees
            self._trainee_existing_state[trainee] = is_existing
            self.trainees_table.setItem(i, 1, QTableWidgetItem("EXISTE" if is_existing else "NOUVEAU"))

            resp_cb = QCheckBox()
            resp_cb.setChecked(True)
            self.trainees_table.setCellWidget(i, 2, resp_cb)
            self._trainee_answer_checks[trainee] = resp_cb

            new_cb = QCheckBox()
            new_cb.setChecked(not is_existing)
            new_cb.setEnabled(not is_existing)
            self.trainees_table.setCellWidget(i, 3, new_cb)
            self._trainee_new_checks[trainee] = new_cb

        trainee_list = "<br/>".join(self.preview.trainees) if self.preview.trainees else "(aucun stagiaire détecté)"
        sections_html = "<br/>".join(f"{s.name}: {len(s.questions)} questions" for s in self.preview.sections_data)
        self.summary.setHtml(
            f"<b>Questionnaire proposé:</b> {self.questionnaire_name.text().strip() or self.preview.questionnaire_name}<br/>"
            f"<b>Sections détectées:</b> {len(self.preview.section_names)}<br/>{sections_html}<br/><br/>"
            f"<b>Questions totales:</b> {self.preview.total_questions}<br/>"
            f"<b>Stagiaires détectés:</b> {len(self.preview.trainees)}<br/>{trainee_list}"
        )

    def run_import(self) -> None:
        if self.preview is None:
            QMessageBox.warning(self, "Import Excel", "Choisissez d'abord un fichier .xlsx")
            return

        q_name = self.questionnaire_name.text().strip() or self.preview.questionnaire_name
        session_code = self._session_code()

        q_exists, _existing_sections = self._target_questionnaire_exists()
        strategy = "copy"
        if q_exists and self.q_cancel_radio.isChecked():
            QMessageBox.information(self, "Import Excel", f"Import annulé: questionnaire '{q_name}' déjà existant.")
            return
        if q_exists:
            strategy = "copy"

        selected_sections = {name for name, cb in self._section_checks.items() if cb.isChecked()}
        selected_trainees_for_answers = {name for name, cb in self._trainee_answer_checks.items() if cb.isChecked()}
        selected_new_trainees = {
            name
            for name, cb in self._trainee_new_checks.items()
            if cb.isEnabled() and cb.isChecked()
        }

        estimated_responses = 0
        for sec in self.preview.sections_data:
            if sec.name in selected_sections:
                estimated_responses += len(sec.questions) * len(selected_trainees_for_answers)

        ok = QMessageBox.question(
            self,
            "Confirmer import",
            f"Vous allez importer: {len(selected_sections)} sections, "
            f"{len(selected_trainees_for_answers)} stagiaires, {estimated_responses} réponses. Continuer ?",
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        self._append_log("--- Début import Excel ---")
        try:
            questionnaire, session, warnings, diagnostics = import_excel_to_db(
                self.db,
                self.preview,
                questionnaire_name=q_name,
                session_code=session_code,
                import_answers=self.import_answers_cb.isChecked(),
                questionnaire_strategy=strategy,
                selected_sections=selected_sections,
                selected_trainees_for_answers=selected_trainees_for_answers,
                import_new_trainees=self.import_new_trainees_cb.isChecked(),
                selected_new_trainees=selected_new_trainees,
            )
        except Exception as exc:
            self._append_log(f"ERREUR: {exc}")
            QMessageBox.critical(self, "Import Excel", f"Erreur pendant l'import: {exc}")
            return

        for line in diagnostics:
            self._append_log(line)
        for warning in warnings:
            self._append_log(f"WARNING: {warning}")

        QMessageBox.information(
            self,
            "Import terminé",
            f"Questionnaire créé: {questionnaire.name}\nSession: {session.code}",
        )
        self.accept()


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
        self.attempt_combo = QComboBox()
        self.attempt_combo.setToolTip("Passation active")
        self.session_combo.setToolTip("Choisir la session active")
        self.questionnaire_combo.setToolTip("Choisir le questionnaire")

        topbar.addWidget(QLabel("Session"))
        topbar.addWidget(self.session_combo)
        topbar.addWidget(QLabel("Questionnaire"))
        topbar.addWidget(self.questionnaire_combo)
        topbar.addWidget(QLabel("Passation"))
        topbar.addWidget(self.attempt_combo)
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
        self.tabs.addTab(self._build_compare_tab(), "Comparaison passations")
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
        self.attempt_combo.currentIndexChanged.connect(self.refresh_section_grid)
        self.attempt_combo.currentIndexChanged.connect(self.refresh_compare_attempts)

        self.load_top_filters()

    def _build_menu_help(self) -> None:
        file_menu = self.menuBar().addMenu("Parcours")
        wizard_action = QAction("Nouveau parcours…", self)
        wizard_action.triggered.connect(self.open_setup_wizard)
        file_menu.addAction(wizard_action)

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
        create_attempt_btn = QPushButton("Créer une nouvelle passation")
        create_attempt_btn.setToolTip("Créer une passation Entrée/Sortie et la sélectionner")
        create_attempt_btn.clicked.connect(self.create_new_attempt)
        buttons.addWidget(save_btn)
        buttons.addWidget(clear_btn)
        buttons.addWidget(copy_btn)
        buttons.addWidget(create_attempt_btn)
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
        self.compare_view = AttemptComparisonView()
        self.compare_view.combo_a.currentIndexChanged.connect(self.refresh_compare_attempts)
        self.compare_view.combo_b.currentIndexChanged.connect(self.refresh_compare_attempts)
        layout.addWidget(self.compare_view)
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

        excel_btn = QPushButton("Importer Excel…")
        excel_btn.setToolTip("Importer questionnaire, sections, questions, stagiaires et réponses depuis un .xlsx")
        excel_btn.clicked.connect(self.open_excel_import)
        layout.addWidget(excel_btn)

        new_attempt_admin_btn = QPushButton("Créer une nouvelle passation")
        new_attempt_admin_btn.clicked.connect(self.create_new_attempt)
        layout.addWidget(new_attempt_admin_btn)

        wizard_btn = QPushButton("Nouveau parcours…")
        wizard_btn.setToolTip("Process guidé: Sections -> Stagiaires -> Rattacher questionnaire")
        wizard_btn.clicked.connect(self.open_setup_wizard)
        layout.addWidget(wizard_btn)

        attach_btn = QPushButton("Rattacher questionnaire à une session")
        attach_btn.clicked.connect(self.open_assignment_step)
        layout.addWidget(attach_btn)

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
        if not sid:
            return

        assigned_qid = get_assigned_questionnaire_id(self.db, sid)
        if assigned_qid:
            idx = self.questionnaire_combo.findData(assigned_qid)
            if idx >= 0 and qid != assigned_qid:
                self.questionnaire_combo.blockSignals(True)
                self.questionnaire_combo.setCurrentIndex(idx)
                self.questionnaire_combo.blockSignals(False)
                qid = assigned_qid

        if not qid:
            self.reference_label.setText("Référence: -")
            self.section_list.clear()
            self.grid.setRowCount(0)
            self.section_total.setText("Aucun questionnaire rattaché. Ouvrir l'assistant.")
            self.section_total.setStyleSheet("color: #c62828; font-weight: bold;")
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

        self.attempt_combo.clear()
        attempts = list_attempts(self.db, sid, qid)
        if not attempts:
            self.attempt_combo.addItem("Aucune passation", None)
        for a in attempts:
            self.attempt_combo.addItem(f"{a.label or 'Passation'} - {a.created_at:%Y-%m-%d}", a.id)

        self.compare_view.combo_a.clear()
        self.compare_view.combo_b.clear()
        for a in attempts:
            label = f"{a.label or 'Passation'} - {a.created_at:%Y-%m-%d}"
            self.compare_view.combo_a.addItem(label, a.id)
            self.compare_view.combo_b.addItem(label, a.id)
        if len(attempts) > 1:
            self.compare_view.combo_b.setCurrentIndex(1)

        if sections:
            self.section_list.setCurrentRow(0)

        self.refresh_synthesis()
        self.refresh_compare_attempts()

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
        aid = self.attempt_combo.currentData()
        section = self.get_current_section()
        if sid and not can_start_saisie(self.db, sid):
            self.grid.setRowCount(0)
            self.section_total.setText("Aucun questionnaire rattaché à cette session. Ouvrir l'assistant.")
            self.section_total.setStyleSheet("color: #c62828; font-weight: bold;")
            return
        if not all([sid, qid, tid, section, aid]):
            return

        questions = self.db.scalars(select(Question).where(Question.section_id == section.id).order_by(Question.numero)).all()
        self.grid.setRowCount(len(questions))
        for i, q in enumerate(questions):
            self.grid.setItem(i, 0, QTableWidgetItem(str(q.numero)))
            self.grid.setItem(i, 1, QTableWidgetItem(q.bonne_reponse or ""))
            existing = self.db.scalar(select(Answer).where(Answer.attempt_id == aid, Answer.trainee_id == tid, Answer.question_id == q.id).limit(1))
            self.grid.setItem(i, 2, QTableWidgetItem(existing.reponse_texte if existing else ""))
            self.grid.setItem(i, 3, QTableWidgetItem(str(existing.score if existing else 0)))

        stats = section_stats_for_attempt(self.db, aid, section.id, tid)
        color = color_for_score(stats.note_sur_20, self.db.get(Questionnaire, qid).reference_score_20)
        self.section_total.setText(f"Total: {stats.total_points} | Note /20: {stats.note_sur_20}")
        self.section_total.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.refresh_trainee_tab()

    def save_grid(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        tid = self.trainee_combo.currentData()
        aid = self.attempt_combo.currentData()
        section = self.get_current_section()
        if not all([sid, qid, tid, section, aid]):
            return
        questions = self.db.scalars(select(Question).where(Question.section_id == section.id).order_by(Question.numero)).all()
        for i, q in enumerate(questions):
            response = self.grid.item(i, 2).text() if self.grid.item(i, 2) else ""
            answer = save_answer_for_attempt(self.db, aid, tid, q.id, response, q.bonne_reponse)
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
        aid = self.attempt_combo.currentData()
        if not aid:
            return
        sections = self.db.scalars(select(Section).where(Section.questionnaire_id == qid).order_by(Section.ordre)).all()
        questionnaire = self.db.get(Questionnaire, qid)

        self.trainee_stats_table.setRowCount(len(sections))
        names, vals = [], []
        weak = []
        for i, sec in enumerate(sections):
            st = section_stats_for_attempt(self.db, aid, sec.id, tid)
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

    def refresh_compare_attempts(self) -> None:
        qid = self.current_questionnaire_id()
        aid_a = self.compare_view.combo_a.currentData()
        aid_b = self.compare_view.combo_b.currentData()
        if not all([qid, aid_a, aid_b]):
            self.compare_view.set_section_deltas({})
            return
        deltas = compare_attempts_section_delta(self.db, aid_a, aid_b, qid)
        self.compare_view.set_section_deltas(deltas)

    def create_new_attempt(self) -> None:
        sid = self.current_session_id()
        qid = self.current_questionnaire_id()
        if not all([sid, qid]):
            QMessageBox.warning(self, "Passation", "Sélectionnez une session et un questionnaire.")
            return
        dialog = CreateAttemptDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        label, date_value, duplicate = dialog.values()
        attempts = list_attempts(self.db, sid, qid)
        source = attempts[0].id if (duplicate and attempts) else None
        created = create_attempt(
            self.db,
            session_id=sid,
            questionnaire_id=qid,
            label=label,
            created_at=date_value,
            duplicate_from_attempt_id=source,
        )
        self.load_top_filters()
        idx = self.attempt_combo.findData(created.id)
        if idx >= 0:
            self.attempt_combo.setCurrentIndex(idx)

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

    def open_excel_import(self) -> None:
        dialog = ExcelImportDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_top_filters()

    def open_setup_wizard(self) -> None:
        dialog = SetupWizardDialog(self.db, self, start_step=0)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_top_filters()
            if dialog.selected_session_id:
                i = self.session_combo.findData(dialog.selected_session_id)
                if i >= 0:
                    self.session_combo.setCurrentIndex(i)
            if dialog.selected_questionnaire_id:
                i = self.questionnaire_combo.findData(dialog.selected_questionnaire_id)
                if i >= 0:
                    self.questionnaire_combo.setCurrentIndex(i)

    def open_assignment_step(self) -> None:
        dialog = SetupWizardDialog(self.db, self, start_step=2)
        dialog.selected_session_id = self.current_session_id()
        dialog.selected_questionnaire_id = self.current_questionnaire_id()
        dialog._update_step3_resume()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_top_filters()

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
    initialize_database()
    with SessionLocal() as db:
        ensure_seed_data(db)

    existing_app = QApplication.instance()
    created_app = existing_app is None
    app = QApplication(sys.argv) if created_app else existing_app

    w = MainWindow()
    w.show()

    if created_app:
        sys.exit(app.exec())


if __name__ == "__main__":
    main()
