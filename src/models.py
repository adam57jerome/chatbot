from __future__ import annotations

from datetime import datetime, date

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reference_score_20: Mapped[float] = mapped_column(Float, default=15.0)

    sections = relationship("Section", back_populates="questionnaire", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="questionnaire", cascade="all, delete-orphan")


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("questionnaire_id", "name", name="uq_section_questionnaire_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordre: Mapped[int] = mapped_column(Integer, default=0)

    questionnaire = relationship("Questionnaire", back_populates="sections")
    questions = relationship("Question", back_populates="section", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("questionnaire_id", "numero", name="uq_questionnaire_numero"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    bonne_reponse: Mapped[str] = mapped_column(String(10), nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=1)

    questionnaire = relationship("Questionnaire", back_populates="questions")
    section = relationship("Section", back_populates="questions")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    date_debut: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    trainees = relationship("Trainee", back_populates="session", cascade="all, delete-orphan")


class Trainee(Base):
    __tablename__ = "trainees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    prenom: Mapped[str] = mapped_column(String(255), nullable=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)

    session = relationship("Session", back_populates="trainees")


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("session_id", "questionnaire_id", "trainee_id", name="uq_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    questionnaire_id: Mapped[int] = mapped_column(ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False)
    trainee_id: Mapped[int] = mapped_column(ForeignKey("trainees.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    answers = relationship("Answer", back_populates="attempt", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    reponse_texte: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempt = relationship("Attempt", back_populates="answers")
