"""add total_possible_points to qcm_attempts

Revision ID: 0006_add_total_possible_points_to_attempts
Revises: 0005_add_possible_answers_to_qcm_questions
Create Date: 2026-02-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_add_total_possible_points_to_attempts"
down_revision: Union[str, None] = "0005_add_possible_answers_to_qcm_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "qcm_attempts",
        sa.Column("total_possible_points", sa.Integer(), nullable=False, server_default="0"),
    )

    op.execute(
        """
        UPDATE qcm_attempts
        SET total_possible_points = (
            SELECT COALESCE(SUM(CASE WHEN qq.points > 0 THEN qq.points ELSE 0 END), 0)
            FROM qcm_questions qq
            WHERE qq.questionnaire_id = qcm_attempts.questionnaire_id
        )
        WHERE total_possible_points IS NULL OR total_possible_points <= 0
        """
    )


def downgrade() -> None:
    op.drop_column("qcm_attempts", "total_possible_points")
