"""add chapitre/sous_chapitre hierarchy to qcm_questions

Revision ID: 0004_qcm_question_hierarchy
Revises: 0003_add_qcm_module
Create Date: 2026-02-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_qcm_question_hierarchy"
down_revision: Union[str, None] = "0003_add_qcm_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("qcm_questions", sa.Column("chapitre", sa.String(length=120), nullable=True))
    op.add_column("qcm_questions", sa.Column("sous_chapitre", sa.String(length=120), nullable=True))
    op.create_index(op.f("ix_qcm_questions_chapitre"), "qcm_questions", ["chapitre"], unique=False)
    op.create_index(op.f("ix_qcm_questions_sous_chapitre"), "qcm_questions", ["sous_chapitre"], unique=False)

    op.execute("UPDATE qcm_questions SET chapitre='Général' WHERE chapitre IS NULL OR trim(chapitre) = ''")

    with op.batch_alter_table("qcm_questions") as batch_op:
        batch_op.alter_column("chapitre", existing_type=sa.String(length=120), nullable=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_qcm_questions_sous_chapitre"), table_name="qcm_questions")
    op.drop_index(op.f("ix_qcm_questions_chapitre"), table_name="qcm_questions")
    op.drop_column("qcm_questions", "sous_chapitre")
    op.drop_column("qcm_questions", "chapitre")
