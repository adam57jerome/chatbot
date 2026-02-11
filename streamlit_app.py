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
from app.models import Formation, Section, Stagiaire
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

st.session_state.setdefault("trainee_screen", "list")
st.session_state.setdefault("edit_trainee_id", None)
st.session_state.setdefault("section_screen", "list")
st.session_state.setdefault("edit_section_id", None)
st.session_state.setdefault("formation_screen", "list")
st.session_state.setdefault("edit_formation_id", None)


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


def set_trainee_screen(screen: str, trainee_id: int | None = None) -> None:
    st.session_state.trainee_screen = screen
    st.session_state.edit_trainee_id = trainee_id


def set_section_screen(screen: str, section_id: int | None = None) -> None:
    st.session_state.section_screen = screen
    st.session_state.edit_section_id = section_id


def set_formation_screen(screen: str, formation_id: int | None = None) -> None:
    st.session_state.formation_screen = screen
    st.session_state.edit_formation_id = formation_id


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

        orient_left, orient_right = st.columns(2)
        section_label = orient_left.selectbox("Section", section_labels, index=section_labels.index(default_section), help=HELP_TEXTS["section"])
        formation_label = orient_right.selectbox("Formation souhaitée", formation_labels, index=formation_labels.index(default_formation), help=HELP_TEXTS["formation"])
        notes = st.text_area("Notes", value=trainee.notes or "" if trainee else "")

        primary, secondary = st.columns([1, 1])
        save = primary.form_submit_button("💾 Enregistrer", type="primary")
        cancel = secondary.form_submit_button("Annuler")

        if cancel:
            set_trainee_screen("list")
            st.rerun()

        if save:
            section_id = section_options[section_label]
            formation_id = formation_options[formation_label]
            field_errors: list[str] = []
            if not nom.strip():
                field_errors.append("Le nom est obligatoire.")
            if not prenom.strip():
                field_errors.append("Le prénom est obligatoire.")
            if section_id is not None and not crud.get_section_by_id(db, section_id):
                field_errors.append("La section sélectionnée n'existe pas.")
            if formation_id is not None and not crud.get_formation_by_id(db, formation_id):
                field_errors.append("La formation sélectionnée n'existe pas.")
            if field_errors:
                st.error("\n".join(field_errors))
                st.markdown("</div>", unsafe_allow_html=True)
                return

            try:
                payload = StagiaireUpdate(
                    nom=nom, prenom=prenom, email=email or None, telephone=telephone or None,
                    notes=notes or None, section_id=section_id, formation_souhaitee_id=formation_id
                )
                if is_edit and trainee is not None:
                    if not crud.update_trainee(db, trainee.id, payload):
                        st.error("Stagiaire introuvable.")
                        st.markdown("</div>", unsafe_allow_html=True)
                        return
                    toast("success", "Stagiaire mis à jour")
                else:
                    crud.create_stagiaire(db, StagiaireCreate(**payload.model_dump()))
                    toast("success", "Stagiaire créé")
                set_trainee_screen("list")
                st.rerun()
            except ValidationError as exc:
                st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
            except IntegrityError:
                db.rollback()
                st.error("Erreur: email déjà utilisé.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_section_form(*, db, mode: str, section: Section | None = None) -> None:
    is_edit = mode == "edit"
    section_id = section.id if section else None
    if is_edit and not section:
        st.error("Section introuvable.")
        set_section_screen("list")
        return

    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {'Modifier section' if is_edit else 'Nouvelle section'}")
    with st.form(f"section_form_{mode}_{section_id or 'new'}"):
        left, right = st.columns(2)
        code = left.text_input("Code *", value=section.code if section else "")
        nom = right.text_input("Nom *", value=section.nom if section else "")
        has_date_debut = left.checkbox("Date début", value=section.date_debut is not None if section else False)
        has_date_fin = right.checkbox("Date fin", value=section.date_fin is not None if section else False, help=HELP_TEXTS["dates"])
        date_debut = left.date_input("Date début", value=section.date_debut or date.today() if section else date.today(), disabled=not has_date_debut)
        date_fin = right.date_input("Date fin", value=section.date_fin or date.today() if section else date.today(), disabled=not has_date_fin)
        description = st.text_area("Description", value=section.description or "" if section else "")

        save = st.form_submit_button("💾 Enregistrer", type="primary")
        cancel = st.form_submit_button("Annuler")
        if cancel:
            set_section_screen("list")
            st.rerun()
        if save:
            try:
                payload = (SectionUpdate if is_edit else SectionCreate)(
                    code=code, nom=nom, date_debut=date_debut if has_date_debut else None,
                    date_fin=date_fin if has_date_fin else None, description=description or None,
                )
                if is_edit and section_id is not None:
                    if not crud.update_section(db, section_id, payload):
                        st.error("Section introuvable.")
                        st.markdown("</div>", unsafe_allow_html=True)
                        return
                    toast("success", "Section mise à jour")
                else:
                    crud.create_section(db, payload)
                    toast("success", "Section créée")
                set_section_screen("list")
                st.rerun()
            except ValidationError as exc:
                st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
            except IntegrityError:
                db.rollback()
                st.error("Erreur: code section déjà utilisé.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_formation_form(*, db, mode: str, formation: Formation | None = None) -> None:
    is_edit = mode == "edit"
    formation_id = formation.id if formation else None
    if is_edit and not formation:
        st.error("Formation introuvable.")
        set_formation_screen("list")
        return

    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {'Modifier formation' if is_edit else 'Nouvelle formation'}")
    with st.form(f"formation_form_{mode}_{formation_id or 'new'}"):
        left, right = st.columns(2)
        code = left.text_input("Code *", value=formation.code if formation else "")
        nom = right.text_input("Nom *", value=formation.nom if formation else "")
        actif = left.checkbox("Active", value=formation.actif if formation else True)
        description = st.text_area("Description", value=formation.description or "" if formation else "")
        save = st.form_submit_button("💾 Enregistrer", type="primary")
        cancel = st.form_submit_button("Annuler")
        if cancel:
            set_formation_screen("list")
            st.rerun()
        if save:
            try:
                payload = (FormationUpdate if is_edit else FormationCreate)(code=code, nom=nom, description=description or None, actif=actif)
                if is_edit and formation_id is not None:
                    if not crud.update_formation(db, formation_id, payload):
                        st.error("Formation introuvable.")
                        st.markdown("</div>", unsafe_allow_html=True)
                        return
                    toast("success", "Formation mise à jour")
                else:
                    crud.create_formation(db, payload)
                    toast("success", "Formation créée")
                set_formation_screen("list")
                st.rerun()
            except ValidationError as exc:
                st.error("Validation: " + ", ".join(err["msg"] for err in exc.errors()))
            except IntegrityError:
                db.rollback()
                st.error("Erreur: code formation déjà utilisé.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_section_assignments(db, section_id: int) -> None:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("#### Affectation des stagiaires")
    include_other = st.checkbox("Inclure stagiaires d'autres sections", value=True, key=f"include_other_{section_id}")
    in_section = crud.list_trainees_in_section(db, section_id)
    available = crud.list_trainees_available_for_section(db, section_id, include_other_sections=include_other)

    col_in, col_av = st.columns(2)
    with col_in:
        st.markdown("**Dans cette section**")
        for trainee in in_section:
            row = st.columns([3, 1])
            row[0].write(f"{trainee.nom} {trainee.prenom}")
            if row[1].button("Retirer", key=f"unassign_{section_id}_{trainee.id}"):
                crud.unassign_trainee(db, trainee.id)
                toast("success", f"{trainee.prenom} retiré")
                st.rerun()

    with col_av:
        st.markdown("**Disponibles**")
        for trainee in available:
            row = st.columns([3, 1])
            row[0].write(f"{trainee.nom} {trainee.prenom}")
            if row[1].button("Ajouter", key=f"assign_{section_id}_{trainee.id}"):
                crud.assign_trainee_to_section(db, trainee.id, section_id)
                toast("success", f"{trainee.prenom} ajouté")
                st.rerun()

    confirm = st.checkbox("Je confirme la suppression", key=f"confirm_delete_{section_id}", help=HELP_TEXTS["delete"])
    if st.button("🗑️ Supprimer la section", disabled=not confirm, key=f"delete_{section_id}", help=HELP_TEXTS["delete"]):
        if crud.delete_section_safely(db, section_id):
            toast("success", "Section supprimée")
            set_section_screen("list")
            st.rerun()
        st.error("Section introuvable")
    st.markdown("</div>", unsafe_allow_html=True)


def page_stagiaires() -> None:
    render_header("Gestion des stagiaires", "Gestion / Stagiaires", actions=[("+ Nouveau", lambda: set_trainee_screen("create"))])
    st.info("ℹ️ Astuce: utilisez l'email pour éviter les doublons et faciliter les mises à jour CSV.")
    with SessionLocal() as db:
        st.markdown("<div class='app-toolbar'>", unsafe_allow_html=True)
        q = st.text_input("Recherche (nom, prénom, email)", key="q_trainees")
        st.markdown("</div>", unsafe_allow_html=True)

        trainees = load_trainees(db, q)
        sections = load_sections(db)
        formations = load_formations(db, active_only=True)

        if st.session_state.trainee_screen == "edit":
            trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
            render_trainee_form(db=db, mode="edit", sections=sections, formations=formations, trainee=trainee)
        elif st.session_state.trainee_screen == "create":
            render_trainee_form(db=db, mode="create", sections=sections, formations=formations)

        st.dataframe([
            {
                "Nom": t.nom, "Prénom": t.prenom, "Email": t.email or "-", "Section": t.section.code if t.section else "Aucune",
                "Formation souhaitée": t.formation_souhaitee.code if t.formation_souhaitee else "Aucune",
            }
            for t in trainees
        ], use_container_width=True, hide_index=True)


def page_sections() -> None:
    render_header("Gestion des sections", "Gestion / Sections", actions=[("+ Nouvelle", lambda: set_section_screen("create"))])
    with SessionLocal() as db:
        q_section = st.text_input("Recherche (code/nom)", key="q_sections")
        sections = load_sections(db)
        if q_section:
            needle = q_section.lower().strip()
            sections = [s for s in sections if needle in s.code.lower() or needle in s.nom.lower()]
        if st.session_state.section_screen == "edit":
            section = crud.get_section_by_id(db, st.session_state.edit_section_id)
            render_section_form(db=db, mode="edit", section=section)
            if section:
                render_section_assignments(db, section.id)
        elif st.session_state.section_screen == "create":
            render_section_form(db=db, mode="create")
        st.dataframe([{"Code": s.code, "Nom": s.nom, "Stagiaires": len(s.stagiaires)} for s in sections], use_container_width=True, hide_index=True)


def page_formations() -> None:
    render_header("Gestion des formations", "Gestion / Formations", actions=[("+ Nouvelle", lambda: set_formation_screen("create"))])
    with SessionLocal() as db:
        q = st.text_input("Recherche (code/nom)", key="q_formations")
        active_filter = st.selectbox("Filtre actif", ["Toutes", "Actives", "Inactives"], key="formation_actif_filter")
        mapped = {"Toutes": None, "Actives": "active", "Inactives": "inactive"}
        formations, _ = crud.list_formations(db, q=q, actif_filter=mapped[active_filter], page=1, per_page=500)

        if st.session_state.formation_screen == "edit":
            formation = crud.get_formation_by_id(db, st.session_state.edit_formation_id)
            render_formation_form(db=db, mode="edit", formation=formation)
        elif st.session_state.formation_screen == "create":
            render_formation_form(db=db, mode="create")

        st.dataframe([{"Code": f.code, "Nom": f.nom, "Actif": "Oui" if f.actif else "Non"} for f in formations], use_container_width=True, hide_index=True)


def page_import_csv() -> None:
    render_header("Import CSV", "Outils / Import CSV")
    st.info("ℹ️ Importez vos stagiaires avec prévisualisation, mapping et rapport téléchargeable.")

    upload = st.file_uploader("Fichier CSV", type=["csv"], help="Choisir un fichier .csv")
    sep_choice = st.selectbox("Séparateur", ["auto", ",", ";", "\t"], help=HELP_TEXTS["import_separator"])
    encoding_choice = st.selectbox("Encodage", ["auto", "utf-8", "latin-1"], help=HELP_TEXTS["import_encoding"])
    has_header = st.checkbox("Le fichier a une ligne d'en-tête", value=True)

    if not upload:
        return

    raw = upload.getvalue()
    try:
        df = parse_csv(raw, sep=sep_choice, encoding=encoding_choice, has_header=has_header)
    except ValueError as exc:
        st.error(str(exc))
        return

    st.markdown("#### Prévisualisation")
    st.dataframe(df.head(20), use_container_width=True)
    st.caption(f"Colonnes détectées: {', '.join(df.columns)}")

    st.markdown("#### Mapping des colonnes")
    columns = ["-- Ignorer --"] + list(df.columns)
    c1, c2 = st.columns(2)
    mapping = {
        "nom": c1.selectbox("nom *", columns, index=columns.index("nom") if "nom" in columns else 0),
        "prenom": c2.selectbox("prenom *", columns, index=columns.index("prenom") if "prenom" in columns else 0),
        "email": c1.selectbox("email", columns, index=columns.index("email") if "email" in columns else 0),
        "telephone": c2.selectbox("telephone", columns, index=columns.index("telephone") if "telephone" in columns else 0),
        "notes": c1.selectbox("notes", columns, index=columns.index("notes") if "notes" in columns else 0),
        "section_code": c2.selectbox("section_code/section", columns, index=columns.index("section_code") if "section_code" in columns else (columns.index("section") if "section" in columns else 0)),
        "formation_code": c1.selectbox("formation_code/formation", columns, index=columns.index("formation_code") if "formation_code" in columns else (columns.index("formation") if "formation" in columns else 0)),
    }

    create_sections = st.checkbox("Créer sections manquantes", value=False)
    create_formations = st.checkbox("Créer formations manquantes", value=False)
    strategy = st.selectbox("Stratégie doublons", ["skip", "update", "strict"], help=HELP_TEXTS["import_strategy"])

    with SessionLocal() as db:
        options = ImportOptions(
            create_missing_sections=create_sections,
            create_missing_formations=create_formations,
            duplicate_strategy=strategy,
        )
        valid_rows, errors, duplicates = validate_rows(df, mapping, db, options)

        st.markdown("#### Résumé avant import")
        st.write({
            "lignes_totales": len(df),
            "lignes_valides": len(valid_rows),
            "lignes_erreur": len(errors),
            "doublons_detectes": len(duplicates),
        })
        if errors:
            st.dataframe(errors, use_container_width=True)

        if st.button("Lancer l'import", type="primary"):
            stats, report = apply_import(db, valid_rows, options)
            report = report + errors
            st.success(f"Import terminé: créés={stats['created']}, mis à jour={stats['updated']}, ignorés={stats['skipped']}, erreurs={stats['errors']}")
            st.dataframe(report, use_container_width=True)
            st.download_button("Télécharger rapport_import.csv", data=report_to_csv(report), file_name="rapport_import.csv", mime="text/csv")


def page_help() -> None:
    render_header("📘 Aide", "Aide / Guide utilisateur")
    st.markdown("### Sommaire")
    st.markdown("- Vue d'ensemble\n- Stagiaires\n- Sections\n- Formations\n- Import CSV\n- Sauvegarde / BDD")

    with st.expander("Vue d'ensemble"):
        st.write(AIDE_SECTIONS["overview"])
    with st.expander("Stagiaires"):
        st.write(AIDE_SECTIONS["stagiaires"])
    with st.expander("Sections"):
        st.write(AIDE_SECTIONS["sections"])
    with st.expander("Formations"):
        st.write(AIDE_SECTIONS["formations"])
    with st.expander("Import CSV"):
        st.write(AIDE_SECTIONS["import_csv"])
        st.code(CSV_EXAMPLE, language="csv")
        st.markdown("Erreurs fréquentes: email invalide, section/formation absente, colonnes non mappées.")
    with st.expander("Sauvegarde / Base de données"):
        st.write(AIDE_SECTIONS["database"])
        db_path = get_sqlite_db_path()
        if db_path:
            st.code(db_path, language="text")


def page_tools() -> None:
    render_header("Outils", "Outils / Initialisation")
    if st.button("Initialiser la base", type="primary"):
        init_db()
        toast("success", "Base initialisée")


def page_about() -> None:
    render_header("À propos", "Paramètres / À propos")
    if logo_path.exists():
        st.image(str(logo_path))
    st.markdown("**Gestion Stagiaires, Sections, Formations**")


def page_preferences() -> None:
    render_header("Préférences", "Paramètres / Préférences")
    db_path = get_sqlite_db_path()
    if db_path:
        st.code(db_path, language="text")


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
        ["Stagiaires", "Sections", "Formations", "Import CSV", "📘 Aide", "Init DB", "À propos", "Préférences"],
    )
    {
        "Stagiaires": page_stagiaires,
        "Sections": page_sections,
        "Formations": page_formations,
        "Import CSV": page_import_csv,
        "📘 Aide": page_help,
        "Init DB": page_tools,
        "À propos": page_about,
        "Préférences": page_preferences,
    }[choice]()
