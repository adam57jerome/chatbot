from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


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


class SectionCreate(SectionBase):
    pass


class SectionUpdate(SectionBase):
    pass


class StagiaireBase(BaseModel):
    nom: str
    prenom: str
    email: EmailStr | None = None
    telephone: str | None = None
    notes: str | None = None
    section_id: int | None = None

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


class StagiaireRead(StagiaireBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
