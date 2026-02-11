from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QRadioButton,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from ..assignment_service import (
    assign_questionnaire_to_session,
    get_assignment_for_session,
    questionnaire_counts,
    wizard_prerequisites_logic,
)
from ..models import Question, Questionnaire, Section, Session as CohortSession, Trainee
from ..services import parse_question_block


class SetupWizardDialog(QDialog):
    def __init__(self, db, parent=None, start_step: int = 0) -> None:
        super().__init__(parent)
        self.db = db
        self.selected_questionnaire_id: int | None = None
        self.selected_session_id: int | None = None

        self.setWindowTitle("Nouveau parcours")
        self.resize(900, 650)

        root = QVBoxLayout(self)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.step1 = self._build_step1()
        self.step2 = self._build_step2()
        self.step3 = self._build_step3()
        self.stack.addWidget(self.step1)
        self.stack.addWidget(self.step2)
        self.stack.addWidget(self.step3)

        nav = QHBoxLayout()
        self.back_btn = QPushButton("Retour")
        self.next_btn = QPushButton("Suivant")
        self.finish_btn = QPushButton("Commencer la saisie")
        self.finish_btn.setEnabled(False)
        self.finish_btn.clicked.connect(self.accept)
        self.back_btn.clicked.connect(self.go_back)
        self.next_btn.clicked.connect(self.go_next)
        nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn)
        nav.addWidget(self.finish_btn)
        root.addLayout(nav)

        QShortcut(QKeySequence(Qt.Key.Key_F1), self, activated=self.open_context_help)

        self.stack.setCurrentIndex(start_step)
        self.refresh_questionnaires()
        self.refresh_sessions()
        self.update_nav()

    def open_context_help(self) -> None:
        idx = self.stack.currentIndex() + 1
        QMessageBox.information(self, "Aide", f"Aide wizard étape {idx} (voir help.md #wizard-etape-{idx}).")

    def _build_step1(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        self.radio_new_q = QRadioButton("Créer un nouveau questionnaire")
        self.radio_existing_q = QRadioButton("Utiliser un questionnaire existant")
        self.radio_new_q.setChecked(True)
        l.addWidget(self.radio_new_q)
        l.addWidget(self.radio_existing_q)

        form = QFormLayout()
        self.new_q_name = QLineEdit()
        self.new_q_ref = QLineEdit("15")
        self.existing_q_combo = QComboBox()
        form.addRow("Nom questionnaire", self.new_q_name)
        form.addRow("Référence /20", self.new_q_ref)
        form.addRow("Questionnaire existant", self.existing_q_combo)
        l.addLayout(form)

        l.addWidget(QLabel("Sections"))
        sec_row = QHBoxLayout()
        self.section_name_edit = QLineEdit()
        add_sec_btn = QPushButton("Ajouter section")
        add_sec_btn.clicked.connect(self.add_section)
        del_sec_btn = QPushButton("Supprimer section")
        del_sec_btn.clicked.connect(self.remove_section)
        sec_row.addWidget(self.section_name_edit)
        sec_row.addWidget(add_sec_btn)
        sec_row.addWidget(del_sec_btn)
        l.addLayout(sec_row)
        self.sections_list = QListWidget()
        l.addWidget(self.sections_list)

        l.addWidget(QLabel("Questions en bloc (section sélectionnée)"))
        self.questions_block = QPlainTextEdit()
        self.questions_block.setPlaceholderText("1=a\n2=c")
        l.addWidget(self.questions_block)
        add_q_btn = QPushButton("Ajouter questions")
        add_q_btn.clicked.connect(self.add_questions_block)
        l.addWidget(add_q_btn)

        self.step1_status = QLabel("Pré-requis: questionnaire + >=1 section + >=1 question")
        l.addWidget(self.step1_status)

        self._wizard_sections: dict[str, list[tuple[int, str]]] = {}
        return w

    def _build_step2(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)

        form = QFormLayout()
        self.session_combo = QComboBox()
        self.session_code = QLineEdit()
        self.session_label = QLineEdit()
        form.addRow("Session existante", self.session_combo)
        form.addRow("Code session (création)", self.session_code)
        form.addRow("Label session", self.session_label)
        l.addLayout(form)

        row = QHBoxLayout()
        self.nom_edit = QLineEdit()
        self.prenom_edit = QLineEdit()
        add_tr_btn = QPushButton("Ajouter stagiaire")
        add_tr_btn.clicked.connect(self.add_trainee)
        row.addWidget(self.nom_edit)
        row.addWidget(self.prenom_edit)
        row.addWidget(add_tr_btn)
        l.addLayout(row)

        self.trainees_bulk = QPlainTextEdit()
        self.trainees_bulk.setPlaceholderText("Dupont Alice\nDurand Bob")
        l.addWidget(self.trainees_bulk)
        add_bulk_btn = QPushButton("Importer liste")
        add_bulk_btn.clicked.connect(self.add_trainees_bulk)
        l.addWidget(add_bulk_btn)

        self.trainees_list = QListWidget()
        l.addWidget(self.trainees_list)
        self.step2_status = QLabel("Pré-requis: >=1 stagiaire")
        l.addWidget(self.step2_status)
        return w

    def _build_step3(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        self.resume = QTextBrowser()
        l.addWidget(self.resume)
        self.overwrite_assignment = QCheckBox("Écraser l'affectation existante")
        self.overwrite_assignment.setChecked(True)
        l.addWidget(self.overwrite_assignment)
        assign_btn = QPushButton("Rattacher")
        assign_btn.clicked.connect(self.assign)
        l.addWidget(assign_btn)
        self.done_label = QLabel("")
        l.addWidget(self.done_label)
        return w

    def refresh_questionnaires(self) -> None:
        self.existing_q_combo.clear()
        for q in self.db.scalars(select(Questionnaire).order_by(Questionnaire.name)).all():
            self.existing_q_combo.addItem(q.name, q.id)

    def refresh_sessions(self) -> None:
        self.session_combo.clear()
        self.session_combo.addItem("(Aucune)", None)
        for s in self.db.scalars(select(CohortSession).order_by(CohortSession.code)).all():
            self.session_combo.addItem(f"{s.code} - {s.label}", s.id)

    def add_section(self) -> None:
        name = self.section_name_edit.text().strip()
        if not name:
            return
        if name not in self._wizard_sections:
            self._wizard_sections[name] = []
            self.sections_list.addItem(name)

    def remove_section(self) -> None:
        item = self.sections_list.currentItem()
        if not item:
            return
        name = item.text()
        self._wizard_sections.pop(name, None)
        self.sections_list.takeItem(self.sections_list.currentRow())

    def add_questions_block(self) -> None:
        item = self.sections_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Wizard", "Sélectionnez une section.")
            return
        try:
            rows = parse_question_block(self.questions_block.toPlainText())
        except ValueError as exc:
            QMessageBox.warning(self, "Format invalide", str(exc))
            return
        sec = item.text()
        self._wizard_sections.setdefault(sec, []).extend(rows)
        self.step1_status.setText(f"{sec}: {len(self._wizard_sections[sec])} question(s)")

    def add_trainee(self) -> None:
        nom, prenom = self.nom_edit.text().strip(), self.prenom_edit.text().strip()
        if not nom:
            return
        self.trainees_list.addItem(f"{nom} {prenom}".strip())

    def add_trainees_bulk(self) -> None:
        for line in self.trainees_bulk.toPlainText().splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                self.trainees_list.addItem(f"{parts[0]} {' '.join(parts[1:])}")

    def go_back(self) -> None:
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self.update_nav()

    def _validate_step1(self) -> bool:
        if self.radio_existing_q.isChecked():
            qid = self.existing_q_combo.currentData()
            if not qid:
                return False
            sec_count, q_count = questionnaire_counts(self.db, qid)
            checks = wizard_prerequisites_logic(True, sec_count, q_count, 1)
            self.selected_questionnaire_id = qid if checks["step1_ok"] else None
            return checks["step1_ok"]

        name = self.new_q_name.text().strip()
        section_count = len(self._wizard_sections)
        question_count = sum(len(v) for v in self._wizard_sections.values())
        checks = wizard_prerequisites_logic(bool(name), section_count, question_count, 1)
        return checks["step1_ok"]

    def _persist_step1_if_needed(self) -> None:
        if self.radio_existing_q.isChecked():
            self.selected_questionnaire_id = self.existing_q_combo.currentData()
            return

        if self.selected_questionnaire_id:
            return

        q = Questionnaire(name=self.new_q_name.text().strip(), reference_score_20=float(self.new_q_ref.text() or "15"), active=True)
        self.db.add(q)
        self.db.flush()

        for idx, (sec_name, rows) in enumerate(self._wizard_sections.items(), start=1):
            sec = Section(questionnaire_id=q.id, name=sec_name, ordre=idx)
            self.db.add(sec)
            self.db.flush()
            for numero, rep in rows:
                self.db.add(Question(questionnaire_id=q.id, section_id=sec.id, numero=numero, bonne_reponse=rep))

        self.db.commit()
        self.selected_questionnaire_id = q.id

    def _validate_step2(self) -> bool:
        trainee_count = self.trainees_list.count()
        if trainee_count == 0:
            existing_session_id = self.session_combo.currentData()
            if existing_session_id:
                trainee_count = len(self.db.scalars(select(Trainee).where(Trainee.session_id == existing_session_id)).all())

        checks = wizard_prerequisites_logic(True, 1, 1, trainee_count)
        return checks["step2_ok"]

    def _persist_step2(self) -> None:
        session_id = self.session_combo.currentData()
        if session_id:
            session = self.db.get(CohortSession, session_id)
        else:
            code = self.session_code.text().strip()
            if not code:
                raise ValueError("Code session requis")
            session = self.db.scalar(select(CohortSession).where(CohortSession.code == code).limit(1))
            if not session:
                session = CohortSession(code=code, label=self.session_label.text().strip() or code, active=True)
                self.db.add(session)
                self.db.flush()

        existing = {f"{t.nom} {t.prenom}".strip() for t in self.db.scalars(select(Trainee).where(Trainee.session_id == session.id)).all()}
        for i in range(self.trainees_list.count()):
            fullname = self.trainees_list.item(i).text().strip()
            if fullname in existing:
                continue
            parts = fullname.split()
            self.db.add(Trainee(session_id=session.id, nom=parts[0], prenom=" ".join(parts[1:]), actif=True))

        self.db.commit()
        self.selected_session_id = session.id

    def _update_step3_resume(self) -> None:
        if not self.selected_questionnaire_id or not self.selected_session_id:
            return
        q = self.db.get(Questionnaire, self.selected_questionnaire_id)
        s = self.db.get(CohortSession, self.selected_session_id)
        sec_count, q_count = questionnaire_counts(self.db, q.id)
        tr_count = len(self.db.scalars(select(Trainee).where(Trainee.session_id == s.id)).all())
        self.resume.setMarkdown(
            f"## Résumé\n- Session: {s.code} - {s.label}\n- Questionnaire: {q.name}\n- Sections: {sec_count}\n- Questions: {q_count}\n- Stagiaires: {tr_count}"
        )

    def go_next(self) -> None:
        idx = self.stack.currentIndex()
        if idx == 0:
            if not self._validate_step1():
                QMessageBox.warning(self, "Wizard", "Étape 1 incomplète.")
                return
            self._persist_step1_if_needed()
        if idx == 1:
            if not self._validate_step2():
                QMessageBox.warning(self, "Wizard", "Ajoutez au moins 1 stagiaire.")
                return
            self._persist_step2()
            self._update_step3_resume()
        self.stack.setCurrentIndex(min(2, idx + 1))
        self.update_nav()

    def assign(self) -> None:
        if not self.selected_questionnaire_id or not self.selected_session_id:
            QMessageBox.warning(self, "Wizard", "Étapes précédentes incomplètes.")
            return
        existing = get_assignment_for_session(self.db, self.selected_session_id)
        if existing and not self.overwrite_assignment.isChecked():
            QMessageBox.information(self, "Wizard", "Affectation existante conservée.")
            return
        if existing and self.overwrite_assignment.isChecked():
            confirm = QMessageBox.question(self, "Confirmation", "Écraser l'affectation existante ?")
            if confirm != QMessageBox.StandardButton.Yes:
                return

        assign_questionnaire_to_session(
            self.db,
            session_id=self.selected_session_id,
            questionnaire_id=self.selected_questionnaire_id,
            overwrite=True,
        )
        self.done_label.setText("Configuration terminée ✅")
        self.finish_btn.setEnabled(True)

    def update_nav(self) -> None:
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx > 0)
        self.next_btn.setEnabled(idx < 2)
