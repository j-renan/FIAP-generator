"""Add FIAP evaluations and temporary drafts.

Revision ID: 301ec1a9f070
Revises: bd48206e78a1
Create Date: 2026-11-16 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "301ec1a9f070"
down_revision = "bd48206e78a1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evaluation_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_evaluation_drafts_expires_at"),
        "evaluation_drafts",
        ["expires_at"],
        unique=False,
    )
    op.create_table(
        "evaluation_sheets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("curricular_unit_id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("evaluated_on", sa.Date(), nullable=False),
        sa.Column("workload_hours", sa.Integer(), nullable=False),
        sa.Column("class_average", sa.Integer(), nullable=False),
        sa.Column("student_grade", sa.Integer(), nullable=False),
        sa.Column("absence_limit_hours", sa.Integer(), nullable=False),
        sa.Column("absences_hours", sa.Integer(), nullable=False),
        sa.Column("difficulties", sa.Text(), nullable=False),
        sa.Column("recommendations", sa.Text(), nullable=False),
        sa.Column("school_actions", sa.Text(), nullable=False),
        sa.Column("observations", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["curricular_unit_id"],
            ["curricular_units.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("evaluation_sheets")
    op.drop_index(
        op.f("ix_evaluation_drafts_expires_at"),
        table_name="evaluation_drafts",
    )
    op.drop_table("evaluation_drafts")
