from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, TypeVar

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import crud
from app.db import SessionLocal, get_sqlite_db_path, init_db
from app.help_texts import AIDE_SECTIONS, CSV_EXAMPLE, HELP_TEXTS
from app.importer import ImportOptions, apply_import, parse_csv, report_to_csv, validate_rows
from app.models import Formation, QCMQuestion, Questionnaire, Section, Stagiaire
from app.qcm_service import (
    add_question,
    create_questionnaire,
    delete_question,
    delete_questionnaire,
    get_attempt_detail,
    list_attempts,
    list_questionnaires,
    list_questions,
    normalize_answer,
    start_attempt,
    submit_attempt,
    update_question,
    update_questionnaire,
)
from app.schemas import (
    FormationCreate,
    FormationUpdate,
    SectionCreate,
    SectionUpdate,
    StagiaireCreate,
    StagiaireUpdate,
)
from ui.layout import inject_app_css, render_header, toast

st.set_page_config(page_title="Gestion Stagiaires", layout="wide")

T = TypeVar("T")
logo_path = Path("app/static/logo_acces_vii.svg")

for key, value in {
    "trainee_screen": "list",
    "edit_trainee_id": None,
    "section_screen": "list",
    "edit_section_id": None,
    "formation_screen": "list",
    "edit_formation_id": None,
    "qcm_questionnaire_id": None,
    "qcm_attempt_id": None,
}.items():
    st.session_state.setdefault(key, value)


def safe_query(action: Callable[[], T]) -> T:
    try:
        return action()
    except OperationalError as exc:
        if "no such table" in str(exc).lower():
            init_db()
            return action()
        raise


def load_sections(db):
    return safe_query(lambda: db.scalars(select(Section).order_by(Section.code)).all())


def load_formations(db, active_only: bool = False):
    stmt = select(Formation).order_by(Formation.code)
    if active_only:
        stmt = stmt.where(Formation.actif.is_(True))
    return safe_query(lambda: db.scalars(stmt).all())


def load_trainees(db, query: str):
    stmt = select(Stagiaire).order_by(Stagiaire.nom, Stagiaire.prenom)
    if query:
        q = f"%{query.strip()}%"
        stmt = stmt.where(or_(Stagiaire.nom.ilike(q), Stagiaire.prenom.ilike(q), Stagiaire.email.ilike(q)))
    return safe_query(lambda: db.scalars(stmt).all())


def render_trainee_form(*, db, mode: str, sections: list[Section], formations: list[Formation], trainee: Stagiaire | None = None) -> None:
    is_edit = mode == "edit"
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {'Modifier stagiaire' if is_edit else 'Nouveau stagiaire'}")
    section_options = {"Aucune section": None} | {f"{s.code} - {s.nom}": s.id for s in sections}
    formation_options = {"Aucune formation": None} | {f"{f.code} - {f.nom}": f.id for f in formations}

    section_labels = list(section_options.keys())
    formation_labels = list(formation_options.keys())
    current_section = trainee.section_id if trainee else None
    current_formation = trainee.formation_souhaitee_id if trainee else None
    default_section = next((label for label, sid in section_options.items() if sid == current_section), "Aucune section")
    default_formation = next((label for label, fid in formation_options.items() if fid == current_formation), "Aucune formation")

    with st.form(f"trainee_form_{mode}_{trainee.id if trainee else 'new'}"):
        left, right = st.columns(2)
        nom = left.text_input("Nom *", value=trainee.nom if trainee else "")
        prenom = left.text_input("Prénom *", value=trainee.prenom if trainee else "")
        email = right.text_input("Email", value=trainee.email or "" if trainee else "", help=HELP_TEXTS["email"])
        telephone = right.text_input("Téléphone", value=trainee.telephone or "" if trainee else "")
        o_left, o_right = st.columns(2)
        section_label = o_left.selectbox("Section", section_labels, index=section_labels.index(default_section), help=HELP_TEXTS["section"])
        formation_label = o_right.selectbox("Formation souhaitée", formation_labels, index=formation_labels.index(default_formation), help=HELP_TEXTS["formation"])
        notes = st.text_area("Notes", value=trainee.notes or "" if trainee else "")
        save = st.form_submit_button("💾 Enregistrer", type="primary")

    if save:
        try:
            payload = StagiaireUpdate(
                nom=nom,
                prenom=prenom,
                email=email or None,
                telephone=telephone or None,
                notes=notes or None,
                section_id=section_options[section_label],
                formation_souhaitee_id=formation_options[formation_label],
            )
            if is_edit and trainee:
                crud.update_trainee(db, trainee.id, payload)
                toast("success", "Stagiaire mis à jour")
            else:
                crud.create_stagiaire(db, StagiaireCreate(**payload.model_dump()))
                toast("success", "Stagiaire créé")
            st.session_state.trainee_screen = "list"
            st.rerun()
        except ValidationError as exc:
            st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
        except IntegrityError:
            db.rollback()
            st.error("Erreur: email déjà utilisé")

    st.markdown("</div>", unsafe_allow_html=True)


