from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import Section, Stagiaire
from app.schemas import SectionCreate, SectionUpdate, StagiaireCreate, StagiaireUpdate


def paginate(query: Select, page: int, per_page: int = 50):
    page = max(page, 1)
    return query.limit(per_page).offset((page - 1) * per_page)


def list_sections(db: Session, q: str | None = None, page: int = 1, per_page: int = 50):
    query = select(Section)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Section.code.ilike(pattern), Section.nom.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(paginate(query.order_by(Section.code), page, per_page)).all()
    return items, total


def get_section(db: Session, section_id: int) -> Section | None:
    return db.get(Section, section_id)


def create_section(db: Session, payload: SectionCreate) -> Section:
    section = Section(**payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def update_section(db: Session, section: Section, payload: SectionUpdate) -> Section:
    for key, value in payload.model_dump().items():
        setattr(section, key, value)
    db.commit()
    db.refresh(section)
    return section


def delete_section(db: Session, section: Section) -> None:
    db.delete(section)
    db.commit()


def list_stagiaires(
    db: Session,
    q: str | None = None,
    section_filter: str | None = None,
    page: int = 1,
    per_page: int = 50,
):
    query = select(Stagiaire)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(Stagiaire.nom.ilike(pattern), Stagiaire.prenom.ilike(pattern), Stagiaire.email.ilike(pattern))
        )

    if section_filter == "none":
        query = query.where(Stagiaire.section_id.is_(None))
    elif section_filter and section_filter.isdigit():
        query = query.where(Stagiaire.section_id == int(section_filter))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(paginate(query.order_by(Stagiaire.nom, Stagiaire.prenom), page, per_page)).all()
    return items, total


def get_stagiaire(db: Session, trainee_id: int) -> Stagiaire | None:
    return db.get(Stagiaire, trainee_id)


def create_stagiaire(db: Session, payload: StagiaireCreate) -> Stagiaire:
    trainee = Stagiaire(**payload.model_dump())
    db.add(trainee)
    db.commit()
    db.refresh(trainee)
    return trainee


def update_stagiaire(db: Session, trainee: Stagiaire, payload: StagiaireUpdate) -> Stagiaire:
    for key, value in payload.model_dump().items():
        setattr(trainee, key, value)
    db.commit()
    db.refresh(trainee)
    return trainee


def delete_stagiaire(db: Session, trainee: Stagiaire) -> None:
    db.delete(trainee)
    db.commit()


def trainees_in_section(db: Session, section_id: int):
    return db.scalars(
        select(Stagiaire).where(Stagiaire.section_id == section_id).order_by(Stagiaire.nom, Stagiaire.prenom)
    ).all()


def trainees_available_for_assignment(db: Session, section_id: int):
    return db.scalars(
        select(Stagiaire).where(or_(Stagiaire.section_id.is_(None), Stagiaire.section_id != section_id)).order_by(Stagiaire.nom, Stagiaire.prenom)
    ).all()


def assign_trainee(db: Session, trainee_id: int, section_id: int) -> bool:
    trainee = db.get(Stagiaire, trainee_id)
    if not trainee:
        return False
    trainee.section_id = section_id
    db.commit()
    return True


def unassign_trainee(db: Session, trainee_id: int, section_id: int) -> bool:
    trainee = db.get(Stagiaire, trainee_id)
    if not trainee or trainee.section_id != section_id:
        return False
    trainee.section_id = None
    db.commit()
    return True
