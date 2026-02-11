from __future__ import annotations

from datetime import date
from typing import Callable, TypeVar

import streamlit as st
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db import SessionLocal, get_sqlite_db_path, init_db
from app.models import Section, Stagiaire
from app.schemas import SectionCreate, StagiaireCreate

T = TypeVar("T")

st.set_page_config(page_title="Gestion des stagiaires", layout="wide")
st.title("Gestion des stagiaires (Streamlit)")
st.caption("Application locale, sans clé API.")

# Initialisation proactive: création des tables si base vide.
init_db()

db_path = get_sqlite_db_path()
if db_path:
    st.caption(f"SQLite utilisé: {db_path}")


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
        st.subheader("Liste des stagiaires")
        q = st.text_input("Recherche (nom/prénom/email)", key="q")
        trainees = load_trainees(db, q)

        if trainees:
            st.dataframe(
                [
                    {
                        "ID": t.id,
                        "Nom": t.nom,
                        "Prénom": t.prenom,
                        "Email": t.email or "",
                        "Téléphone": t.telephone or "",
                        "Section": t.section.code if t.section else "Aucune",
                    }
                    for t in trainees
                ],
                use_container_width=True,
            )
        else:
            st.info("Aucun stagiaire trouvé.")

        st.markdown("### Ajouter un stagiaire")
        sections = load_sections(db)
        section_options = {"Aucune": None} | {f"{s.code} - {s.nom}": s.id for s in sections}

        with st.form("create_trainee", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nom *")
            prenom = c2.text_input("Prénom *")
            email = c1.text_input("Email")
            telephone = c2.text_input("Téléphone")
            section_label = st.selectbox("Section", list(section_options.keys()))
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Créer")

            if submitted:
                try:
                    payload = StagiaireCreate(
                        nom=nom,
                        prenom=prenom,
                        email=email or None,
                        telephone=telephone or None,
                        notes=notes or None,
                        section_id=section_options[section_label],
                    )
                    db.add(Stagiaire(**payload.model_dump()))
                    db.commit()
                    st.success("Stagiaire créé.")
                except ValidationError as exc:
                    st.error(f"Validation: {exc.errors()[0]['msg']}")
                except IntegrityError:
                    db.rollback()
                    st.error("Erreur: email déjà utilisé.")

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
                    db.add(Section(**payload.model_dump()))
                    db.commit()
                    st.success("Section créée.")
                except ValidationError as exc:
                    st.error(f"Validation: {exc.errors()[0]['msg']}")
                except IntegrityError:
                    db.rollback()
                    st.error("Erreur: code section déjà utilisé.")