def page_stagiaires() -> None:
    render_header("Gestion des stagiaires", "Gestion / Stagiaires")
    with SessionLocal() as db:
        q = st.text_input("Recherche", key="q_trainees")
        trainees = load_trainees(db, q)
        sections = load_sections(db)
        formations = load_formations(db, active_only=True)
        if st.button("+ Nouveau stagiaire"):
            st.session_state.trainee_screen = "create"
        if st.session_state.trainee_screen == "create":
            render_trainee_form(db=db, mode="create", sections=sections, formations=formations)
        st.dataframe(
            [{"Nom": t.nom, "Prénom": t.prenom, "Email": t.email or "-", "Formation": t.formation_souhaitee.code if t.formation_souhaitee else "Aucune"} for t in trainees],
            use_container_width=True,
            hide_index=True,
        )


def page_sections() -> None:
    render_header("Gestion des sections", "Gestion / Sections")
    st.info("Fonctionnalité sections inchangée.")


def page_formations() -> None:
    render_header("Gestion des formations", "Gestion / Formations")
    st.info("Fonctionnalité formations inchangée.")


def page_import_csv() -> None:
    render_header("Import CSV", "Outils / Import CSV")
    upload = st.file_uploader("Fichier CSV", type=["csv"])
    sep_choice = st.selectbox("Séparateur", ["auto", ",", ";", "\t"], help=HELP_TEXTS["import_separator"])
    encoding_choice = st.selectbox("Encodage", ["auto", "utf-8", "latin-1"], help=HELP_TEXTS["import_encoding"])
    has_header = st.checkbox("Le fichier a une ligne d'en-tête", value=True)
    if not upload:
        return
    df = parse_csv(upload.getvalue(), sep=sep_choice, encoding=encoding_choice, has_header=has_header)
    st.dataframe(df.head(20), use_container_width=True)
    cols = ["-- Ignorer --"] + list(df.columns)
    mapping = {
        "nom": st.selectbox("nom *", cols, key="map_nom"),
        "prenom": st.selectbox("prenom *", cols, key="map_prenom"),
        "email": st.selectbox("email", cols, key="map_email"),
        "telephone": st.selectbox("telephone", cols, key="map_tel"),
        "notes": st.selectbox("notes", cols, key="map_notes"),
        "section_code": st.selectbox("section_code", cols, key="map_section"),
        "formation_code": st.selectbox("formation_code", cols, key="map_formation"),
    }
    strategy = st.selectbox("Stratégie doublons", ["skip", "update", "strict"], help=HELP_TEXTS["import_strategy"])
    create_sections = st.checkbox("Créer sections manquantes")
    create_formations = st.checkbox("Créer formations manquantes")
    with SessionLocal() as db:
        options = ImportOptions(create_sections, create_formations, strategy)
        valid_rows, errors, duplicates = validate_rows(df, mapping, db, options)
        st.write({"lignes": len(df), "valides": len(valid_rows), "erreurs": len(errors), "doublons": len(duplicates)})
        if st.button("Lancer l'import", type="primary"):
            stats, report = apply_import(db, valid_rows, options)
            final_report = report + errors
            st.success(f"créés={stats['created']} mis à jour={stats['updated']} ignorés={stats['skipped']} erreurs={stats['errors']}")
            st.dataframe(final_report, use_container_width=True)
            st.download_button("Télécharger rapport_import.csv", report_to_csv(final_report), "rapport_import.csv", "text/csv")


