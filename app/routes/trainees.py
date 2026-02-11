from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.db import get_db
from app.main import templates

router = APIRouter(prefix="/stagiaires", tags=["stagiaires"])


def _flash(request: Request, kind: str, message: str) -> None:
    request.session["flash"] = {"kind": kind, "message": message}


@router.get("", response_class=HTMLResponse)
def list_trainees(request: Request, q: str | None = None, section: str | None = None, page: int = 1, db: Session = Depends(get_db)):
    trainees, total = crud.list_stagiaires(db, q=q, section_filter=section, page=page)
    sections, _ = crud.list_sections(db, page=1, per_page=500)
    return templates.TemplateResponse(
        "trainees_list.html",
        {
            "request": request,
            "trainees": trainees,
            "sections": sections,
            "q": q or "",
            "section_filter": section or "",
            "page": page,
            "has_next": page * 50 < total,
            "has_prev": page > 1,
        },
    )


@router.get("/nouveau", response_class=HTMLResponse)
def new_trainee_form(request: Request, db: Session = Depends(get_db)):
    sections, _ = crud.list_sections(db, page=1, per_page=500)
    return templates.TemplateResponse("trainee_form.html", {"request": request, "sections": sections, "trainee": None, "errors": {}})


@router.post("/nouveau")
def create_trainee(
    request: Request,
    nom: str = Form(...),
    prenom: str = Form(...),
    email: str | None = Form(None),
    telephone: str | None = Form(None),
    notes: str | None = Form(None),
    section_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    sections, _ = crud.list_sections(db, page=1, per_page=500)
    payload_data = {
        "nom": nom,
        "prenom": prenom,
        "email": email or None,
        "telephone": telephone or None,
        "notes": notes or None,
        "section_id": int(section_id) if section_id else None,
    }
    try:
        payload = schemas.StagiaireCreate(**payload_data)
        trainee = crud.create_stagiaire(db, payload)
        _flash(request, "success", "Stagiaire créé avec succès.")
        return RedirectResponse(f"/stagiaires/{trainee.id}", status_code=303)
    except ValidationError as exc:
        errors = {e["loc"][-1]: e["msg"] for e in exc.errors()}
    except IntegrityError:
        db.rollback()
        errors = {"email": "Cet email est déjà utilisé."}

    return templates.TemplateResponse(
        "trainee_form.html",
        {
            "request": request,
            "sections": sections,
            "trainee": payload_data,
            "errors": errors,
        },
        status_code=400,
    )


@router.get("/{trainee_id}", response_class=HTMLResponse)
def trainee_detail(trainee_id: int, request: Request, db: Session = Depends(get_db)):
    trainee = crud.get_stagiaire(db, trainee_id)
    if not trainee:
        _flash(request, "error", "Stagiaire introuvable.")
        return RedirectResponse("/stagiaires", status_code=303)
    return templates.TemplateResponse("trainee_detail.html", {"request": request, "trainee": trainee})


@router.get("/{trainee_id}/edit", response_class=HTMLResponse)
def edit_trainee_form(trainee_id: int, request: Request, db: Session = Depends(get_db)):
    trainee = crud.get_stagiaire(db, trainee_id)
    if not trainee:
        _flash(request, "error", "Stagiaire introuvable.")
        return RedirectResponse("/stagiaires", status_code=303)
    sections, _ = crud.list_sections(db, page=1, per_page=500)
    return templates.TemplateResponse("trainee_form.html", {"request": request, "sections": sections, "trainee": trainee, "errors": {}})


@router.post("/{trainee_id}/edit")
def update_trainee(
    trainee_id: int,
    request: Request,
    nom: str = Form(...),
    prenom: str = Form(...),
    email: str | None = Form(None),
    telephone: str | None = Form(None),
    notes: str | None = Form(None),
    section_id: str | None = Form(None),
    db: Session = Depends(get_db),
):
    trainee = crud.get_stagiaire(db, trainee_id)
    if not trainee:
        _flash(request, "error", "Stagiaire introuvable.")
        return RedirectResponse("/stagiaires", status_code=303)

    sections, _ = crud.list_sections(db, page=1, per_page=500)
    payload_data = {
        "nom": nom,
        "prenom": prenom,
        "email": email or None,
        "telephone": telephone or None,
        "notes": notes or None,
        "section_id": int(section_id) if section_id else None,
    }

    try:
        payload = schemas.StagiaireUpdate(**payload_data)
        crud.update_stagiaire(db, trainee, payload)
        _flash(request, "success", "Stagiaire mis à jour.")
        return RedirectResponse(f"/stagiaires/{trainee.id}", status_code=303)
    except ValidationError as exc:
        errors = {e["loc"][-1]: e["msg"] for e in exc.errors()}
    except IntegrityError:
        db.rollback()
        errors = {"email": "Cet email est déjà utilisé."}

    payload_data["id"] = trainee.id
    return templates.TemplateResponse(
        "trainee_form.html",
        {"request": request, "sections": sections, "trainee": payload_data, "errors": errors},
        status_code=400,
    )


@router.post("/{trainee_id}/delete")
def delete_trainee(trainee_id: int, request: Request, db: Session = Depends(get_db)):
    trainee = crud.get_stagiaire(db, trainee_id)
    if trainee:
        crud.delete_stagiaire(db, trainee)
        _flash(request, "success", "Stagiaire supprimé.")
    else:
        _flash(request, "error", "Stagiaire introuvable.")
    return RedirectResponse("/stagiaires", status_code=303)
