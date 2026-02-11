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


def get_section_by_id(db: Session, section_id: int) -> Section | None:
    return get_section(db, section_id)


def create_section(db: Session, payload: SectionCreate) -> Section:
    section = Section(**payload.model_dump())
    db.add(section)
    db.commit()
    db.refresh(section)
    return section


def update_section(db: Session, section_or_id: Section | int, payload: SectionUpdate) -> Section | None:
    section = section_or_id if isinstance(section_or_id, Section) else get_section_by_id(db, section_or_id)
    if not section:
        return None

    for key, value in payload.model_dump().items():
        setattr(section, key, value)
    db.commit()
    db.refresh(section)
    return section


def delete_section(db: Session, section: Section) -> None:
    db.delete(section)
    db.commit()


def list_trainees_in_section(db: Session, section_id: int):
    return db.scalars(
        select(Stagiaire).where(Stagiaire.section_id == section_id).order_by(Stagiaire.nom, Stagiaire.prenom)
    ).all()


def trainees_in_section(db: Session, section_id: int):
    return list_trainees_in_section(db, section_id)


def list_trainees_available_for_section(
    db: Session,
    section_id: int,
    include_other_sections: bool = True,
):
    base_query = select(Stagiaire)
    if include_other_sections:
        base_query = base_query.where(or_(Stagiaire.section_id.is_(None), Stagiaire.section_id != section_id))
    else:
        base_query = base_query.where(Stagiaire.section_id.is_(None))

    return db.scalars(base_query.order_by(Stagiaire.nom, Stagiaire.prenom)).all()


def trainees_available_for_assignment(db: Session, section_id: int):
    return list_trainees_available_for_section(db, section_id, include_other_sections=True)


def assign_trainee(db: Session, trainee_id: int, section_id: int) -> bool:
    trainee = db.get(Stagiaire, trainee_id)
    if not trainee:
        return False
    trainee.section_id = section_id
    db.commit()
    return True


def assign_trainee_to_section(db: Session, trainee_id: int, section_id: int) -> bool:
    if not get_section_by_id(db, section_id):
        return False
    return assign_trainee(db, trainee_id, section_id)


def unassign_trainee(db: Session, trainee_id: int, section_id: int | None = None) -> bool:
    trainee = db.get(Stagiaire, trainee_id)
    if not trainee:
        return False
    if section_id is not None and trainee.section_id != section_id:
        return False
    trainee.section_id = None
    db.commit()
    return True


def delete_section_safely(db: Session, section_id: int) -> bool:
    section = get_section_by_id(db, section_id)
    if not section:
        return False

    db.query(Stagiaire).filter(Stagiaire.section_id == section_id).update({Stagiaire.section_id: None})
    db.delete(section)
    db.commit()
    return True


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


def get_trainee_by_id(db: Session, trainee_id: int) -> Stagiaire | None:
    return get_stagiaire(db, trainee_id)


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


def update_trainee(db: Session, trainee_id: int, payload: StagiaireUpdate) -> Stagiaire | None:
    trainee = get_trainee_by_id(db, trainee_id)
    if not trainee:
        return None
    return update_stagiaire(db, trainee, payload)


def delete_stagiaire(db: Session, trainee: Stagiaire) -> None:
    db.delete(trainee)
    db.commit()
