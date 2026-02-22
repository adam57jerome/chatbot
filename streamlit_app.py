from __future__ import annotations

import csv
import json
from datetime import date
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, TypeVar

import pandas as pd
import streamlit as st
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import crud
from app.auth import is_auth_enabled, verify_credentials
from charts.radar import build_radar_figure
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
    get_attempt_review_rows,
    get_attempt_total_possible_points,
    get_trainee_qcm_summary,
    list_attempts,
    list_questionnaires,
    list_questions,
    normalize_answer,
    parse_possible_answers,
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
from app.utils.mailer import is_email_enabled, send_qcm_result_email
from app.utils.paper_export import (
    build_attempt_review_html,
    build_attempt_review_pdf_bytes,
    build_questionnaire_paper_html,
    build_questionnaire_scan_html,
)
from ui.layout import (
    get_role_ui_preset,
    inject_app_css,
    render_context_actions,
    render_header,
    render_onboarding,
    render_page_assistant,
    toast,
)

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
    "edit_question_id": None,
    "edit_question_questionnaire_id": None,
    "ui_show_trainee_table": True,
    "ui_show_trainee_actions": True,
    "ui_show_attempt_history": True,
    "ui_show_attempt_actions": True,
    "ui_attempt_page": 1,
    "ui_attempt_rows_per_page": 10,
    "ui_attempt_detail_mode": "Détail complet",
    "ui_show_section_table": True,
    "ui_show_section_actions": True,
    "ui_show_formation_table": True,
    "ui_show_formation_actions": True,
    "ui_show_qcm_questions_table": True,
    "ui_show_qcm_editor": True,
    "ui_density": "Confort",
    "ui_compact_tables": False,
    "ui_role_profile": "Admin",
    "auth_ok": False,
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
    render_page_assistant([
        "1) Filtrer/rechercher un stagiaire.",
        "2) Créer ou modifier sa fiche.",
        "3) Ouvrir sa synthèse QCM si nécessaire.",
    ])
    render_onboarding("stagiaires", [
        "Le bloc Filtres & affichage permet de simplifier la vue.",
        "Le formulaire ne s'affiche que pendant création/modification.",
        "Utilisez Actions rapides pour accéder à la synthèse QCM.",
    ])
    with SessionLocal() as db:
        with st.expander("🔎 Filtres & affichage", expanded=True):
            q = st.text_input("Recherche", key="q_trainees")
            fcol1, fcol2 = st.columns(2)
            fcol1.checkbox("Afficher le tableau", key="ui_show_trainee_table")
            fcol2.checkbox("Afficher les actions rapides", key="ui_show_trainee_actions")

        trainees = load_trainees(db, q)
        sections = load_sections(db)
        formations = load_formations(db, active_only=True)

        k1, k2, k3 = st.columns(3)
        k1.metric("Stagiaires", len(trainees))
        k2.metric("Sections", len(sections))
        k3.metric("Formations actives", len(formations))

        action_col, hint_col = st.columns([1, 3])
        if action_col.button("+ Nouveau stagiaire", type="primary"):
            st.session_state.trainee_screen = "create"
            st.rerun()
        hint_col.caption("Astuce: utilisez les actions rapides pour modifier un profil ou ouvrir la synthèse QCM.")

        if st.session_state.trainee_screen in {"create", "edit"}:
            with st.expander("🧾 Formulaire stagiaire", expanded=True):
                if st.session_state.trainee_screen == "create":
                    render_trainee_form(db=db, mode="create", sections=sections, formations=formations)
                else:
                    trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
                    if not trainee:
                        toast("warning", "Stagiaire introuvable")
                        st.session_state.trainee_screen = "list"
                        st.session_state.edit_trainee_id = None
                        st.rerun()
                    render_trainee_form(db=db, mode="edit", sections=sections, formations=formations, trainee=trainee)

        if st.session_state.get("ui_show_trainee_table", True):
            with st.expander("📋 Liste des stagiaires", expanded=True):
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

        if st.session_state.get("ui_show_trainee_actions", True):
            with st.expander("⚡ Actions rapides", expanded=True):
                for trainee in trainees:
                    cols = st.columns([3, 1, 1])
                    cols[0].write(f"{trainee.nom} {trainee.prenom}")
                    if cols[1].button("✏️ Modifier", key=f"edit_trainee_btn_{trainee.id}"):
                        st.session_state.trainee_screen = "edit"
                        st.session_state.edit_trainee_id = trainee.id
                        st.rerun()
                    if cols[2].button("Voir synthèse QCM", key=f"summary_btn_{trainee.id}"):
                        st.query_params.update({"summary_trainee": str(trainee.id)})
                        st.info("Allez dans Synthèse > 📊 Synthèse stagiaire (stagiaire présélectionné).")


