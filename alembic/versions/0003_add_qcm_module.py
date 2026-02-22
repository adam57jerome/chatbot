"""add qcm module tables

Revision ID: 0003_add_qcm_module
Revises: 0002_add_formations
Create Date: 2026-02-12 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_qcm_module"
down_revision: Union[str, None] = "0002_add_formations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "questionnaires",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titre", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("bareme_sur", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_questionnaires_id"), "questionnaires", ["id"], unique=False)
    op.create_index(op.f("ix_questionnaires_titre"), "questionnaires", ["titre"], unique=False)

    op.create_table(
        "qcm_questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("enonce", sa.Text(), nullable=True),
        sa.Column("resultat_attendu", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["questionnaire_id"], ["questionnaires.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("questionnaire_id", "numero", name="uq_qcm_questionnaire_numero"),
    )
    op.create_index(op.f("ix_qcm_questions_id"), "qcm_questions", ["id"], unique=False)
    op.create_index(op.f("ix_qcm_questions_questionnaire_id"), "qcm_questions", ["questionnaire_id"], unique=False)

    op.create_table(
        "qcm_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("questionnaire_id", sa.Integer(), nullable=False),
        sa.Column("stagiaire_id", sa.Integer(), nullable=False),
        sa.Column("date_passage", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("score_brut", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note_sur_20", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["questionnaire_id"], ["questionnaires.id"]),
        sa.ForeignKeyConstraint(["stagiaire_id"], ["stagiaires.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_qcm_attempts_id"), "qcm_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_qcm_attempts_questionnaire_id"), "qcm_attempts", ["questionnaire_id"], unique=False)
    op.create_index(op.f("ix_qcm_attempts_stagiaire_id"), "qcm_attempts", ["stagiaire_id"], unique=False)

    op.create_table(
        "qcm_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attempt_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("reponse_stagiaire", sa.String(length=255), nullable=True),
        sa.Column("est_correct", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("point_obtenu", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["attempt_id"], ["qcm_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["qcm_questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_question"),
    )
    op.create_index(op.f("ix_qcm_answers_id"), "qcm_answers", ["id"], unique=False)
    op.create_index(op.f("ix_qcm_answers_attempt_id"), "qcm_answers", ["attempt_id"], unique=False)
    op.create_index(op.f("ix_qcm_answers_question_id"), "qcm_answers", ["question_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_qcm_answers_question_id"), table_name="qcm_answers")
    op.drop_index(op.f("ix_qcm_answers_attempt_id"), table_name="qcm_answers")
    op.drop_index(op.f("ix_qcm_answers_id"), table_name="qcm_answers")
    op.drop_table("qcm_answers")

    op.drop_index(op.f("ix_qcm_attempts_stagiaire_id"), table_name="qcm_attempts")
    op.drop_index(op.f("ix_qcm_attempts_questionnaire_id"), table_name="qcm_attempts")
    op.drop_index(op.f("ix_qcm_attempts_id"), table_name="qcm_attempts")
    op.drop_table("qcm_attempts")

    op.drop_index(op.f("ix_qcm_questions_questionnaire_id"), table_name="qcm_questions")
    op.drop_index(op.f("ix_qcm_questions_id"), table_name="qcm_questions")
    op.drop_table("qcm_questions")

    op.drop_index(op.f("ix_questionnaires_titre"), table_name="questionnaires")
    op.drop_index(op.f("ix_questionnaires_id"), table_name="questionnaires")
    op.drop_table("questionnaires")