def page_qcm_questionnaires() -> None:
    render_header("QCM - Questionnaires", "QCM / Questionnaires")
    with SessionLocal() as db:
        q = st.text_input("Recherche titre", key="q_qcm")
        questionnaires = list_questionnaires(db, q)
        with st.form("new_qcm"):
            titre = st.text_input("Titre questionnaire *")
            description = st.text_area("Description")
            create_btn = st.form_submit_button("Créer questionnaire", type="primary")
        if create_btn and titre.strip():
            create_questionnaire(db, titre, description)
            toast("success", "Questionnaire créé")
            st.rerun()

        st.dataframe([{"ID": qn.id, "Titre": qn.titre, "Description": qn.description or "-"} for qn in questionnaires], use_container_width=True, hide_index=True)

        if questionnaires:
            selected_id = st.selectbox("Questionnaire", [q.id for q in questionnaires], format_func=lambda x: next(q.titre for q in questionnaires if q.id == x))
            selected = next(q for q in questionnaires if q.id == selected_id)
            st.session_state.qcm_questionnaire_id = selected_id

            with st.form("edit_qcm"):
                etitre = st.text_input("Titre", value=selected.titre)
                edesc = st.text_area("Description", value=selected.description or "")
                save = st.form_submit_button("Mettre à jour")
                delete = st.form_submit_button("Supprimer", help=HELP_TEXTS["delete"])
            if save:
                update_questionnaire(db, selected_id, etitre, edesc)
                toast("success", "Questionnaire mis à jour")
                st.rerun()
            if delete:
                delete_questionnaire(db, selected_id)
                toast("success", "Questionnaire supprimé")
                st.rerun()

            st.markdown("#### Questions")
            questions = list_questions(db, selected_id)
            st.dataframe([{"ID": q.id, "N°": q.numero, "Attendu": q.resultat_attendu, "Points": q.points, "Énoncé": q.enonce or "-"} for q in questions], use_container_width=True, hide_index=True)
            with st.form("add_question"):
                numero = st.number_input("Numéro", min_value=1, step=1, value=1)
                attendu = st.text_input("Résultat attendu *", placeholder="A ou A,C")
                enonce = st.text_area("Énoncé")
                points = st.number_input("Points", min_value=1, value=1)
                add_btn = st.form_submit_button("Ajouter question", type="primary")
            if add_btn and attendu.strip():
                add_question(db, selected_id, int(numero), attendu, enonce, int(points))
                toast("success", "Question ajoutée")
                st.rerun()

            if questions:
                qid = st.selectbox("Question à modifier/supprimer", [q.id for q in questions], format_func=lambda x: f"Q{next(q.numero for q in questions if q.id==x)}")
                qobj = next(q for q in questions if q.id == qid)
                with st.form("edit_question"):
                    enumero = st.number_input("Numéro", min_value=1, value=qobj.numero)
                    eattendu = st.text_input("Résultat attendu", value=qobj.resultat_attendu)
                    eenonce = st.text_area("Énoncé", value=qobj.enonce or "")
                    epoints = st.number_input("Points", min_value=1, value=qobj.points)
                    saveq = st.form_submit_button("Modifier question")
                    delq = st.form_submit_button("Supprimer question", help=HELP_TEXTS["delete"])
                if saveq:
                    update_question(db, qid, int(enumero), eattendu, eenonce, int(epoints))
                    toast("success", "Question modifiée")
                    st.rerun()
                if delq:
                    delete_question(db, qid)
                    toast("success", "Question supprimée")
                    st.rerun()

            st.markdown("#### Import rapide des questions")
            bulk = st.text_area("Format: numero;resultat_attendu;enonce")
            if st.button("Importer lignes questions"):
                added = 0
                for line in bulk.splitlines():
                    parts = [p.strip() for p in line.split(";")]
                    if len(parts) >= 2 and parts[0].isdigit():
                        add_question(db, selected_id, int(parts[0]), parts[1], parts[2] if len(parts) > 2 else None, 1)
                        added += 1
                toast("success", f"{added} question(s) importée(s)")
                st.rerun()