def page_sections() -> None:
    render_header("Gestion des sections", "Gestion / Sections")
    render_page_assistant([
        "1) Filtrer les sections et vérifier les effectifs.",
        "2) Créer ou modifier la section.",
        "3) Gérer les affectations stagiaires.",
    ])
    render_onboarding("sections", [
        "Utilisez les filtres pour réduire la liste.",
        "Le bouton + Nouvelle section est toujours disponible en haut.",
        "Passez par l'action 👥 pour gérer les affectations.",
    ])
    with SessionLocal() as db:
        with st.expander("🔎 Filtres & affichage", expanded=True):
            query = st.text_input("Recherche section", key="q_sections")
            cfa, cfb = st.columns(2)
            cfa.checkbox("Afficher le tableau", key="ui_show_section_table")
            cfb.checkbox("Afficher les actions", key="ui_show_section_actions")

        sections, _total = crud.list_sections(db, q=query, page=1, per_page=500)
        k1, k2 = st.columns(2)
        k1.metric("Sections", len(sections))
        k2.metric("Stagiaires affectés", sum(len(s.stagiaires) for s in sections))

        clicked_action = render_context_actions([
            ("new_section", "+ Nouvelle section", "primary"),
        ])
        if clicked_action == "new_section":
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

            with st.expander("🧾 Formulaire section", expanded=True):
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

        if st.session_state.get("ui_show_section_table", True):
            with st.expander("📋 Liste des sections", expanded=True):
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

        if st.session_state.get("ui_show_section_actions", True):
            with st.expander("⚡ Actions", expanded=True):
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
                with st.expander(f"👥 Affectations — {section.code} / {section.nom}", expanded=True):
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
    render_page_assistant([
        "1) Filtrer par statut actif/inactif.",
        "2) Créer ou mettre à jour une formation.",
        "3) Nettoyer les formations obsolètes si besoin.",
    ])
    render_onboarding("formations", [
        "Le mode Compact réduit la densité visuelle si vous gérez beaucoup de lignes.",
        "Utilisez le filtre de statut pour isoler les formations inactives.",
        "Les actions d'édition/suppression sont regroupées dans la section Actions.",
    ])
    with SessionLocal() as db:
        with st.expander("🔎 Filtres & affichage", expanded=True):
            query = st.text_input("Recherche formation", key="q_formations")
            active_filter = st.selectbox(
                "Statut",
                ["Toutes", "Actives", "Inactives"],
                key="formation_status_filter",
            )
            fc1, fc2 = st.columns(2)
            fc1.checkbox("Afficher le tableau", key="ui_show_formation_table")
            fc2.checkbox("Afficher les actions", key="ui_show_formation_actions")

        actif_filter = {"Toutes": None, "Actives": "active", "Inactives": "inactive"}[active_filter]
        formations, _total = crud.list_formations(db, q=query, actif_filter=actif_filter, page=1, per_page=500)
        m1, m2 = st.columns(2)
        m1.metric("Formations", len(formations))
        m2.metric("Actives", len([f for f in formations if f.actif]))

        clicked_action = render_context_actions([
            ("new_formation", "+ Nouvelle formation", "primary"),
        ])
        if clicked_action == "new_formation":
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

            with st.expander("🧾 Formulaire formation", expanded=True):
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

        if st.session_state.get("ui_show_formation_table", True):
            with st.expander("📋 Liste des formations", expanded=True):
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

        if st.session_state.get("ui_show_formation_actions", True):
            with st.expander("⚡ Actions", expanded=True):
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
    render_page_assistant([
        "1) Déposer un CSV et vérifier l'aperçu.",
        "2) Mapper les colonnes et choisir la stratégie.",
        "3) Lancer l'import puis télécharger le rapport.",
    ])
    render_onboarding("import_csv", [
        "Commencez par vérifier séparateur/encodage.",
        "Le mapping est obligatoire pour nom et prénom.",
        "Téléchargez le rapport en fin d'import pour audit.",
    ])

    with st.expander("⚙️ Paramètres d'import", expanded=True):
        upload = st.file_uploader("Fichier CSV", type=["csv"])
        p1, p2, p3 = st.columns(3)
        sep_choice = p1.selectbox("Séparateur", ["auto", ",", ";", "	"], help=HELP_TEXTS["import_separator"])
        encoding_choice = p2.selectbox("Encodage", ["auto", "utf-8", "latin-1"], help=HELP_TEXTS["import_encoding"])
        has_header = p3.checkbox("Le fichier a une ligne d'en-tête", value=True)
    if not upload:
        return

    df = parse_csv(upload.getvalue(), sep=sep_choice, encoding=encoding_choice, has_header=has_header)
    k1, k2 = st.columns(2)
    k1.metric("Lignes détectées", len(df))
    k2.metric("Colonnes détectées", len(df.columns))

    with st.expander("👀 Aperçu & mapping", expanded=True):
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
    render_page_assistant([
        "1) Créer ou sélectionner un questionnaire.",
        "2) Ajouter/éditer les questions avec filtres chapitre/sous-chapitre.",
        "3) Exporter (CSV/papier/scan) ou importer en lot.",
    ])
    render_onboarding("qcm_questionnaires", [
        "Créez un questionnaire puis ajoutez des questions dans le bloc dédié.",
        "Activez/désactivez les blocs d'affichage via les checkboxes en haut.",
        "Les exports CSV/papier/scan sont disponibles en bas de page.",
    ])
    with SessionLocal() as db:
        with st.expander("🔎 Filtres & affichage", expanded=True):
            q = st.text_input("Recherche titre", key="q_qcm")
            qc1, qc2 = st.columns(2)
            qc1.checkbox("Afficher la table questionnaires", key="ui_show_qcm_questions_table")
            qc2.checkbox("Afficher le bloc édition question", key="ui_show_qcm_editor")
        questionnaires = list_questionnaires(db, q)

        st.metric("Questionnaires", len(questionnaires))

        with st.expander("🧾 Nouveau questionnaire", expanded=False):
            with st.form("new_qcm"):
                titre = st.text_input("Titre questionnaire *")
                description = st.text_area("Description")
                create_btn = st.form_submit_button("Créer questionnaire", type="primary")
            if create_btn and titre.strip():
                create_questionnaire(db, titre, description)
                toast("success", "Questionnaire créé")
                st.rerun()

        if st.session_state.get("ui_show_qcm_questions_table", True):
            with st.expander("📋 Liste des questionnaires", expanded=True):
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

            st.dataframe([{"ID": q.id, "Chapitre": q.chapitre, "Sous-chapitre": q.sous_chapitre or "Sans sous-chapitre", "N°": q.numero, "Attendu": q.resultat_attendu, "Points": q.points, "Réponses possibles": " | ".join(parse_possible_answers(q.reponses_possibles)) or "-", "Énoncé": q.enonce or "-"} for q in filtered_questions], use_container_width=True, hide_index=True)

            with st.form("add_question"):
                chapitre = st.text_input("Chapitre *", placeholder="Français, Mathématiques, ...")
                sous_chapitre = st.text_input("Sous-chapitre", placeholder="Optionnel")
                numero = st.number_input("Numéro", min_value=1, step=1, value=1)
                attendu = st.text_input("Résultat attendu *", placeholder="A ou A,C")
                enonce = st.text_area("Énoncé")
                possible_answers_text = st.text_area("Réponses possibles (une par ligne)", help="Nombre de réponses variable")
                points = st.number_input("Points", min_value=1, value=1)
                add_btn = st.form_submit_button("Ajouter question", type="primary")
            if add_btn:
                if not chapitre.strip():
                    st.error("Le chapitre est obligatoire.")
                elif not attendu.strip():
                    st.error("Le résultat attendu est obligatoire.")
                else:
                    possible_answers = [line.strip() for line in possible_answers_text.splitlines() if line.strip()]
                    add_question(db, selected_id, int(numero), attendu, enonce, int(points), chapitre, sous_chapitre, possible_answers)
                    toast("success", "Question ajoutée")
                    st.rerun()

            if st.session_state.get("ui_show_qcm_editor", True) and questions:
                st.markdown("#### Modifier une question")
                question_ids = [q.id for q in questions]

                # Règle Streamlit: ne pas modifier la clé du widget après instanciation.
                # On pilote la navigation avec edit_question_id (état métier), puis on synchronise
                # la clé fixe du widget AVANT de créer le selectbox.
                questionnaire_changed = st.session_state.edit_question_questionnaire_id != selected_id
                if questionnaire_changed or st.session_state.edit_question_id not in question_ids:
                    st.session_state.edit_question_questionnaire_id = selected_id
                    st.session_state.edit_question_id = question_ids[0]

                if st.session_state.get("edit_question_select") != st.session_state.edit_question_id:
                    st.session_state["edit_question_select"] = st.session_state.edit_question_id

                def _on_edit_question_select_change() -> None:
                    st.session_state.edit_question_id = st.session_state.get("edit_question_select")

                st.selectbox(
                    "Question à modifier",
                    question_ids,
                    format_func=lambda qid: next(
                        f"[{q.chapitre} / {q.sous_chapitre or 'Sans sous-chapitre'}] Q{q.numero} - {q.enonce or '-'}"
                        for q in questions if q.id == qid
                    ),
                    key="edit_question_select",
                    on_change=_on_edit_question_select_change,
                )

                editable_question_id = st.session_state.edit_question_id

                editable_question = next(q for q in questions if q.id == editable_question_id)
                with st.form(f"edit_question_{editable_question_id}"):
                    ec1, ec2 = st.columns(2)
                    e_chapitre = ec1.text_input("Chapitre *", value=editable_question.chapitre)
                    e_sous = ec2.text_input("Sous-chapitre", value=editable_question.sous_chapitre or "")
                    enumero = st.number_input("Numéro", min_value=1, step=1, value=int(editable_question.numero))
                    eattendu = st.text_input("Résultat attendu *", value=editable_question.resultat_attendu)
                    eenonce = st.text_area("Énoncé", value=editable_question.enonce or "")
                    e_possible = st.text_area("Réponses possibles (une par ligne)", value="\n".join(parse_possible_answers(editable_question.reponses_possibles)))
                    epoints = st.number_input("Points", min_value=1, value=int(editable_question.points))
                    save_q = st.form_submit_button("Mettre à jour la question")
                    delete_q = st.form_submit_button("Supprimer la question")

                if save_q:
                    if not e_chapitre.strip():
                        st.error("Le chapitre est obligatoire.")
                    elif not eattendu.strip():
                        st.error("Le résultat attendu est obligatoire.")
                    else:
                        try:
                            updated_question = update_question(
                                db,
                                editable_question_id,
                                int(enumero),
                                eattendu,
                                eenonce,
                                int(epoints),
                                e_chapitre,
                                e_sous,
                                [line.strip() for line in e_possible.splitlines() if line.strip()],
                            )
                            if not updated_question:
                                st.warning("Question introuvable, impossible de sauvegarder.")
                            else:
                                toast("success", "Question mise à jour")
                                st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
                if delete_q:
                    delete_question(db, editable_question_id)
                    remaining_ids = [qid for qid in question_ids if qid != editable_question_id]
                    st.session_state.edit_question_id = remaining_ids[0] if remaining_ids else None
                    toast("success", "Question supprimée")
                    st.rerun()

                nav_left, nav_right = st.columns(2)
                current_idx = question_ids.index(editable_question_id)
                if nav_left.button("⬅️ Question précédente", key="prev_question", disabled=current_idx == 0):
                    st.session_state.edit_question_id = question_ids[current_idx - 1]
                    st.rerun()
                if nav_right.button("Question suivante ➡️", key="next_question", disabled=current_idx == len(question_ids) - 1):
                    st.session_state.edit_question_id = question_ids[current_idx + 1]
                    st.rerun()
            elif st.session_state.get("ui_show_qcm_editor", True):
                st.info("Aucune question disponible pour l'édition.")

            st.markdown("#### Export des questions (.csv)")
            export_rows = [
                {
                    "questionnaire": selected.titre,
                    "numero": q.numero,
                    "resultat_attendu": q.resultat_attendu,
                    "chapitre": q.chapitre,
                    "sous_chapitre": q.sous_chapitre or "",
                    "reponses_possibles": "|".join(parse_possible_answers(q.reponses_possibles)),
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

            paper_rows = [
                {
                    "numero": q.numero,
                    "chapitre": q.chapitre,
                    "sous_chapitre": q.sous_chapitre or "",
                    "enonce": q.enonce or "",
                    "possible_answers": parse_possible_answers(q.reponses_possibles),
                }
                for q in questions
            ]
            paper_html = build_questionnaire_paper_html(selected.titre, paper_rows)
            scan_html = build_questionnaire_scan_html(selected.titre, paper_rows)
            dcol1, dcol2 = st.columns(2)
            dcol1.download_button(
                "Télécharger questionnaire papier (.html)",
                data=paper_html.encode("utf-8"),
                file_name=f"questionnaire_papier_{selected.id}.html",
                mime="text/html",
                key=f"download_questions_paper_{selected.id}",
                help="Ouvrez le fichier dans un navigateur puis imprimez-le pour un passage crayon/papier.",
            )
            dcol2.download_button(
                "Télécharger feuille scan optimisée (.html)",
                data=scan_html.encode("utf-8"),
                file_name=f"questionnaire_scan_{selected.id}.html",
                mime="text/html",
                key=f"download_questions_scan_{selected.id}",
                help="Mise en page A4 avec repères et cases pour faciliter le scan puis l'extraction CSV.",
            )

            st.markdown("#### Import rapide des questions")
            bulk = st.text_area("Format: numero;resultat_attendu;chapitre;sous_chapitre;enonce;reponses_possibles")
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
                    possible_answers_line = [p.strip() for p in (parts[5] if len(parts) > 5 else "").split("|") if p.strip()]
                    if not chapitre_line:
                        chapitre_line = "Général"
                    if not attendu_line:
                        rejected += 1
                        continue
                    add_question(db, selected_id, numero, attendu_line, enonce_line, 1, chapitre_line, sous_chapitre_line, possible_answers_line)
                    added += 1
                toast("success", f"{added} question(s) importée(s), {rejected} rejetée(s)")
                st.rerun()

            st.markdown("#### Importer questionnaire(s) depuis CSV")
            st.caption("Colonnes attendues: questionnaire;numero;resultat_attendu;chapitre;sous_chapitre;enonce;reponses_possibles;points (chapitre obligatoire, numero optionnel)")
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
                            possible_answers_line = [x.strip() for x in ((row.get("reponses_possibles") or "").split("|")) if x.strip()]
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
                            add_question(db, qcache[q_title], numero, attendu_line, enonce_line, points, chapitre_line, sous_chapitre_line, possible_answers_line)
                            added_qs += 1

                        toast("success", f"{created_q} questionnaire(s) créé(s), {added_qs} question(s) importée(s), {rejected} ligne(s) rejetée(s)")
                        st.rerun()


def page_qcm_passages() -> None:
    render_header("QCM - Passages / Saisie", "QCM / Passages")
    render_onboarding("qcm_passages", [
        "Commencez par préparer une tentative en haut de page.",
        "Les sections sont repliables pour garder une vue claire.",
        "Utilisez l'historique pour corriger ou supprimer un passage.",
    ])
    with SessionLocal() as db:
        trainees = load_trainees(db, "")
        questionnaires = list_questionnaires(db)
        if not trainees or not questionnaires:
            st.warning("Créer au moins un stagiaire et un questionnaire avant un passage.")
            return

        with st.expander("🎯 Préparer un passage", expanded=True):
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

            with st.expander(f"🛠️ Modifier tentative #{edit_attempt.id}", expanded=True):
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
                        question_label = f"Q{q.numero} - {q.enonce or 'Sans énoncé'}"
                        choices = parse_possible_answers(q.reponses_possibles)
                        expected_multi = "," in normalize_answer(q.resultat_attendu)
                        current_value = existing_answers.get(q.id) or ""
                        if choices and expected_multi:
                            default_multi = [x.strip() for x in current_value.split(",") if x.strip()]
                            selected_multi = st.multiselect(
                                question_label,
                                options=choices,
                                default=[x for x in default_multi if x in choices],
                                key=f"edit_ans_{edit_attempt.id}_{q.id}",
                                help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                            )
                            edited_answers[q.id] = ",".join(selected_multi)
                        elif choices:
                            options = [""] + choices
                            idx = options.index(current_value) if current_value in options else 0
                            selected_one = st.selectbox(
                                question_label,
                                options=options,
                                index=idx,
                                key=f"edit_ans_{edit_attempt.id}_{q.id}",
                                help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                            )
                            edited_answers[q.id] = selected_one or None
                        else:
                            edited_answers[q.id] = st.text_input(
                                question_label,
                                value=current_value,
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
                    toast("success", f"Tentative mise à jour: {result.score_brut}/{result.total_possible_points} points, note {result.note_sur_20}/20")
                    st.rerun()

        attempt_id = st.session_state.qcm_attempt_id
        if attempt_id:
            attempt = get_attempt_detail(db, attempt_id)
            if attempt and attempt.questionnaire_id == questionnaire_id and attempt.stagiaire_id == stagiaire_id:
                questions = list_questions(db, questionnaire_id)
                with st.expander("📝 Feuille de saisie", expanded=True):
                    answers: dict[int, str | None] = {}
                    with st.form("submit_attempt"):
                        current_chapter = None
                        for q in questions:
                            chapter_label = q.chapitre or "Général"
                            if chapter_label != current_chapter:
                                st.markdown(f"**Chapitre : {chapter_label}**")
                                current_chapter = chapter_label
                            question_label = f"Q{q.numero} - {q.enonce or 'Sans énoncé'}"
                            choices = parse_possible_answers(q.reponses_possibles)
                            expected_multi = "," in normalize_answer(q.resultat_attendu)
                            if choices and expected_multi:
                                selected_multi = st.multiselect(
                                    question_label,
                                    options=choices,
                                    key=f"ans_{attempt_id}_{q.id}",
                                    help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                                )
                                answers[q.id] = ",".join(selected_multi)
                            elif choices:
                                selected_one = st.selectbox(
                                    question_label,
                                    options=[""] + choices,
                                    key=f"ans_{attempt_id}_{q.id}",
                                    help=f"Attendu normalisé: {normalize_answer(q.resultat_attendu)}",
                                )
                                answers[q.id] = selected_one or None
                            else:
                                answers[q.id] = st.text_input(
                                    question_label,
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
                        toast("success", f"Corrigé: score {result.score_brut}/{result.total_possible_points} points, note {result.note_sur_20}/20")
                        st.rerun()

        with st.expander("📚 Historique des passages", expanded=True):
            hcol1, hcol2 = st.columns(2)
            hcol1.checkbox("Afficher le tableau des passages", key="ui_show_attempt_history")
            show_actions = hcol2.checkbox("Afficher les actions Modifier/Supprimer", value=True, key="ui_show_attempt_actions")
            f1, f2, f3 = st.columns(3)
            f_stagiaire = f1.selectbox("Filtre stagiaire", [0] + [t.id for t in trainees], format_func=lambda i: "Tous" if i == 0 else next(f"{t.nom} {t.prenom}" for t in trainees if t.id == i))
            f_q = f2.selectbox("Filtre questionnaire", [0] + [q.id for q in questionnaires], format_func=lambda i: "Tous" if i == 0 else next(q.titre for q in questionnaires if q.id == i))
            f_date = f3.date_input("Date", value=None)
            attempts = list_attempts(db, f_stagiaire or None, f_q or None, f_date if f_date else None)

            opt1, opt2 = st.columns(2)
            rows_per_page = opt1.selectbox("Lignes par page", [5, 10, 20, 50], index=[5, 10, 20, 50].index(st.session_state.get("ui_attempt_rows_per_page", 10)), key="ui_attempt_rows_per_page")
            detail_mode = opt2.selectbox("Mode affichage", ["Résumé compact", "Détail complet"], key="ui_attempt_detail_mode")

            total_attempts = len(attempts)
            total_pages = max((total_attempts + rows_per_page - 1) // rows_per_page, 1)
            if st.session_state.ui_attempt_page > total_pages:
                st.session_state.ui_attempt_page = total_pages
            nav1, nav2, nav3 = st.columns([1, 2, 1])
            if nav1.button("⬅️ Page précédente", disabled=st.session_state.ui_attempt_page <= 1):
                st.session_state.ui_attempt_page -= 1
                st.rerun()
            nav2.markdown(f"<div style='text-align:center;padding-top:8px'>Page {st.session_state.ui_attempt_page}/{total_pages}</div>", unsafe_allow_html=True)
            if nav3.button("Page suivante ➡️", disabled=st.session_state.ui_attempt_page >= total_pages):
                st.session_state.ui_attempt_page += 1
                st.rerun()

            start_idx = (st.session_state.ui_attempt_page - 1) * rows_per_page
            end_idx = start_idx + rows_per_page
            paged_attempts = attempts[start_idx:end_idx]

            if st.session_state.get("ui_show_attempt_history", True):
                st.dataframe(
                    [
                        {
                            "ID": a.id,
                            "Date": a.date_passage,
                            "Stagiaire": f"{a.stagiaire.nom} {a.stagiaire.prenom}",
                            "Questionnaire": a.questionnaire.titre,
                            "Score": f"{a.score_brut}/{get_attempt_total_possible_points(db, a.id)}",
                            "Note/20": a.note_sur_20,
                        }
                        for a in paged_attempts
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            if show_actions:
                st.markdown("#### Détail / Modifier / Supprimer un passage")
                for a in paged_attempts:
                    total_possible = get_attempt_total_possible_points(db, a.id)
                    title_cols = st.columns([4, 1])
                    title_cols[0].markdown(
                        f"**#{a.id} — {a.stagiaire.nom} {a.stagiaire.prenom} — {a.questionnaire.titre} — {a.score_brut}/{total_possible} pts — {a.note_sur_20}/20**"
                    )
                    detail_key = f"attempt_show_detail_{a.id}"
                    st.session_state.setdefault(detail_key, detail_mode == "Détail complet")
                    if title_cols[1].button(
                        "Afficher détail" if not st.session_state[detail_key] else "Masquer détail",
                        key=f"toggle_{a.id}",
                    ):
                        st.session_state[detail_key] = not st.session_state[detail_key]
                        st.rerun()

                    review_rows = get_attempt_review_rows(db, a.id)
                    only_errors = st.checkbox("Voir uniquement erreurs", key=f"attempt_only_errors_{a.id}")
                    rows_to_show = [r for r in review_rows if not r["correct"]] if only_errors else review_rows

                    if st.session_state[detail_key]:
                        st.dataframe(
                            [
                                {
                                    "Q": r["numero"],
                                    "Chapitre": r["chapitre"],
                                    "Énoncé": r["enonce"] or "-",
                                    "Attendu": r["attendu"] or "-",
                                    "Réponse stagiaire": r["reponse_stagiaire"] or "-",
                                    "Résultat": "OK" if r["correct"] else "KO",
                                    "Points": f"{r['points_obtenus']}/{r['points_max']}",
                                }
                                for r in rows_to_show
                            ],
                            use_container_width=True,
                            hide_index=True,
                        )

                    html_report = build_attempt_review_html(
                        attempt_id=a.id,
                        trainee_name=f"{a.stagiaire.nom} {a.stagiaire.prenom}",
                        questionnaire_title=a.questionnaire.titre,
                        note_sur_20=float(a.note_sur_20 or 0),
                        score_brut=int(a.score_brut or 0),
                        total_possible_points=total_possible,
                        rows=rows_to_show,
                    )
                    pdf_bytes = build_attempt_review_pdf_bytes(
                        attempt_id=a.id,
                        trainee_name=f"{a.stagiaire.nom} {a.stagiaire.prenom}",
                        questionnaire_title=a.questionnaire.titre,
                        note_sur_20=float(a.note_sur_20 or 0),
                        score_brut=int(a.score_brut or 0),
                        total_possible_points=total_possible,
                        rows=rows_to_show,
                    )

                    e1, e2 = st.columns(2)
                    e1.download_button(
                        "📄 Exporter résultat (HTML imprimable / PDF)",
                        data=html_report,
                        file_name=f"resultat_qcm_attempt_{a.id}.html",
                        mime="text/html",
                        key=f"export_attempt_html_{a.id}",
                        help="Ouvrez ce fichier dans le navigateur puis Imprimer > Enregistrer en PDF.",
                    )
                    e2.download_button(
                        "🧾 Télécharger PDF",
                        data=pdf_bytes,
                        file_name=f"resultat_qcm_attempt_{a.id}.pdf",
                        mime="application/pdf",
                        key=f"export_attempt_pdf_{a.id}",
                    )

                    trainee_email = (a.stagiaire.email or "").strip()
                    if trainee_email:
                        email_enabled = is_email_enabled()
                        if email_enabled:
                            if st.button("📧 Envoyer le PDF par email", key=f"email_attempt_{a.id}"):
                                try:
                                    send_qcm_result_email(
                                        to_email=trainee_email,
                                        subject=f"Résultat QCM - {a.questionnaire.titre}",
                                        body_text=(
                                            f"Bonjour {a.stagiaire.prenom},\n\n"
                                            f"Vous trouverez en pièce jointe votre résultat QCM (tentative #{a.id}).\n"
                                            f"Note: {a.note_sur_20}/20.\n"
                                        ),
                                        pdf_bytes=pdf_bytes,
                                        filename=f"resultat_qcm_attempt_{a.id}.pdf",
                                    )
                                    toast("success", f"Email envoyé à {trainee_email}")
                                except Exception as exc:
                                    st.error(f"Échec envoi email: {exc}")
                        else:
                            st.caption("Configurer SMTP_HOST et SMTP_FROM (optionnel) pour activer l'envoi email.")

                    c1, c2 = st.columns(2)
                    if c1.button("✏️ Modifier", key=f"edit_attempt_{a.id}", help="Modifier cette tentative"):
                        st.session_state.qcm_edit_attempt_id = a.id
                        st.session_state.qcm_attempt_id = None
                        st.rerun()
                    if c2.button("🗑️ Supprimer", key=f"delete_attempt_{a.id}", help="Supprimer cette tentative"):
                        delete_attempt(db, a.id)
                        if st.session_state.qcm_edit_attempt_id == a.id:
                            st.session_state.qcm_edit_attempt_id = None
                        if st.session_state.qcm_attempt_id == a.id:
                            st.session_state.qcm_attempt_id = None
                        toast("success", "Passage supprimé")
                        st.rerun()

                    st.divider()


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

        with st.expander("📌 Vue d'ensemble", expanded=True):
            st.markdown("#### Top 3 / Bottom 3 questionnaires")
            tcol, bcol = st.columns(2)
            tcol.dataframe(summary["top3"], use_container_width=True, hide_index=True)
            bcol.dataframe(summary["bottom3"], use_container_width=True, hide_index=True)

        with st.expander("🕸️ Radars par chapitre et sous-chapitre", expanded=True):
            chapter_scores = {
                row["chapitre"]: round((row["taux"] / 100) * 20, 1)
                for row in summary.get("by_chapter", [])
            }
            if not chapter_scores:
                st.info("Aucune donnée de chapitre disponible pour le radar.")
            else:
                radar_chapter = build_radar_figure(
                    chapter_scores,
                    f"Radar chapitres - {trainee.nom} {trainee.prenom}",
                    max_score=20,
                    tick_step=2,
                )
                st.plotly_chart(radar_chapter, use_container_width=True)

            st.markdown("#### Radar sous-chapitres")
            by_subchapter = summary.get("by_subchapter", [])
            if by_subchapter:
                chapter_options = ["Tous"] + sorted({row["chapitre"] for row in by_subchapter})
                selected_chapter = st.selectbox(
                    "Filtrer le radar sous-chapitres",
                    chapter_options,
                    key=f"summary_subchapter_chapter_{trainee_id}",
                )
                scoped_rows = (
                    by_subchapter
                    if selected_chapter == "Tous"
                    else [row for row in by_subchapter if row["chapitre"] == selected_chapter]
                )
                subchapter_scores = {
                    f"{row['chapitre']} / {row['sous_chapitre']}": round((row["taux"] / 100) * 20, 1)
                    for row in scoped_rows
                }
                radar_subchapter = build_radar_figure(
                    subchapter_scores,
                    f"Radar sous-chapitres - {trainee.nom} {trainee.prenom}",
                    max_score=20,
                    tick_step=2,
                )
                st.plotly_chart(radar_subchapter, use_container_width=True)

                st.markdown("#### Tableau récapitulatif chapitre / sous-chapitre")
                st.dataframe(scoped_rows, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune donnée de sous-chapitre disponible pour le radar.")

            if chapter_scores:
                col_png, col_html = st.columns(2)
                if col_png.button("Télécharger radar chapitres.png", key=f"radar_chapter_png_{trainee_id}"):
                    try:
                        png_bytes = radar_chapter.to_image(format="png", width=1000, height=700, scale=2)
                        st.download_button(
                            "Confirmer téléchargement PNG",
                            data=png_bytes,
                            file_name=f"radar_chapitres_{trainee_id}.png",
                            mime="image/png",
                            key=f"dl_radar_chapter_png_{trainee_id}",
                        )
                    except Exception:
                        st.warning("Export PNG indisponible (installer kaleido). Utilisez l'export HTML.")

                html_content = radar_chapter.to_html(full_html=True, include_plotlyjs="cdn")
                col_html.download_button(
                    "Télécharger radar chapitres.html",
                    data=html_content,
                    file_name=f"radar_chapitres_{trainee_id}.html",
                    mime="text/html",
                    key=f"dl_radar_chapter_html_{trainee_id}",
                )

        with st.expander("🕘 Historique des tentatives", expanded=False):
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
    render_page_assistant([
        "1) Lire le sommaire et ouvrir le module concerné.",
        "2) Copier l'exemple CSV si vous préparez un import.",
        "3) Consulter SPEC/CHANGELOG en bas de page.",
    ])
    render_onboarding("help", [
        "Les sections sont en accordéons pour aller à l'essentiel.",
        "Le bloc Import CSV contient un exemple prêt à copier.",
        "SPEC et CHANGELOG sont affichés dans les deux derniers blocs.",
    ])

    st.metric("Rubriques d'aide", len(AIDE_SECTIONS))
    with st.expander("📚 Sommaire & guides", expanded=True):
        st.markdown("""### Sommaire
- Vue d'ensemble
- Stagiaires
- Sections
- Formations
- QCM
- Synthèse
- Import CSV
- Sauvegarde / BDD""")
        section_order = [
            "overview",
            "stagiaires",
            "sections",
            "formations",
            "qcm",
            "synthese",
            "import_csv",
            "database",
        ]
        section_titles = {
            "overview": "Vue d'ensemble",
            "stagiaires": "Stagiaires",
            "sections": "Sections",
            "formations": "Formations",
            "qcm": "QCM",
            "synthese": "Synthèse stagiaire",
            "import_csv": "Import CSV",
            "database": "Sauvegarde / Base de données",
        }
        for key in section_order:
            content = AIDE_SECTIONS.get(key)
            if not content:
                continue
            with st.expander(section_titles[key]):
                st.write(content)
                if key == "import_csv":
                    st.code(CSV_EXAMPLE, language="csv")

    with st.expander("📌 Cahier des charges", expanded=False):
        spec_path = Path("docs/SPEC.md")
        if spec_path.exists():
            st.markdown(spec_path.read_text(encoding="utf-8"))
        else:
            st.info("Cahier des charges non trouvé (docs/SPEC.md).")

    with st.expander("🧾 Historique des modifications", expanded=False):
        changelog_path = Path("docs/CHANGELOG.md")
        if changelog_path.exists():
            st.markdown(changelog_path.read_text(encoding="utf-8"))
        else:
            st.info("Historique non trouvé (docs/CHANGELOG.md).")


def page_tools() -> None:
    render_header("Outils", "Outils / Initialisation")

    with st.expander("🧰 Maintenance rapide", expanded=True):
        st.caption("Actions sensibles: pensez à sauvegarder avant toute restauration.")
        if st.button("Initialiser la base", type="primary"):
            init_db()
            toast("success", "Base initialisée")

    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        st.warning("Sauvegarde/restauration indisponible: DATABASE_URL n'est pas une base SQLite locale.")
        return

    with st.expander("💾 Sauvegarde", expanded=True):
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

    with st.expander("♻️ Restaurer une sauvegarde", expanded=False):
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
        else:
            st.info("Aucune sauvegarde locale disponible.")

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
    with st.expander("🎨 Confort d'affichage", expanded=True):
        selected_role = st.selectbox("Profil UI", ["Admin", "Formateur"], key="ui_role_profile")
        st.radio("Densité globale", ["Confort", "Compact"], key="ui_density", horizontal=True)
        st.checkbox("Tableaux compacts", key="ui_compact_tables")
        if st.button("Appliquer le preset du profil", key="apply_role_ui_preset"):
            preset = get_role_ui_preset(selected_role)
            for preset_key, preset_value in preset.items():
                st.session_state[preset_key] = preset_value
            toast("success", f"Preset {selected_role} appliqué")
            st.rerun()
        if st.button("Appliquer l'affichage", key="apply_ui_preferences"):
            toast("success", "Préférences d'affichage appliquées")
            st.rerun()

    with st.expander("🗂️ Informations techniques", expanded=False):
        if db := get_sqlite_db_path():
            st.code(db, language="text")


def ensure_streamlit_auth() -> None:
    if not is_auth_enabled():
        return

    if st.session_state.get("auth_ok"):
        if st.sidebar.button("🔒 Se déconnecter", key="streamlit_logout"):
            st.session_state.auth_ok = False
            st.rerun()
        return

    st.markdown("## 🔐 Connexion")
    st.info("Veuillez vous authentifier pour accéder à l'application.")
    with st.form("streamlit_login_form"):
        username = st.text_input("Utilisateur")
        password = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter", type="primary")
    if submit:
        if verify_credentials(username, password):
            st.session_state.auth_ok = True
            toast("success", "Connexion réussie")
            st.rerun()
        else:
            st.error("Identifiants invalides.")
    st.stop()


ensure_streamlit_auth()
init_db()
inject_app_css()

if hasattr(st, "navigation") and hasattr(st, "Page"):
    nav = st.navigation(
        {
            "Gestion": [
                st.Page(page_stagiaires, title="Stagiaires", icon="👨‍🎓"),
                st.Page(page_sections, title="Sections", icon="🏫"),
                st.Page(page_formations, title="Formations", icon="🎓"),
            ],
            "QCM": [
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
