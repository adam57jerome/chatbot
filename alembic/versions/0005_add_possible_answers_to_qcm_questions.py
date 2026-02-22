"""add possible answers to qcm questions

Revision ID: 0005_add_possible_answers_to_qcm_questions
Revises: 0004_qcm_question_hierarchy
Create Date: 2026-02-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_possible_answers_to_qcm_questions"
down_revision: Union[str, None] = "0004_qcm_question_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("qcm_questions", sa.Column("reponses_possibles", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("qcm_questions", "reponses_possibles")
