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
from app.schemas import SectionCreate, StagiaireCreate, StagiaireUpdate

T = TypeVar("T")

st.set_page_config(page_title="Gestion des stagiaires", layout="wide")
st.title("Gestion des stagiaires (Streamlit)")
st.caption("Application locale, sans clé API.")

# Initialisation proactive: création des tables si base vide.
init_db()

db_path = get_sqlite_db_path()
if db_path:
    st.caption(f"SQLite utilisé: {db_path}")

if "trainee_screen" not in st.session_state:
    st.session_state.trainee_screen = "list"
if "edit_trainee_id" not in st.session_state:
    st.session_state.edit_trainee_id = None


def safe_query(action: Callable[[], T]) -> T:
    """Exécute une requête et auto-initialise la DB si table absente."""
    try:
        return action()
    except OperationalError as exc:
        message = str(exc).lower()
        if "no such table" in message:
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


def set_screen(screen: str, trainee_id: int | None = None) -> None:
    st.session_state.trainee_screen = screen
    st.session_state.edit_trainee_id = trainee_id


def render_trainee_form(
    *,
    db,
    mode: str,
    sections: list[Section],
    trainee: Stagiaire | None = None,
) -> None:
    is_edit = mode == "edit"
    title = "Modifier stagiaire" if is_edit else "Ajouter un stagiaire"
    st.markdown(f"### {title}")

    section_options = {"Aucune section": None} | {f"{s.code} - {s.nom}": s.id for s in sections}

    current_section_id = trainee.section_id if trainee else None
    section_labels = list(section_options.keys())
    default_label = next(
        (label for label, sid in section_options.items() if sid == current_section_id),
        "Aucune section",
    )
    default_index = section_labels.index(default_label)

    form_key = f"trainee_form_{mode}_{trainee.id if trainee else 'new'}"
    with st.form(form_key):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom *", value=trainee.nom if trainee else "")
        prenom = c2.text_input("Prénom *", value=trainee.prenom if trainee else "")
        email = c1.text_input("Email", value=trainee.email or "" if trainee else "")
        telephone = c2.text_input("Téléphone", value=trainee.telephone or "" if trainee else "")
        section_label = st.selectbox("Section", section_labels, index=default_index)
        notes = st.text_area("Notes", value=trainee.notes or "" if trainee else "")

        save_col, cancel_col = st.columns(2)
        save = save_col.form_submit_button("Enregistrer")
        cancel = cancel_col.form_submit_button("Annuler")

        if cancel:
            set_screen("list", None)
            st.rerun()

        if save:
            section_id = section_options[section_label]
            if section_id is not None and not crud.get_section(db, section_id):
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
                    updated = crud.update_trainee(db, trainee.id, payload)
                    if not updated:
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

                set_screen("list", None)
                st.rerun()
            except ValidationError as exc:
                errors = ", ".join(err["msg"] for err in exc.errors())
                st.error(f"Validation: {errors}")
            except IntegrityError:
                db.rollback()
                st.error("Erreur: email déjà utilisé par un autre stagiaire.")


col_a, col_b = st.columns([1, 2])
with col_a:
    if st.button("Initialiser la base"):
        init_db()
        st.success("Base initialisée (tables créées si nécessaire).")

with col_b:
    st.info("Si la base est vide, les tables sont créées automatiquement au démarrage.")


tab1, tab2 = st.tabs(["Stagiaires", "Sections"])

with SessionLocal() as db:
    with tab1:
        st.subheader("Stagiaires")
        top_left, top_right = st.columns([2, 1])
        q = top_left.text_input("Recherche (nom/prénom/email)", key="q")
        if top_right.button("➕ Nouveau stagiaire"):
            set_screen("create", None)
            st.rerun()

        trainees = load_trainees(db, q)
        sections = load_sections(db)

        if st.session_state.trainee_screen == "edit":
            trainee = crud.get_trainee_by_id(db, st.session_state.edit_trainee_id)
            if not trainee:
                st.error("Stagiaire introuvable.")
                set_screen("list", None)
            else:
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
                if cols[5].button("✏️ Modifier", key=f"edit_{trainee.id}"):
                    set_screen("edit", trainee.id)
                    st.rerun()
        else:
            st.info("Aucun stagiaire trouvé.")

    with tab2:
        st.subheader("Liste des sections")
        sections = load_sections(db)
        if sections:
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
            )
        else:
            st.info("Aucune section.")

        st.markdown("### Ajouter une section")
        with st.form("create_section", clear_on_submit=True):
            c1, c2 = st.columns(2)
            code = c1.text_input("Code *")
            nom = c2.text_input("Nom *")
            has_date_debut = c1.checkbox("Renseigner date début", value=False)
            has_date_fin = c2.checkbox("Renseigner date fin", value=False)
            date_debut = c1.date_input("Date début", value=date.today(), disabled=not has_date_debut)
            date_fin = c2.date_input("Date fin", value=date.today(), disabled=not has_date_fin)
            description = st.text_area("Description")
            submitted_section = st.form_submit_button("Créer")

            if submitted_section:
                try:
                    payload = SectionCreate(
                        code=code,
                        nom=nom,
                        date_debut=date_debut if has_date_debut else None,
                        date_fin=date_fin if has_date_fin else None,
                        description=description or None,
                    )
                    crud.create_section(db, payload)
                    st.success("Section créée.")
                    st.rerun()
                except ValidationError as exc:
                    st.error(f"Validation: {exc.errors()[0]['msg']}")
                except IntegrityError:
                    db.rollback()
                    st.error("Erreur: code section déjà utilisé.")
