from __future__ import annotations

from datetime import date
from typing import Callable, TypeVar

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import crud
from app.db import SessionLocal, get_sqlite_db_path, init_db
from app.models import Section, Stagiaire
from app.schemas import SectionCreate, SectionUpdate, StagiaireCreate, StagiaireUpdate

T = TypeVar("T")

# Sidebar state must be set before page config for each rerun.
if "sidebar_state" not in st.session_state:
    st.session_state.sidebar_state = "expanded"

st.set_page_config(
    page_title="Gestion Stagiaires",
    layout="wide",
    initial_sidebar_state=st.session_state.sidebar_state,
)

logo_path = "app/static/logo_acces_vii.svg"

st.session_state.setdefault("trainee_screen", "list")
st.session_state.setdefault("edit_trainee_id", None)
st.session_state.setdefault("section_screen", "list")
st.session_state.setdefault("edit_section_id", None)
st.session_state.setdefault("page", "Stagiaires")
st.session_state.setdefault("auto_collapse_sidebar", False)


def toggle_sidebar_state() -> None:
    st.session_state.sidebar_state = (
        "collapsed" if st.session_state.sidebar_state == "expanded" else "expanded"
    )


def navigate_to(page_name: str) -> None:
    page_changed = st.session_state.page != page_name
    st.session_state.page = page_name
    if page_changed and st.session_state.auto_collapse_sidebar:
        st.session_state.sidebar_state = "collapsed"
    st.rerun()


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
    st.markdown(f"### {'Modifier stagiaire' if is_edit else 'Ajouter un stagiaire'}")

    section_options = {"Aucune section": None} | {f"{s.code} - {s.nom}": s.id for s in sections}
    labels = list(section_options.keys())
    current = trainee.section_id if trainee else None
    default_label = next((label for label, sid in section_options.items() if sid == current), "Aucune section")

    with st.form(f"trainee_form_{mode}_{trainee.id if trainee else 'new'}"):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom *", value=trainee.nom if trainee else "")
        prenom = c2.text_input("Prénom *", value=trainee.prenom if trainee else "")
        email = c1.text_input("Email", value=trainee.email or "" if trainee else "")
        telephone = c2.text_input("Téléphone", value=trainee.telephone or "" if trainee else "")
        section_label = st.selectbox("Section", labels, index=labels.index(default_label))
        notes = st.text_area("Notes", value=trainee.notes or "" if trainee else "")

        save_col, cancel_col = st.columns(2)
        save = save_col.form_submit_button("Enregistrer")
        cancel = cancel_col.form_submit_button("Annuler")

        if cancel:
            set_trainee_screen("list")
            st.rerun()

        if save:
            section_id = section_options[section_label]
            if section_id is not None and not crud.get_section_by_id(db, section_id):
                st.error("La section sélectionnée n'existe pas.")
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
                        return
                    st.success("Stagiaire mis à jour avec succès.")
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
                    st.success("Stagiaire créé.")
                set_trainee_screen("list")
                st.rerun()
            except ValidationError as exc:
                st.error(f"Validation: {', '.join(err['msg'] for err in exc.errors())}")
            except IntegrityError:
                db.rollback()
                st.error("Erreur: email déjà utilisé par un autre stagiaire.")


def render_section_form(*, db, mode: str, section: Section | None = None) -> None:
    is_edit = mode == "edit"
    section_id = section.id if section else None
    st.markdown(f"### {'Modifier section' if is_edit else 'Ajouter une section'}")

    if is_edit and not section:
        st.error("Section introuvable.")
        set_section_screen("list")
        return

    with st.form(f"section_form_{mode}_{section_id or 'new'}"):
        c1, c2 = st.columns(2)
        code = c1.text_input("Code *", value=section.code if section else "")
        nom = c2.text_input("Nom *", value=section.nom if section else "")

        has_date_debut = c1.checkbox("Renseigner date début", value=section.date_debut is not None if section else False)
        has_date_fin = c2.checkbox("Renseigner date fin", value=section.date_fin is not None if section else False)

        date_debut = c1.date_input(
            "Date début",
            value=section.date_debut or date.today() if section else date.today(),
            disabled=not has_date_debut,
        )
        date_fin = c2.date_input(
            "Date fin",
            value=section.date_fin or date.today() if section else date.today(),
            disabled=not has_date_fin,
        )

        description = st.text_area("Description", value=section.description or "" if section else "")

        save_col, cancel_col = st.columns(2)
        save = save_col.form_submit_button("Enregistrer" if is_edit else "Créer")
        cancel = cancel_col.form_submit_button("Annuler")

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
                        return
                    st.success("Section mise à jour avec succès.")
                else:
                    crud.create_section(db, payload)
                    st.success("Section créée.")
                set_section_screen("list")
                st.rerun()
            except ValidationError as exc:
                st.error(f"Validation: {', '.join(err['msg'] for err in exc.errors())}")
            except IntegrityError:
                db.rollback()
                st.error("Erreur: code section déjà utilisé.")


