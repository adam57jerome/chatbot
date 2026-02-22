"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-11 00:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("date_debut", sa.Date(), nullable=True),
        sa.Column("date_fin", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_sections_code"), "sections", ["code"], unique=False)
    op.create_index(op.f("ix_sections_id"), "sections", ["id"], unique=False)

    op.create_table(
        "stagiaires",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(length=255), nullable=False),
        sa.Column("prenom", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("telephone", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("section_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["section_id"], ["sections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_stagiaires_email"), "stagiaires", ["email"], unique=False)
    op.create_index(op.f("ix_stagiaires_id"), "stagiaires", ["id"], unique=False)
    op.create_index(op.f("ix_stagiaires_nom"), "stagiaires", ["nom"], unique=False)
    op.create_index(op.f("ix_stagiaires_prenom"), "stagiaires", ["prenom"], unique=False)
    op.create_index(op.f("ix_stagiaires_section_id"), "stagiaires", ["section_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stagiaires_section_id"), table_name="stagiaires")
    op.drop_index(op.f("ix_stagiaires_prenom"), table_name="stagiaires")
    op.drop_index(op.f("ix_stagiaires_nom"), table_name="stagiaires")
    op.drop_index(op.f("ix_stagiaires_id"), table_name="stagiaires")
    op.drop_index(op.f("ix_stagiaires_email"), table_name="stagiaires")
    op.drop_table("stagiaires")
    op.drop_index(op.f("ix_sections_id"), table_name="sections")
    op.drop_index(op.f("ix_sections_code"), table_name="sections")
    op.drop_table("sections")