def page_qcm_passages() -> None:
    render_header("QCM - Passages / Saisie", "QCM / Passages")
    with SessionLocal() as db:
        trainees = load_trainees(db, "")
        questionnaires = list_questionnaires(db)
        if not trainees or not questionnaires:
            st.warning("Créer au moins un stagiaire et un questionnaire avant un passage.")
            return

        col1, col2 = st.columns(2)
        stagiaire_id = col1.selectbox("Stagiaire", [t.id for t in trainees], format_func=lambda i: next(f"{t.nom} {t.prenom}" for t in trainees if t.id == i))
        questionnaire_id = col2.selectbox("Questionnaire", [q.id for q in questionnaires], format_func=lambda i: next(q.titre for q in questionnaires if q.id == i))

        if st.button("Démarrer une tentative", type="primary"):
            attempt = start_attempt(db, stagiaire_id, questionnaire_id)
            st.session_state.qcm_attempt_id = attempt.id
            st.rerun()

        attempt_id = st.session_state.qcm_attempt_id
        if attempt_id:
            attempt = get_attempt_detail(db, attempt_id)
            if attempt and attempt.questionnaire_id == questionnaire_id and attempt.stagiaire_id == stagiaire_id:
                questions = list_questions(db, questionnaire_id)
                st.markdown("#### Feuille de saisie")
                answers: dict[int, str | None] = {}
                with st.form("submit_attempt"):
                    for q in questions:
                        answers[q.id] = st.text_input(
                            f"Q{q.numero} - {q.enonce or 'Sans énoncé'}",
                            key=f"ans_{attempt_id}_{q.id}",
                            help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                        )
                    submit_btn = st.form_submit_button("Corriger et enregistrer", type="primary")
                    cancel_btn = st.form_submit_button("Annuler")
                if cancel_btn:
                    st.session_state.qcm_attempt_id = None
                    st.rerun()
                if submit_btn:
                    result = submit_attempt(db, attempt_id, answers)
                    toast("success", f"Corrigé: score {result.score_brut}/{result.total_questions}, note {result.note_sur_20}/20")
                    st.rerun()

                refreshed = get_attempt_detail(db, attempt_id)
                if refreshed and refreshed.answers:
                    st.markdown("#### Récapitulatif")
                    rows = []
                    for ans in refreshed.answers:
                        rows.append(
                            {
                                "Question": ans.question.numero,
                                "Attendu": ans.question.resultat_attendu,
                                "Réponse": ans.reponse_stagiaire or "",
                                "Correct": "✅" if ans.est_correct else "❌",
                                "Point": ans.point_obtenu,
                            }
                        )
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                    st.info(f"Score brut: {refreshed.score_brut} / {refreshed.total_questions} | Note: {refreshed.note_sur_20}/20")

        st.markdown("#### Historique des passages")
        f1, f2, f3 = st.columns(3)
        f_stagiaire = f1.selectbox("Filtre stagiaire", [0] + [t.id for t in trainees], format_func=lambda i: "Tous" if i == 0 else next(f"{t.nom} {t.prenom}" for t in trainees if t.id == i))
        f_q = f2.selectbox("Filtre questionnaire", [0] + [q.id for q in questionnaires], format_func=lambda i: "Tous" if i == 0 else next(q.titre for q in questionnaires if q.id == i))
        f_date = f3.date_input("Date", value=None)
        attempts = list_attempts(db, f_stagiaire or None, f_q or None, f_date if f_date else None)
        st.dataframe(
            [
                {
                    "ID": a.id,
                    "Date": a.date_passage,
                    "Stagiaire": f"{a.stagiaire.nom} {a.stagiaire.prenom}",
                    "Questionnaire": a.questionnaire.titre,
                    "Score": f"{a.score_brut}/{a.total_questions}",
                    "Note/20": a.note_sur_20,
                }
                for a in attempts
            ],
            use_container_width=True,
            hide_index=True,
        )