def render_section_assignments(db, section_id: int) -> None:
    st.markdown("### Gestion des stagiaires rattachés")
    include_other = st.checkbox(
        "Inclure aussi les stagiaires d'autres sections dans les disponibles",
        value=True,
        key=f"include_other_{section_id}",
    )

    in_section = crud.list_trainees_in_section(db, section_id)
    available = crud.list_trainees_available_for_section(db, section_id, include_other_sections=include_other)

    col_in, col_av = st.columns(2)

    with col_in:
        st.markdown("**A) Stagiaires dans cette section**")
        if not in_section:
            st.info("Aucun stagiaire dans cette section.")
        for trainee in in_section:
            row = st.columns([3, 1])
            row[0].write(f"{trainee.nom} {trainee.prenom} ({trainee.email or 'sans email'})")
            if row[1].button("Retirer", key=f"unassign_{section_id}_{trainee.id}"):
                if crud.unassign_trainee(db, trainee.id):
                    st.success(f"{trainee.prenom} {trainee.nom} retiré de la section.")
                else:
                    st.error("Impossible de retirer ce stagiaire.")
                st.rerun()

    with col_av:
        st.markdown("**B) Stagiaires disponibles**")
        if not available:
            st.info("Aucun stagiaire disponible.")
        for trainee in available:
            row = st.columns([3, 1])
            section_label = f" (actuel: {trainee.section.code})" if trainee.section else ""
            row[0].write(f"{trainee.nom} {trainee.prenom}{section_label}")
            if row[1].button("Ajouter", key=f"assign_{section_id}_{trainee.id}"):
                if crud.assign_trainee_to_section(db, trainee.id, section_id):
                    st.success(f"{trainee.prenom} {trainee.nom} ajouté à la section.")
                else:
                    st.error("Impossible d'ajouter ce stagiaire.")
                st.rerun()

    st.markdown("### Suppression de section")
    confirm_key = f"confirm_delete_{section_id}"
    if st.checkbox("Confirmer la suppression de cette section", key=confirm_key):
        if st.button("🗑️ Supprimer section", key=f"delete_section_{section_id}"):
            if crud.delete_section_safely(db, section_id):
                st.success("Section supprimée. Les stagiaires ont été désaffectés.")
                set_section_screen("list")
            else:
                st.error("Section introuvable.")
            st.rerun()


def render_trainees_page(db) -> None:
    st.subheader("Stagiaires")
    top_left, top_right = st.columns([2, 1])
    q = top_left.text_input("Recherche (nom/prénom/email)", key="q")
    if top_right.button("➕ Nouveau stagiaire"):
        set_trainee_screen("create")
        st.rerun()

    trainees = load_trainees(db, q)
    sections = load_sections(db)

    if st.session_state.trainee_screen == "edit":
        trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
        render_trainee_form(db=db, mode="edit", sections=sections, trainee=trainee)
    elif st.session_state.trainee_screen == "create":
        render_trainee_form(db=db, mode="create", sections=sections)

    st.markdown("### Liste")
    if trainees:
        header = st.columns([1.2, 1.2, 2.2, 1.4, 1.8, 1])
        header[0].markdown("**Nom**")
        header[1].markdown("**Prénom**")
        header[2].markdown("**Email**")
        header[3].markdown("**Téléphone**")
        header[4].markdown("**Section**")
        header[5].markdown("**Action**")
        for trainee in trainees:
            cols = st.columns([1.2, 1.2, 2.2, 1.4, 1.8, 1])
            cols[0].write(trainee.nom)
            cols[1].write(trainee.prenom)
            cols[2].write(trainee.email or "-")
            cols[3].write(trainee.telephone or "-")
            cols[4].write(trainee.section.code if trainee.section else "Aucune section")
            if cols[5].button("✏️ Modifier", key=f"edit_trainee_{trainee.id}"):
                set_trainee_screen("edit", trainee.id)
                st.rerun()
    else:
        st.info("Aucun stagiaire trouvé.")


