from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, ValidationInfo, field_validator


class SectionBase(BaseModel):
    code: str
    nom: str
    date_debut: date | None = None
    date_fin: date | None = None
    description: str | None = None

    @field_validator("code", "nom")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ est obligatoire.")
        return value

    @field_validator("date_fin")
    @classmethod
    def end_date_must_be_after_start(cls, value: date | None, info: ValidationInfo) -> date | None:
        date_debut = info.data.get("date_debut")
        if value and date_debut and value < date_debut:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début.")
        return value


class SectionCreate(SectionBase):
    pass


class SectionUpdate(SectionBase):
    pass


class FormationBase(BaseModel):
    code: str
    nom: str
    description: str | None = None
    actif: bool = True

    @field_validator("code", "nom")
    @classmethod
    def required_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ est obligatoire.")
        return value


class FormationCreate(FormationBase):
    pass


class FormationUpdate(FormationBase):
    pass


class StagiaireBase(BaseModel):
    nom: str
    prenom: str
    email: EmailStr | None = None
    telephone: str | None = None
    notes: str | None = None
    section_id: int | None = None
    formation_souhaitee_id: int | None = None

    @field_validator("nom", "prenom")
    @classmethod
    def names_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Ce champ est obligatoire.")
        return value


class StagiaireCreate(StagiaireBase):
    pass


class StagiaireUpdate(StagiaireBase):
    pass


class SectionRead(SectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class FormationRead(FormationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class StagiaireRead(StagiaireBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