def page_help() -> None:
    render_header("📘 Aide", "Aide / Guide utilisateur")
    st.markdown("### Sommaire\n- Vue d'ensemble\n- Stagiaires\n- Sections\n- Formations\n- QCM\n- Import CSV\n- Sauvegarde / BDD")
    for k, title in [
        ("overview", "Vue d'ensemble"),
        ("stagiaires", "Stagiaires"),
        ("sections", "Sections"),
        ("formations", "Formations"),
        ("import_csv", "Import CSV"),
        ("database", "Sauvegarde / Base de données"),
    ]:
        with st.expander(title):
            st.write(AIDE_SECTIONS[k])
            if k == "import_csv":
                st.code(CSV_EXAMPLE, language="csv")


def page_tools() -> None:
    render_header("Outils", "Outils / Initialisation")
    if st.button("Initialiser la base", type="primary"):
        init_db()
        toast("success", "Base initialisée")


def page_about() -> None:
    render_header("À propos", "Paramètres / À propos")
    if logo_path.exists():
        st.image(str(logo_path))


def page_preferences() -> None:
    render_header("Préférences", "Paramètres / Préférences")
    if db := get_sqlite_db_path():
        st.code(db, language="text")


init_db()
inject_app_css()

if hasattr(st, "navigation") and hasattr(st, "Page"):
    nav = st.navigation(
        {
            "Gestion": [
                st.Page(page_stagiaires, title="Stagiaires", icon="👨‍🎓"),
                st.Page(page_sections, title="Sections", icon="🏫"),
                st.Page(page_formations, title="Formations", icon="🎓"),
                st.Page(page_qcm_questionnaires, title="QCM - Questionnaires", icon="📝"),
                st.Page(page_qcm_passages, title="QCM - Passages", icon="✅"),
            ],
            "Outils": [
                st.Page(page_import_csv, title="Import CSV", icon="📥"),
                st.Page(page_tools, title="Init DB", icon="🛠️"),
            ],
            "Paramètres": [
                st.Page(page_help, title="📘 Aide", icon="📘"),
                st.Page(page_about, title="À propos", icon="ℹ️"),
                st.Page(page_preferences, title="Préférences", icon="⚙️"),
            ],
        },
        position="top",
    )
    nav.run()
else:
    st.sidebar.image(str(logo_path))
    choice = st.sidebar.selectbox(
        "Navigation",
        ["Stagiaires", "Sections", "Formations", "QCM - Questionnaires", "QCM - Passages", "Import CSV", "📘 Aide", "Init DB", "À propos", "Préférences"],
    )
    {
        "Stagiaires": page_stagiaires,
        "Sections": page_sections,
        "Formations": page_formations,
        "QCM - Questionnaires": page_qcm_questionnaires,
        "QCM - Passages": page_qcm_passages,
        "Import CSV": page_import_csv,
        "📘 Aide": page_help,
        "Init DB": page_tools,
        "À propos": page_about,
        "Préférences": page_preferences,
    }[choice]()