def render_sections_page(db) -> None:
    st.subheader("Sections")
    search_col, add_col = st.columns([2, 1])
    q_section = search_col.text_input("Recherche section (code/nom)", key="q_section")
    if add_col.button("➕ Nouvelle section"):
        set_section_screen("create")
        st.rerun()

    sections = load_sections(db)
    if q_section:
        q_filter = q_section.strip().lower()
        sections = [s for s in sections if q_filter in s.code.lower() or q_filter in s.nom.lower()]

    if st.session_state.section_screen == "edit":
        section = crud.get_section_by_id(db, st.session_state.edit_section_id)
        render_section_form(db=db, mode="edit", section=section)
        if section:
            render_section_assignments(db, section.id)
    elif st.session_state.section_screen == "create":
        render_section_form(db=db, mode="create")

    st.markdown("### Liste des sections")
    if sections:
        header = st.columns([0.9, 1.5, 2, 1.2, 1.2, 1.2, 1])
        header[0].markdown("**ID**")
        header[1].markdown("**Code**")
        header[2].markdown("**Nom**")
        header[3].markdown("**Début**")
        header[4].markdown("**Fin**")
        header[5].markdown("**Stagiaires**")
        header[6].markdown("**Action**")
        for section in sections:
            row = st.columns([0.9, 1.5, 2, 1.2, 1.2, 1.2, 1])
            row[0].write(section.id)
            row[1].write(section.code)
            row[2].write(section.nom)
            row[3].write(section.date_debut or "-")
            row[4].write(section.date_fin or "-")
            row[5].write(len(section.stagiaires))
            if row[6].button("✏️ Modifier", key=f"edit_section_{section.id}"):
                set_section_screen("edit", section.id)
                st.rerun()
    else:
        st.info("Aucune section.")


def render_settings_page() -> None:
    st.subheader("Paramètres")
    st.write("Panneau de configuration de l'application Streamlit.")
    db_path = get_sqlite_db_path()
    if db_path:
        st.code(db_path, language="text")
    if st.button("Initialiser la base"):
        init_db()
        st.success("Base initialisée (tables créées si nécessaire).")


# Init DB early for both pages
init_db()

with st.sidebar:
    st.image(logo_path)
    st.markdown("## Navigation")
    st.caption("Gestion stagiaires / sections")
    st.session_state.auto_collapse_sidebar = st.checkbox(
        "Auto-rétracter après navigation",
        value=st.session_state.auto_collapse_sidebar,
    )

    selected_page = st.radio(
        "Aller vers",
        options=["Stagiaires", "Sections", "Paramètres"],
        index=["Stagiaires", "Sections", "Paramètres"].index(st.session_state.page),
        key="sidebar_page_selector",
    )
    if selected_page != st.session_state.page:
        navigate_to(selected_page)

st.markdown(
    """
    <style>
      .main-menu-row { margin: 0.25rem 0 1rem 0; }
      .main-menu-hint { color: #6b7280; font-size: 0.9rem; margin-top: 0.25rem; }
      section[data-testid="stSidebar"] .stRadio > div { gap: 0.4rem; }
      section[data-testid="stSidebar"] .stRadio label { font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

menu_col, title_col = st.columns([1, 8])
with menu_col:
    if st.button("☰ Menu", use_container_width=True):
        toggle_sidebar_state()
        st.rerun()
with title_col:
    st.title("Gestion des stagiaires (Streamlit)")
    st.caption("Application locale, sans clé API.")

with SessionLocal() as db:
    if st.session_state.page == "Stagiaires":
        render_trainees_page(db)
    elif st.session_state.page == "Sections":
        render_sections_page(db)
    else:
        render_settings_page()
