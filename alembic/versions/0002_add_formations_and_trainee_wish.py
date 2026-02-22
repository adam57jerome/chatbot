"""add formations and trainee desired formation

Revision ID: 0002_add_formations
Revises: 0001_initial
Create Date: 2026-02-11 23:45:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_add_formations"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "formations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("actif", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_formations_id"), "formations", ["id"], unique=False)
    op.create_index(op.f("ix_formations_code"), "formations", ["code"], unique=False)

    op.add_column("stagiaires", sa.Column("formation_souhaitee_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_stagiaires_formation_souhaitee_id"), "stagiaires", ["formation_souhaitee_id"], unique=False)
    op.create_foreign_key(
        "fk_stagiaires_formation_souhaitee_id_formations",
        "stagiaires",
        "formations",
        ["formation_souhaitee_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_stagiaires_formation_souhaitee_id_formations", "stagiaires", type_="foreignkey")
    op.drop_index(op.f("ix_stagiaires_formation_souhaitee_id"), table_name="stagiaires")
    op.drop_column("stagiaires", "formation_souhaitee_id")

    op.drop_index(op.f("ix_formations_code"), table_name="formations")
    op.drop_index(op.f("ix_formations_id"), table_name="formations")
    op.drop_table("formations")
