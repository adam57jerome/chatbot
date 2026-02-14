from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, TypeVar

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import crud
from app.db import (
    SessionLocal,
    create_sqlite_backup,
    get_sqlite_db_path,
    init_db,
    list_sqlite_backups,
    restore_sqlite_backup,
)
from app.help_texts import AIDE_SECTIONS, CSV_EXAMPLE, HELP_TEXTS
from app.importer import ImportOptions, apply_import, parse_csv, report_to_csv, validate_rows
from app.models import Formation, Section, Stagiaire
from app.qcm_service import (
    add_question,
    create_questionnaire,
    delete_question,
    delete_questionnaire,
    delete_attempt,
    get_attempt_answers_map,
    get_attempt_detail,
    aggregate_scores_by_subchapter,
    get_trainee_qcm_summary,
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
from app.utils.json_safe import find_first_non_serializable_path, to_jsonable
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
    "qcm_edit_attempt_id": None,
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
            st.rerun()

        if st.session_state.trainee_screen == "create":
            render_trainee_form(db=db, mode="create", sections=sections, formations=formations)

        if st.session_state.trainee_screen == "edit":
            trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
            if not trainee:
                toast("warning", "Stagiaire introuvable")
                st.session_state.trainee_screen = "list"
                st.session_state.edit_trainee_id = None
                st.rerun()
            render_trainee_form(db=db, mode="edit", sections=sections, formations=formations, trainee=trainee)

        st.dataframe(
            [
                {
                    "ID": t.id,
                    "Nom": t.nom,
                    "Prénom": t.prenom,
                    "Email": t.email or "-",
                    "Formation": t.formation_souhaitee.code if t.formation_souhaitee else "Aucune",
                }
                for t in trainees
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Actions rapides")
        for trainee in trainees:
            cols = st.columns([3, 1, 1])
            cols[0].write(f"{trainee.nom} {trainee.prenom}")
            if cols[1].button("✏️ Modifier", key=f"edit_trainee_btn_{trainee.id}"):
                st.session_state.trainee_screen = "edit"
                st.session_state.edit_trainee_id = trainee.id
                st.rerun()
            if cols[2].button("Voir synthèse QCM", key=f"summary_btn_{trainee.id}"):
                st.query_params.update({"summary_trainee": str(trainee.id)})
                st.switch_page if False else None
                st.info("Allez dans Synthèse > 📊 Synthèse stagiaire (stagiaire présélectionné).")


def page_sections() -> None:
    render_header("Gestion des sections", "Gestion / Sections")
    with SessionLocal() as db:
        query = st.text_input("Recherche section", key="q_sections")
        sections, _total = crud.list_sections(db, q=query, page=1, per_page=500)

        if st.button("+ Nouvelle section", key="new_section_btn"):
            st.session_state.section_screen = "create"
            st.session_state.edit_section_id = None
            st.rerun()

        if st.session_state.section_screen in {"create", "edit"}:
            is_edit = st.session_state.section_screen == "edit"
            section = crud.get_section_by_id(db, st.session_state.edit_section_id) if is_edit else None
            if is_edit and not section:
                toast("warning", "Section introuvable")
                st.session_state.section_screen = "list"
                st.session_state.edit_section_id = None
                st.rerun()

            st.markdown("<div class='app-card'>", unsafe_allow_html=True)
            st.markdown(f"#### {'Modifier section' if is_edit else 'Nouvelle section'}")
            with st.form(f"section_form_{'edit' if is_edit else 'create'}"):
                c1, c2 = st.columns(2)
                code = c1.text_input("Code *", value=section.code if section else "")
                nom = c2.text_input("Nom *", value=section.nom if section else "")
                c3, c4 = st.columns(2)
                date_debut = c3.date_input("Date début", value=section.date_debut if section and section.date_debut else None)
                date_fin = c4.date_input("Date fin", value=section.date_fin if section and section.date_fin else None)
                description = st.text_area("Description", value=section.description or "" if section else "")
                save = st.form_submit_button("💾 Enregistrer", type="primary")
                cancel = st.form_submit_button("Annuler")

            if cancel:
                st.session_state.section_screen = "list"
                st.session_state.edit_section_id = None
                st.rerun()

            if save:
                try:
                    payload = SectionUpdate(
                        code=code,
                        nom=nom,
                        date_debut=date_debut,
                        date_fin=date_fin,
                        description=description or None,
                    )
                    if is_edit and section:
                        crud.update_section(db, section.id, payload)
                        toast("success", "Section mise à jour")
                    else:
                        crud.create_section(db, SectionCreate(**payload.model_dump()))
                        toast("success", "Section créée")
                    st.session_state.section_screen = "list"
                    st.session_state.edit_section_id = None
                    st.rerun()
                except ValidationError as exc:
                    st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
                except IntegrityError:
                    db.rollback()
                    st.error("Erreur: code section déjà utilisé")

            st.markdown("</div>", unsafe_allow_html=True)

        st.dataframe(
            [
                {
                    "ID": s.id,
                    "Code": s.code,
                    "Nom": s.nom,
                    "Date début": s.date_debut,
                    "Date fin": s.date_fin,
                    "Stagiaires": len(s.stagiaires),
                }
                for s in sections
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Actions")
        for section in sections:
            c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
            c1.write(f"{section.code} — {section.nom}")
            if c2.button("👥", key=f"section_assign_{section.id}", help="Assigner des stagiaires"):
                st.session_state["selected_section_for_assign"] = section.id
            if c3.button("✏️", key=f"section_edit_{section.id}"):
                st.session_state.section_screen = "edit"
                st.session_state.edit_section_id = section.id
                st.rerun()
            if c4.button("🗑️", key=f"section_delete_{section.id}"):
                crud.delete_section_safely(db, section.id)
                toast("success", "Section supprimée")
                st.rerun()

        selected_section_id = st.session_state.get("selected_section_for_assign")
        if selected_section_id:
            section = crud.get_section_by_id(db, selected_section_id)
            if section:
                st.markdown("---")
                st.markdown(f"#### Affectations — {section.code} / {section.nom}")
                assigned = crud.list_trainees_in_section(db, section.id)
                available = crud.list_trainees_available_for_section(db, section.id, include_other_sections=False)

                left, right = st.columns(2)
                with left:
                    st.markdown("**Stagiaires de la section**")
                    for trainee in assigned:
                        u1, u2 = st.columns([4, 1])
                        u1.write(f"{trainee.nom} {trainee.prenom}")
                        if u2.button("Retirer", key=f"unassign_{section.id}_{trainee.id}"):
                            crud.unassign_trainee(db, trainee.id, section.id)
                            st.rerun()
                with right:
                    st.markdown("**Stagiaires sans section**")
                    for trainee in available:
                        a1, a2 = st.columns([4, 1])
                        a1.write(f"{trainee.nom} {trainee.prenom}")
                        if a2.button("Ajouter", key=f"assign_{section.id}_{trainee.id}"):
                            crud.assign_trainee_to_section(db, trainee.id, section.id)
                            st.rerun()


def page_formations() -> None:
    render_header("Gestion des formations", "Gestion / Formations")
    with SessionLocal() as db:
        query = st.text_input("Recherche formation", key="q_formations")
        active_filter = st.selectbox(
            "Statut",
            ["Toutes", "Actives", "Inactives"],
            key="formation_status_filter",
        )
        actif_filter = {"Toutes": None, "Actives": "active", "Inactives": "inactive"}[active_filter]
        formations, _total = crud.list_formations(db, q=query, actif_filter=actif_filter, page=1, per_page=500)

        if st.button("+ Nouvelle formation", key="new_formation_btn"):
            st.session_state.formation_screen = "create"
            st.session_state.edit_formation_id = None
            st.rerun()

        if st.session_state.formation_screen in {"create", "edit"}:
            is_edit = st.session_state.formation_screen == "edit"
            formation = crud.get_formation_by_id(db, st.session_state.edit_formation_id) if is_edit else None
            if is_edit and not formation:
                toast("warning", "Formation introuvable")
                st.session_state.formation_screen = "list"
                st.session_state.edit_formation_id = None
                st.rerun()

            st.markdown("<div class='app-card'>", unsafe_allow_html=True)
            st.markdown(f"#### {'Modifier formation' if is_edit else 'Nouvelle formation'}")
            with st.form(f"formation_form_{'edit' if is_edit else 'create'}"):
                c1, c2 = st.columns(2)
                code = c1.text_input("Code *", value=formation.code if formation else "")
                nom = c2.text_input("Nom *", value=formation.nom if formation else "")
                description = st.text_area("Description", value=formation.description or "" if formation else "")
                actif = st.checkbox("Formation active", value=formation.actif if formation else True)
                save = st.form_submit_button("💾 Enregistrer", type="primary")
                cancel = st.form_submit_button("Annuler")

            if cancel:
                st.session_state.formation_screen = "list"
                st.session_state.edit_formation_id = None
                st.rerun()

            if save:
                try:
                    payload = FormationUpdate(
                        code=code,
                        nom=nom,
                        description=description or None,
                        actif=actif,
                    )
                    if is_edit and formation:
                        crud.update_formation(db, formation.id, payload)
                        toast("success", "Formation mise à jour")
                    else:
                        crud.create_formation(db, FormationCreate(**payload.model_dump()))
                        toast("success", "Formation créée")
                    st.session_state.formation_screen = "list"
                    st.session_state.edit_formation_id = None
                    st.rerun()
                except ValidationError as exc:
                    st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
                except IntegrityError:
                    db.rollback()
                    st.error("Erreur: code formation déjà utilisé")

            st.markdown("</div>", unsafe_allow_html=True)

        st.dataframe(
            [
                {
                    "ID": f.id,
                    "Code": f.code,
                    "Nom": f.nom,
                    "Active": "Oui" if f.actif else "Non",
                    "Souhaits": len(f.stagiaires_souhaits),
                }
                for f in formations
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Actions")
        for formation in formations:
            c1, c2, c3 = st.columns([5, 1, 1])
            c1.write(f"{formation.code} — {formation.nom}")
            if c2.button("✏️", key=f"formation_edit_{formation.id}"):
                st.session_state.formation_screen = "edit"
                st.session_state.edit_formation_id = formation.id
                st.rerun()
            if c3.button("🗑️", key=f"formation_delete_{formation.id}"):
                crud.delete_formation_safely(db, formation.id)
                toast("success", "Formation supprimée")
                st.rerun()


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

            questions = list_questions(db, selected_id)
            chapter_values = list(dict.fromkeys([q.chapitre for q in questions if q.chapitre]))
            chapter_options = ["Tous"] + chapter_values
            selected_chapter_filter = st.selectbox("Filtre chapitre", chapter_options, key=f"q_filter_chapter_{selected_id}")
            filtered_questions = questions
            if selected_chapter_filter != "Tous":
                filtered_questions = [q for q in filtered_questions if q.chapitre == selected_chapter_filter]

            subchapter_values = list(dict.fromkeys([(q.sous_chapitre or "Sans sous-chapitre") for q in filtered_questions]))
            subchapter_options = ["Tous"] + subchapter_values
            selected_subchapter_filter = st.selectbox("Filtre sous-chapitre", subchapter_options, key=f"q_filter_subchapter_{selected_id}")
            if selected_subchapter_filter != "Tous":
                filtered_questions = [q for q in filtered_questions if (q.sous_chapitre or "Sans sous-chapitre") == selected_subchapter_filter]

            st.dataframe([{"ID": q.id, "Chapitre": q.chapitre, "Sous-chapitre": q.sous_chapitre or "Sans sous-chapitre", "N°": q.numero, "Attendu": q.resultat_attendu, "Points": q.points, "Énoncé": q.enonce or "-"} for q in filtered_questions], use_container_width=True, hide_index=True)

            with st.form("add_question"):
                chapitre = st.text_input("Chapitre *", placeholder="Français, Mathématiques, ...")
                sous_chapitre = st.text_input("Sous-chapitre", placeholder="Optionnel")
                numero = st.number_input("Numéro", min_value=1, step=1, value=1)
                attendu = st.text_input("Résultat attendu *", placeholder="A ou A,C")
                enonce = st.text_area("Énoncé")
                points = st.number_input("Points", min_value=1, value=1)
                add_btn = st.form_submit_button("Ajouter question", type="primary")
            if add_btn:
                if not chapitre.strip():
                    st.error("Le chapitre est obligatoire.")
                elif not attendu.strip():
                    st.error("Le résultat attendu est obligatoire.")
                else:
                    add_question(db, selected_id, int(numero), attendu, enonce, int(points), chapitre, sous_chapitre)
                    toast("success", "Question ajoutée")
                    st.rerun()

            if questions:
                st.markdown("#### Modifier une question")
                editable_question_id = st.selectbox(
                    "Question à modifier",
                    [q.id for q in questions],
                    format_func=lambda qid: next(
                        f"[{q.chapitre} / {q.sous_chapitre or 'Sans sous-chapitre'}] Q{q.numero} - {q.enonce or '-'}"
                        for q in questions if q.id == qid
                    ),
                    key=f"edit_question_select_{selected_id}",
                )
                editable_question = next(q for q in questions if q.id == editable_question_id)
                with st.form(f"edit_question_{editable_question_id}"):
                    ec1, ec2 = st.columns(2)
                    e_chapitre = ec1.text_input("Chapitre *", value=editable_question.chapitre)
                    e_sous = ec2.text_input("Sous-chapitre", value=editable_question.sous_chapitre or "")
                    enumero = st.number_input("Numéro", min_value=1, step=1, value=int(editable_question.numero))
                    eattendu = st.text_input("Résultat attendu *", value=editable_question.resultat_attendu)
                    eenonce = st.text_area("Énoncé", value=editable_question.enonce or "")
                    epoints = st.number_input("Points", min_value=1, value=int(editable_question.points))
                    save_q = st.form_submit_button("Mettre à jour la question")
                    delete_q = st.form_submit_button("Supprimer la question")

                if save_q:
                    if not e_chapitre.strip():
                        st.error("Le chapitre est obligatoire.")
                    else:
                        update_question(
                            db,
                            editable_question_id,
                            int(enumero),
                            eattendu,
                            eenonce,
                            int(epoints),
                            e_chapitre,
                            e_sous,
                        )
                        toast("success", "Question mise à jour")
                        st.rerun()
                if delete_q:
                    delete_question(db, editable_question_id)
                    toast("success", "Question supprimée")
                    st.rerun()

            st.markdown("#### Export des questions (.csv)")
            export_rows = [
                {
                    "questionnaire": selected.titre,
                    "numero": q.numero,
                    "resultat_attendu": q.resultat_attendu,
                    "chapitre": q.chapitre,
                    "sous_chapitre": q.sous_chapitre or "",
                    "enonce": q.enonce or "",
                    "points": q.points,
                }
                for q in questions
            ]
            export_df = pd.DataFrame(export_rows)
            st.download_button(
                "Télécharger questions.csv",
                data=export_df.to_csv(index=False, sep=";").encode("utf-8"),
                file_name=f"questions_{selected.id}.csv",
                mime="text/csv",
                key=f"download_questions_csv_{selected.id}",
            )

            st.markdown("#### Import rapide des questions")
            bulk = st.text_area("Format: numero;resultat_attendu;chapitre;sous_chapitre;enonce")
            if st.button("Importer lignes questions"):
                added = 0
                rejected = 0
                for line in bulk.splitlines():
                    parts = [p.strip() for p in line.split(";")]
                    if len(parts) < 3 or not parts[0].isdigit():
                        rejected += 1
                        continue
                    numero = int(parts[0])
                    attendu_line = parts[1]
                    chapitre_line = parts[2]
                    sous_chapitre_line = parts[3] if len(parts) > 3 else None
                    enonce_line = parts[4] if len(parts) > 4 else None
                    if not chapitre_line:
                        chapitre_line = "Général"
                    if not attendu_line:
                        rejected += 1
                        continue
                    add_question(db, selected_id, numero, attendu_line, enonce_line, 1, chapitre_line, sous_chapitre_line)
                    added += 1
                toast("success", f"{added} question(s) importée(s), {rejected} rejetée(s)")
                st.rerun()

            st.markdown("#### Importer questionnaire(s) depuis CSV")
            st.caption("Colonnes attendues: questionnaire;numero;resultat_attendu;chapitre;sous_chapitre;enonce;points (chapitre obligatoire, numero optionnel)")
            csv_file = st.file_uploader("Fichier CSV questionnaires", type=["csv"], key="qcm_questionnaires_csv")
            if st.button("Importer questionnaire(s) CSV", key="import_qcm_csv_btn"):
                if not csv_file:
                    st.warning("Veuillez sélectionner un fichier CSV.")
                else:
                    content = csv_file.getvalue().decode("utf-8", errors="ignore")
                    reader = csv.DictReader(StringIO(content), delimiter=';')
                    required = {"questionnaire", "resultat_attendu", "chapitre"}
                    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                        st.error("Colonnes minimales requises: questionnaire;resultat_attendu;chapitre")
                    else:
                        created_q = 0
                        added_qs = 0
                        rejected = 0
                        qcache: dict[str, int] = {}
                        auto_num: dict[str, int] = {}
                        for row in reader:
                            q_title = (row.get("questionnaire") or "").strip()
                            attendu_line = (row.get("resultat_attendu") or "").strip()
                            chapitre_line = (row.get("chapitre") or "").strip()
                            sous_chapitre_line = (row.get("sous_chapitre") or "").strip() or None
                            enonce_line = (row.get("enonce") or "").strip() or None
                            points_raw = (row.get("points") or "1").strip()
                            numero_raw = (row.get("numero") or "").strip()

                            if not q_title or not attendu_line or not chapitre_line:
                                rejected += 1
                                continue

                            if q_title not in qcache:
                                qn = create_questionnaire(db, q_title)
                                qcache[q_title] = qn.id
                                auto_num[q_title] = 1
                                created_q += 1

                            if numero_raw.isdigit():
                                numero = int(numero_raw)
                            else:
                                numero = auto_num[q_title]
                                auto_num[q_title] += 1

                            points = int(points_raw) if points_raw.isdigit() and int(points_raw) > 0 else 1
                            add_question(db, qcache[q_title], numero, attendu_line, enonce_line, points, chapitre_line, sous_chapitre_line)
                            added_qs += 1

                        toast("success", f"{created_q} questionnaire(s) créé(s), {added_qs} question(s) importée(s), {rejected} ligne(s) rejetée(s)")
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

        edit_attempt_id = st.session_state.qcm_edit_attempt_id
        if edit_attempt_id:
            edit_attempt = get_attempt_detail(db, edit_attempt_id)
            if not edit_attempt:
                st.session_state.qcm_edit_attempt_id = None
                st.warning("Tentative introuvable.")
                st.rerun()

            st.markdown(f"#### Modifier tentative #{edit_attempt.id}")
            questions_edit = list_questions(db, edit_attempt.questionnaire_id)
            existing_answers = get_attempt_answers_map(db, edit_attempt.id)
            edited_answers: dict[int, str | None] = {}
            with st.form(f"edit_attempt_form_{edit_attempt.id}"):
                current_chapter = None
                for q in questions_edit:
                    chapter_label = q.chapitre or "Général"
                    if chapter_label != current_chapter:
                        st.markdown(f"**Chapitre : {chapter_label}**")
                        current_chapter = chapter_label
                    edited_answers[q.id] = st.text_input(
                        f"Q{q.numero} - {q.enonce or 'Sans énoncé'}",
                        value=existing_answers.get(q.id) or "",
                        key=f"edit_ans_{edit_attempt.id}_{q.id}",
                        help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                    )
                save_edit = st.form_submit_button("Enregistrer modifications", type="primary")
                cancel_edit = st.form_submit_button("Annuler")

            if cancel_edit:
                st.session_state.qcm_edit_attempt_id = None
                st.rerun()
            if save_edit:
                result = submit_attempt(db, edit_attempt.id, edited_answers)
                st.session_state.qcm_edit_attempt_id = None
                toast("success", f"Tentative mise à jour: {result.score_brut}/{result.total_questions}, note {result.note_sur_20}/20")
                st.rerun()

        attempt_id = st.session_state.qcm_attempt_id
        if attempt_id:
            attempt = get_attempt_detail(db, attempt_id)
            if attempt and attempt.questionnaire_id == questionnaire_id and attempt.stagiaire_id == stagiaire_id:
                questions = list_questions(db, questionnaire_id)
                st.markdown("#### Feuille de saisie")
                answers: dict[int, str | None] = {}
                with st.form("submit_attempt"):
                    current_chapter = None
                    for q in questions:
                        chapter_label = q.chapitre or "Général"
                        if chapter_label != current_chapter:
                            st.markdown(f"**Chapitre : {chapter_label}**")
                            current_chapter = chapter_label
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

        st.markdown("#### Modifier / Supprimer un passage")
        for a in attempts:
            c1, c2, c3 = st.columns([5, 1, 1])
            c1.write(f"#{a.id} — {a.stagiaire.nom} {a.stagiaire.prenom} — {a.questionnaire.titre} — {a.note_sur_20}/20")
            if c2.button("✏️", key=f"edit_attempt_{a.id}", help="Modifier cette tentative"):
                st.session_state.qcm_edit_attempt_id = a.id
                st.session_state.qcm_attempt_id = None
                st.rerun()
            if c3.button("🗑️", key=f"delete_attempt_{a.id}", help="Supprimer cette tentative"):
                delete_attempt(db, a.id)
                if st.session_state.qcm_edit_attempt_id == a.id:
                    st.session_state.qcm_edit_attempt_id = None
                if st.session_state.qcm_attempt_id == a.id:
                    st.session_state.qcm_attempt_id = None
                toast("success", "Passage supprimé")
                st.rerun()


def page_synthese_stagiaire() -> None:
    render_header("📊 Synthèse stagiaire", "Synthèse / Stagiaire")
    with SessionLocal() as db:
        trainees = load_trainees(db, "")
        if not trainees:
            st.warning("Aucun stagiaire disponible.")
            return

        default_id = None
        qp = st.query_params.get("summary_trainee")
        if qp and str(qp).isdigit():
            default_id = int(qp)
        trainee_ids = [t.id for t in trainees]
        index = trainee_ids.index(default_id) if default_id in trainee_ids else 0

        trainee_id = st.selectbox("Choisir un stagiaire", trainee_ids, index=index, format_func=lambda i: next(f"{t.nom} {t.prenom}" for t in trainees if t.id == i))
        trainee = next(t for t in trainees if t.id == trainee_id)

        summary = get_trainee_qcm_summary(db, trainee_id)
        stats = summary["stats"]

        if stats["total_attempts"] == 0:
            st.info("Ce stagiaire n'a encore passé aucun QCM.")
            st.markdown("➡️ **Action recommandée :** aller dans **QCM - Passages** puis cliquer sur *Démarrer une tentative*.")
            return

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tentatives", stats["total_attempts"])
        c2.metric("Questionnaires distincts", stats["distinct_questionnaires"])
        c3.metric("Moyenne /20", stats["average_note"])
        c4.metric("Taux bonnes réponses", f"{stats['global_correct_rate']}%")

        c5, c6, c7 = st.columns(3)
        c5.metric("Meilleure note", stats["best_note"])
        c6.metric("Pire note", stats["worst_note"])
        c7.metric("Dernière tentative", str(stats["last_attempt_date"]).split(".")[0] if stats["last_attempt_date"] else "-")

        # Charts
        chart_left, chart_right = st.columns(2)
        with chart_left:
            ci = summary["correct_incorrect"]
            fig1, ax1 = plt.subplots()
            ax1.pie([ci["correct"], ci["incorrect"]], labels=["Correctes", "Incorrectes"], autopct="%1.1f%%", startangle=90)
            ax1.set_title("Réponses correctes vs incorrectes")
            st.pyplot(fig1)

        with chart_right:
            attempts_chrono = list(reversed(summary["attempts"]))
            labels = [a.date_passage.strftime("%d/%m") for a in attempts_chrono]
            notes = [a.note_sur_20 for a in attempts_chrono]
            fig2, ax2 = plt.subplots()
            ax2.bar(labels, notes, color="#3b82f6")
            ax2.set_ylim(0, 20)
            ax2.set_title("Note /20 par tentative")
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Note")
            st.pyplot(fig2)

        st.markdown("#### Top 3 / Bottom 3 questionnaires")
        tcol, bcol = st.columns(2)
        tcol.dataframe(summary["top3"], use_container_width=True, hide_index=True)
        bcol.dataframe(summary["bottom3"], use_container_width=True, hide_index=True)

        st.markdown("#### Performance par chapitre")
        by_chapter = summary.get("by_chapter", [])
        if by_chapter:
            chap_labels = [x["chapitre"] for x in by_chapter]
            chap_rates = [x["taux"] for x in by_chapter]
            fig3, ax3 = plt.subplots()
            ax3.bar(chap_labels, chap_rates, color="#10b981")
            ax3.set_ylim(0, 100)
            ax3.set_ylabel("Taux de réussite (%)")
            ax3.set_title("Réussite par chapitre")
            plt.xticks(rotation=20, ha="right")
            st.pyplot(fig3)

            selected_chapter = st.selectbox("Chapitre (drill-down sous-chapitres)", chap_labels, key=f"summary_chapter_{trainee_id}")
            by_subchapter = aggregate_scores_by_subchapter(db, trainee_id, selected_chapter)
            sub_labels = [x["sous_chapitre"] for x in by_subchapter]
            sub_rates = [x["taux"] for x in by_subchapter]
            fig4, ax4 = plt.subplots()
            ax4.bar(sub_labels, sub_rates, color="#f59e0b")
            ax4.set_ylim(0, 100)
            ax4.set_ylabel("Taux de réussite (%)")
            ax4.set_title(f"Réussite par sous-chapitre — {selected_chapter}")
            plt.xticks(rotation=20, ha="right")
            st.pyplot(fig4)

            st.markdown("#### Tableau récapitulatif chapitre / sous-chapitre")
            st.dataframe(summary.get("by_subchapter", []), use_container_width=True, hide_index=True)

        st.markdown("#### Historique des tentatives")
        recap_rows = []
        for a in summary["attempts"]:
            recap_rows.append(
                {
                    "Date passage": a.date_passage,
                    "Questionnaire": a.questionnaire.titre,
                    "Score brut": f"{a.score_brut}/{a.total_questions}",
                    "Note /20": a.note_sur_20,
                    "Détail": f"attempt_id={a.id}",
                }
            )
        st.dataframe(recap_rows, use_container_width=True, hide_index=True)

        # ChatGPT block
        payload = {
            "stagiaire": {"id": trainee.id, "nom": trainee.nom, "prenom": trainee.prenom},
            "statistiques_globales": stats,
            "tentatives": [
                {
                    "date": a.date_passage.isoformat(),
                    "questionnaire": a.questionnaire.titre,
                    "score": {"brut": a.score_brut, "total": a.total_questions},
                    "note_sur_20": a.note_sur_20,
                }
                for a in summary["attempts"]
            ],
            "top3_questionnaires": summary["top3"],
            "bottom3_questionnaires": summary["bottom3"],
        }

        # Diagnostic JSON (pour identifier les objets non sérialisables)
        try:
            json.dumps(payload, ensure_ascii=False, indent=2)
        except TypeError:
            issue = find_first_non_serializable_path(payload)
            if issue:
                issue_path, issue_type = issue
                st.warning(f"Diagnostic sérialisation: {issue_path} -> {issue_type}")

        fallbacks: list[tuple[str, str, str]] = []

        def _on_fallback(path: str, typ: str, _value: str) -> None:
            fallbacks.append((path, typ, _value))

        payload_json = to_jsonable(payload, on_fallback=_on_fallback)

        try:
            payload_json_text = json.dumps(payload_json, ensure_ascii=False, indent=2)
        except TypeError:
            st.error("Certaines données n'ont pas pu être sérialisées proprement. Affichage simplifié activé.")
            payload_json_text = json.dumps(payload_json, ensure_ascii=False, indent=2, default=str)

        if fallbacks:
            st.warning(
                "Fallback de sérialisation appliqué pour: "
                + ", ".join(f"{path}({typ})" for path, typ, _ in fallbacks[:5])
            )

        prompt = (
            "Tu es un formateur expert. À partir des données ci-dessous, rédige :\n"
            "1) une synthèse courte (5-8 lignes),\n"
            "2) une synthèse détaillée,\n"
            "3) points forts / points à améliorer,\n"
            "4) 2 à 5 recommandations d'entraînement concrètes,\n"
            "5) un plan d'accompagnement.\n"
            "Contraintes: ton professionnel, adapté à un adulte en formation, factuel, sans jugement.\n"
            "Évite les jugements de valeur et propose un plan d'accompagnement progressif.\n\n"
            f"DONNÉES:\n{payload_json_text}"
        )

        st.markdown("#### Bloc ChatGPT (copier-coller)")
        st.text_area("Prompt prêt à l'emploi", value=prompt, height=360)
        st.caption("Copiez ce bloc dans ChatGPT pour générer automatiquement la synthèse.")


def page_help() -> None:
    render_header("📘 Aide", "Aide / Guide utilisateur")
    st.markdown("### Sommaire\n- Vue d'ensemble\n- Stagiaires\n- Sections\n- Formations\n- QCM\n- Synthèse\n- Import CSV\n- Sauvegarde / BDD")
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
    with st.expander("Synthèse stagiaire"):
        st.write("Affiche indicateurs QCM, graphiques, historique et bloc ChatGPT prêt à copier-coller.")

    st.markdown("### 📌 Cahier des charges")
    spec_path = Path("docs/SPEC.md")
    if spec_path.exists():
        st.markdown(spec_path.read_text(encoding="utf-8"))
    else:
        st.info("Cahier des charges non trouvé (docs/SPEC.md).")

    st.markdown("### 🧾 Historique des modifications")
    changelog_path = Path("docs/CHANGELOG.md")
    if changelog_path.exists():
        st.markdown(changelog_path.read_text(encoding="utf-8"))
    else:
        st.info("Historique non trouvé (docs/CHANGELOG.md).")


def page_tools() -> None:
    render_header("Outils", "Outils / Initialisation")

    if st.button("Initialiser la base", type="primary"):
        init_db()
        toast("success", "Base initialisée")

    st.markdown("---")
    st.markdown("### Sauvegarde / Restauration")

    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        st.warning("Sauvegarde/restauration indisponible: DATABASE_URL n'est pas une base SQLite locale.")
        return

    st.caption(f"Base active: {sqlite_path}")

    c1, c2 = st.columns([1, 2])
    if c1.button("Créer une sauvegarde", key="create_backup_btn"):
        try:
            backup_file = create_sqlite_backup()
            toast("success", f"Sauvegarde créée: {backup_file.name}")
            st.session_state["latest_backup_path"] = str(backup_file)
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur sauvegarde: {exc}")

    latest_backup = st.session_state.get("latest_backup_path")
    if latest_backup:
        backup_path = Path(latest_backup)
        if backup_path.exists():
            c2.download_button(
                "Télécharger la dernière sauvegarde",
                data=backup_path.read_bytes(),
                file_name=backup_path.name,
                mime="application/octet-stream",
                key="download_latest_backup",
            )

    backups = list_sqlite_backups()
    if backups:
        backup_map = {b.name: b for b in backups}
        selected_name = st.selectbox("Sauvegardes disponibles", list(backup_map.keys()), key="backup_select")
        confirm_restore = st.checkbox("Je confirme remplacer la base actuelle par cette sauvegarde", key="confirm_restore_file")
        if st.button("Restaurer la sauvegarde sélectionnée", key="restore_selected_backup"):
            if not confirm_restore:
                st.warning("Veuillez confirmer la restauration.")
            else:
                try:
                    restore_sqlite_backup(backup_map[selected_name])
                    toast("success", f"Base restaurée depuis {selected_name}")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Erreur restauration: {exc}")

    st.markdown("#### Restaurer depuis un fichier local")
    uploaded_backup = st.file_uploader("Importer un fichier .db de sauvegarde", type=["db"], key="upload_backup_db")
    confirm_upload_restore = st.checkbox("Je confirme remplacer la base actuelle avec ce fichier", key="confirm_restore_upload")
    if st.button("Restaurer le fichier importé", key="restore_uploaded_backup"):
        if not uploaded_backup:
            st.warning("Aucun fichier sélectionné.")
        elif not confirm_upload_restore:
            st.warning("Veuillez confirmer la restauration.")
        else:
            with NamedTemporaryFile(delete=False, suffix=".db") as tmp:
                tmp.write(uploaded_backup.getvalue())
                tmp_path = Path(tmp.name)
            try:
                restore_sqlite_backup(tmp_path)
                toast("success", "Base restaurée depuis le fichier importé")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Erreur restauration: {exc}")
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()


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
            "Synthèse": [
                st.Page(page_synthese_stagiaire, title="📊 Synthèse stagiaire", icon="📊"),
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
        [
            "Stagiaires",
            "Sections",
            "Formations",
            "QCM - Questionnaires",
            "QCM - Passages",
            "📊 Synthèse stagiaire",
            "Import CSV",
            "📘 Aide",
            "Init DB",
            "À propos",
            "Préférences",
        ],
    )
    {
        "Stagiaires": page_stagiaires,
        "Sections": page_sections,
        "Formations": page_formations,
        "QCM - Questionnaires": page_qcm_questionnaires,
        "QCM - Passages": page_qcm_passages,
        "📊 Synthèse stagiaire": page_synthese_stagiaire,
        "Import CSV": page_import_csv,
        "📘 Aide": page_help,
        "Init DB": page_tools,
        "À propos": page_about,
        "Préférences": page_preferences,
    }[choice]()
