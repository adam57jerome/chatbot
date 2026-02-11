from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db
from app.main import templates

router = APIRouter(prefix="/sections", tags=["sections"])


def _flash(request: Request, kind: str, message: str) -> None:
    request.session["flash"] = {"kind": kind, "message": message}


def _render_assign_lists(request: Request, db: Session, section_id: int):
    return templates.TemplateResponse(
        "partials/section_assign_lists.html",
        {
            "request": request,
            "in_section": crud.trainees_in_section(db, section_id),
            "available": crud.trainees_available_for_assignment(db, section_id),
            "section_id": section_id,
        },
    )


@router.get("", response_class=HTMLResponse)
def list_sections(request: Request, q: str | None = None, page: int = 1, db: Session = Depends(get_db)):
    sections, total = crud.list_sections(db, q=q, page=page)
    return templates.TemplateResponse(
        "sections_list.html",
        {"request": request, "sections": sections, "q": q or "", "page": page, "has_next": page * 50 < total, "has_prev": page > 1},
    )


@router.get("/nouveau", response_class=HTMLResponse)
def new_section_form(request: Request):
    return templates.TemplateResponse("section_form.html", {"request": request, "section": None, "errors": {}})


@router.post("/nouveau")
def create_section(
    request: Request,
    code: str = Form(...),
    nom: str = Form(...),
    date_debut: str | None = Form(None),
    date_fin: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
):
    payload_data = {
        "code": code,
        "nom": nom,
        "date_debut": date_debut or None,
        "date_fin": date_fin or None,
        "description": description or None,
    }
    try:
        payload = schemas.SectionCreate(**payload_data)
        section = crud.create_section(db, payload)
        _flash(request, "success", "Section créée avec succès.")
        return RedirectResponse(f"/sections/{section.id}", status_code=303)
    except ValidationError as exc:
        errors = {e["loc"][-1]: e["msg"] for e in exc.errors()}
    except IntegrityError:
        db.rollback()
        errors = {"code": "Ce code section existe déjà."}

    return templates.TemplateResponse("section_form.html", {"request": request, "section": payload_data, "errors": errors}, status_code=400)


@router.get("/{section_id}", response_class=HTMLResponse)
def section_detail(section_id: int, request: Request, db: Session = Depends(get_db)):
    section = crud.get_section(db, section_id)
    if not section:
        _flash(request, "error", "Section introuvable.")
        return RedirectResponse("/sections", status_code=303)
    trainees = crud.trainees_in_section(db, section_id)
    return templates.TemplateResponse("section_detail.html", {"request": request, "section": section, "trainees": trainees})


@router.get("/{section_id}/edit", response_class=HTMLResponse)
def edit_section_form(section_id: int, request: Request, db: Session = Depends(get_db)):
    section = crud.get_section(db, section_id)
    if not section:
        _flash(request, "error", "Section introuvable.")
        return RedirectResponse("/sections", status_code=303)

    return templates.TemplateResponse(
        "section_edit_assign.html",
        {
            "request": request,
            "section": section,
            "errors": {},
            "in_section": crud.trainees_in_section(db, section_id),
            "available": crud.trainees_available_for_assignment(db, section_id),
        },
    )


@router.post("/{section_id}/edit")
def update_section(
    section_id: int,
    request: Request,
    code: str = Form(...),
    nom: str = Form(...),
    date_debut: str | None = Form(None),
    date_fin: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
):
    section = crud.get_section(db, section_id)
    if not section:
        _flash(request, "error", "Section introuvable.")
        return RedirectResponse("/sections", status_code=303)

    payload_data = {"code": code, "nom": nom, "date_debut": date_debut or None, "date_fin": date_fin or None, "description": description or None}

    try:
        payload = schemas.SectionUpdate(**payload_data)
        crud.update_section(db, section, payload)
        _flash(request, "success", "Section mise à jour.")
        return RedirectResponse(f"/sections/{section_id}/edit", status_code=303)
    except ValidationError as exc:
        errors = {e["loc"][-1]: e["msg"] for e in exc.errors()}
    except IntegrityError:
        db.rollback()
        errors = {"code": "Ce code section existe déjà."}

    payload_data["id"] = section_id
    return templates.TemplateResponse(
        "section_edit_assign.html",
        {
            "request": request,
            "section": payload_data,
            "errors": errors,
            "in_section": crud.trainees_in_section(db, section_id),
            "available": crud.trainees_available_for_assignment(db, section_id),
        },
        status_code=400,
    )


@router.post("/{section_id}/delete")
def delete_section(section_id: int, request: Request, db: Session = Depends(get_db)):
    section = crud.get_section(db, section_id)
    if section:
        crud.delete_section(db, section)
        _flash(request, "success", "Section supprimée. Les stagiaires ont été désaffectés.")
    else:
        _flash(request, "error", "Section introuvable.")
    return RedirectResponse("/sections", status_code=303)


@router.post("/{section_id}/assign", response_class=HTMLResponse)
def assign(section_id: int, request: Request, trainee_id: int = Form(...), db: Session = Depends(get_db)):
    crud.assign_trainee(db, trainee_id, section_id)
    return _render_assign_lists(request, db, section_id)


@router.post("/{section_id}/unassign", response_class=HTMLResponse)
def unassign(section_id: int, request: Request, trainee_id: int = Form(...), db: Session = Depends(get_db)):
    crud.unassign_trainee(db, trainee_id, section_id)
    return _render_assign_lists(request, db, section_id)
