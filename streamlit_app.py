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
from app.models import Section, Stagiaire
from app.schemas import SectionCreate, SectionUpdate, StagiaireCreate, StagiaireUpdate
from ui.layout import inject_app_css, render_header, toast

st.set_page_config(page_title="Gestion Stagiaires", layout="wide")

T = TypeVar("T")
logo_path = Path("app/static/logo_acces_vii.svg")

st.session_state.setdefault("trainee_screen", "list")
st.session_state.setdefault("edit_trainee_id", None)
st.session_state.setdefault("section_screen", "list")
st.session_state.setdefault("edit_section_id", None)


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


def render_trainee_form(*, db, mode: str, sections: list[Section], trainee: Stagiaire | None = None) -> None:
    is_edit = mode == "edit"
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown(f"#### {'Modifier stagiaire' if is_edit else 'Nouveau stagiaire'}")

    section_options = {"Aucune section": None} | {f"{s.code} - {s.nom}": s.id for s in sections}
    labels = list(section_options.keys())
    current = trainee.section_id if trainee else None
    default_label = next((label for label, sid in section_options.items() if sid == current), "Aucune section")

    with st.form(f"trainee_form_{mode}_{trainee.id if trainee else 'new'}"):
        left, right = st.columns(2)
        nom = left.text_input("Nom *", value=trainee.nom if trainee else "")
        prenom = left.text_input("Prénom *", value=trainee.prenom if trainee else "")
        email = right.text_input("Email", value=trainee.email or "" if trainee else "")
        telephone = right.text_input("Téléphone", value=trainee.telephone or "" if trainee else "")
        section_label = st.selectbox("Section", labels, index=labels.index(default_label))
        notes = st.text_area("Notes", value=trainee.notes or "" if trainee else "")

        primary, secondary = st.columns([1, 1])
        save = primary.form_submit_button("💾 Enregistrer", type="primary")
        cancel = secondary.form_submit_button("Annuler")

        if cancel:
            set_trainee_screen("list")
            st.rerun()

        if save:
            section_id = section_options[section_label]
            field_errors: list[str] = []
            if not nom.strip():
                field_errors.append("Le nom est obligatoire.")
            if not prenom.strip():
                field_errors.append("Le prénom est obligatoire.")
            if section_id is not None and not crud.get_section_by_id(db, section_id):
                field_errors.append("La section sélectionnée n'existe pas.")

            if field_errors:
                st.error("\n".join(field_errors))
                st.markdown("</div>", unsafe_allow_html=True)
                return

            try:
                if is_edit and trainee is not None:
                    payload = StagiaireUpdate(
                        nom=nom,
                        prenom=prenom,
                        email=email or None,
                        telephone=telephone or None,
                        notes=notes or None,
                        section_id=section_id,
                    )
                    if not crud.update_trainee(db, trainee.id, payload):
                        st.error("Stagiaire introuvable.")
                        st.markdown("</div>", unsafe_allow_html=True)
                        return
                    toast("success", "Stagiaire mis à jour")
                else:
                    payload = StagiaireCreate(
                        nom=nom,
                        prenom=prenom,
                        email=email or None,
                        telephone=telephone or None,
                        notes=notes or None,
                        section_id=section_id,
                    )
                    crud.create_stagiaire(db, payload)
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
        has_date_fin = right.checkbox("Date fin", value=section.date_fin is not None if section else False)

        date_debut = left.date_input("Date début", value=section.date_debut or date.today() if section else date.today(), disabled=not has_date_debut)
        date_fin = right.date_input("Date fin", value=section.date_fin or date.today() if section else date.today(), disabled=not has_date_fin)
        description = st.text_area("Description", value=section.description or "" if section else "")

        primary, secondary = st.columns([1, 1])
        save = primary.form_submit_button("💾 Enregistrer", type="primary")
        cancel = secondary.form_submit_button("Annuler")

        if cancel:
            set_section_screen("list")
            st.rerun()

        if save:
            try:
                payload = (SectionUpdate if is_edit else SectionCreate)(
                    code=code,
                    nom=nom,
                    date_debut=date_debut if has_date_debut else None,
                    date_fin=date_fin if has_date_fin else None,
                    description=description or None,
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


def render_section_assignments(db, section_id: int) -> None:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("#### Affectation des stagiaires")
    include_other = st.checkbox("Inclure stagiaires d'autres sections", value=True, key=f"include_other_{section_id}")

    in_section = crud.list_trainees_in_section(db, section_id)
    available = crud.list_trainees_available_for_section(db, section_id, include_other_sections=include_other)

    col_in, col_av = st.columns(2)
    with col_in:
        st.markdown("**Dans cette section**")
        if not in_section:
            st.caption("Aucun stagiaire")
        for trainee in in_section:
            row = st.columns([3, 1])
            row[0].write(f"{trainee.nom} {trainee.prenom}")
            if row[1].button("Retirer", key=f"unassign_{section_id}_{trainee.id}"):
                crud.unassign_trainee(db, trainee.id)
                toast("success", f"{trainee.prenom} retiré")
                st.rerun()

    with col_av:
        st.markdown("**Disponibles**")
        if not available:
            st.caption("Aucun stagiaire")
        for trainee in available:
            row = st.columns([3, 1])
            row[0].write(f"{trainee.nom} {trainee.prenom}")
            if row[1].button("Ajouter", key=f"assign_{section_id}_{trainee.id}"):
                crud.assign_trainee_to_section(db, trainee.id, section_id)
                toast("success", f"{trainee.prenom} ajouté")
                st.rerun()

    st.warning("Suppression: les stagiaires seront désaffectés puis la section supprimée.")
    confirm = st.checkbox("Je confirme la suppression", key=f"confirm_delete_{section_id}")
    if st.button("🗑️ Supprimer la section", disabled=not confirm, key=f"delete_{section_id}"):
        if crud.delete_section_safely(db, section_id):
            toast("success", "Section supprimée")
            set_section_screen("list")
            st.rerun()
        st.error("Section introuvable")

    st.markdown("</div>", unsafe_allow_html=True)


def page_stagiaires() -> None:
    render_header(
        "Gestion des stagiaires",
        "Gestion / Stagiaires",
        actions=[("+ Nouveau stagiaire", lambda: set_trainee_screen("create"))],
    )

    with SessionLocal() as db:
        st.markdown("<div class='app-toolbar'>", unsafe_allow_html=True)
        q = st.text_input("Recherche (nom, prénom, email)", key="q_trainees")
        st.markdown("</div>", unsafe_allow_html=True)

        trainees = load_trainees(db, q)
        sections = load_sections(db)

        if st.session_state.trainee_screen == "edit":
            trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
            render_trainee_form(db=db, mode="edit", sections=sections, trainee=trainee)
        elif st.session_state.trainee_screen == "create":
            render_trainee_form(db=db, mode="create", sections=sections)

        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("#### Liste des stagiaires")
        rows = [
            {
                "Nom": t.nom,
                "Prénom": t.prenom,
                "Email": t.email or "-",
                "Téléphone": t.telephone or "-",
                "Section": t.section.code if t.section else "Aucune",
            }
            for t in trainees
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if trainees:
            st.markdown("##### Actions rapides")
            for trainee in trainees:
                line = st.columns([2, 2, 1, 1])
                line[0].write(f"{trainee.nom} {trainee.prenom}")
                line[1].write(trainee.email or "-")
                if line[2].button("Modifier", key=f"edit_trainee_{trainee.id}"):
                    set_trainee_screen("edit", trainee.id)
                    st.rerun()
                if line[3].button("Supprimer", key=f"delete_trainee_{trainee.id}"):
                    crud.delete_stagiaire(db, trainee)
                    toast("success", "Stagiaire supprimé")
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def page_sections() -> None:
    render_header(
        "Gestion des sections",
        "Gestion / Sections",
        actions=[("+ Nouvelle section", lambda: set_section_screen("create"))],
    )

    with SessionLocal() as db:
        st.markdown("<div class='app-toolbar'>", unsafe_allow_html=True)
        q_section = st.text_input("Recherche (code/nom)", key="q_sections")
        st.markdown("</div>", unsafe_allow_html=True)

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

        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("#### Liste des sections")
        st.dataframe(
            [
                {
                    "Code": s.code,
                    "Nom": s.nom,
                    "Début": s.date_debut,
                    "Fin": s.date_fin,
                    "Stagiaires": len(s.stagiaires),
                }
                for s in sections
            ],
            use_container_width=True,
            hide_index=True,
        )
        for section in sections:
            row = st.columns([2, 2, 1])
            row[0].write(f"{section.code} — {section.nom}")
            row[1].write(f"{len(section.stagiaires)} stagiaire(s)")
            if row[2].button("Modifier", key=f"edit_section_{section.id}"):
                set_section_screen("edit", section.id)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def page_tools() -> None:
    render_header("Outils", "Outils / Initialisation")
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("#### Maintenance")
    st.caption("Initialiser ou alimenter la base locale")
    if st.button("Initialiser la base", type="primary"):
        init_db()
        toast("success", "Base initialisée")
    st.markdown("</div>", unsafe_allow_html=True)


def page_about() -> None:
    render_header("À propos", "Paramètres / À propos")
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    if logo_path.exists():
        st.image(str(logo_path))
    st.markdown("**Gestion Stagiaires & Sections**")
    st.markdown("Application locale Streamlit/FastAPI pour la gestion métier.")
    st.markdown("</div>", unsafe_allow_html=True)


def page_preferences() -> None:
    render_header("Préférences", "Paramètres / Préférences")
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("#### Configuration locale")
    db_path = get_sqlite_db_path()
    if db_path:
        st.code(db_path, language="text")
    st.markdown("<span class='small-muted'>Le thème se configure dans .streamlit/config.toml.</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


init_db()
inject_app_css()

if hasattr(st, "navigation") and hasattr(st, "Page"):
    nav = st.navigation(
        {
            "Gestion": [
                st.Page(page_stagiaires, title="Stagiaires", icon="👨‍🎓"),
                st.Page(page_sections, title="Sections", icon="🏫"),
            ],
            "Outils": [
                st.Page(page_tools, title="Init DB", icon="🛠️"),
            ],
            "Paramètres": [
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
        ["Stagiaires", "Sections", "Init DB", "À propos", "Préférences"],
    )
    {
        "Stagiaires": page_stagiaires,
        "Sections": page_sections,
        "Init DB": page_tools,
        "À propos": page_about,
        "Préférences": page_preferences,
    }[choice]()
