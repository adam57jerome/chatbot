from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    date_debut: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stagiaires: Mapped[list["Stagiaire"]] = relationship(back_populates="section")


class Formation(Base):
    __tablename__ = "formations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1", default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    stagiaires_souhaits: Mapped[list["Stagiaire"]] = relationship(back_populates="formation_souhaitee")


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titre: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bareme_sur: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    questions: Mapped[list["QCMQuestion"]] = relationship(back_populates="questionnaire", cascade="all, delete-orphan")
    attempts: Mapped[list["QCMAttempt"]] = relationship(back_populates="questionnaire", cascade="all, delete-orphan")


class QCMQuestion(Base):
    __tablename__ = "qcm_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    questionnaire_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    enonce: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapitre: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    resultat_attendu: Mapped[str] = mapped_column(String(255), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    questionnaire: Mapped[Questionnaire] = relationship(back_populates="questions")
    answers: Mapped[list["QCMAnswer"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class QCMAttempt(Base):
    __tablename__ = "qcm_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaires.id"), nullable=False, index=True)
    stagiaire_id: Mapped[int] = mapped_column(ForeignKey("stagiaires.id"), nullable=False, index=True)
    date_passage: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    score_brut: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    note_sur_20: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    questionnaire: Mapped[Questionnaire] = relationship(back_populates="attempts")
    stagiaire: Mapped["Stagiaire"] = relationship(back_populates="qcm_attempts")
    answers: Mapped[list["QCMAnswer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")


class QCMAnswer(Base):
    __tablename__ = "qcm_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("qcm_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("qcm_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    reponse_stagiaire: Mapped[str | None] = mapped_column(String(255), nullable=True)
    est_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    point_obtenu: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    attempt: Mapped[QCMAttempt] = relationship(back_populates="answers")
    question: Mapped[QCMQuestion] = relationship(back_populates="answers")


class Stagiaire(Base):
    __tablename__ = "stagiaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    prenom: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    formation_souhaitee_id: Mapped[int | None] = mapped_column(
        ForeignKey("formations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    section: Mapped[Section | None] = relationship(back_populates="stagiaires")
    formation_souhaitee: Mapped[Formation | None] = relationship(back_populates="stagiaires_souhaits")
    qcm_attempts: Mapped[list[QCMAttempt]] = relationship(back_populates="stagiaire", cascade="all, delete-orphan")
