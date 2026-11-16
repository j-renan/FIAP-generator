"""Add students and temporary import previews.

Revision ID: bd48206e78a1
Revises: 9d43c2e8a615
Create Date: 2026-11-16 09:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "bd48206e78a1"
down_revision = "9d43c2e8a615"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("class_id", "name", name="uq_students_class_name"),
    )
    op.create_table(
        "student_import_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("rows_json", sa.Text(), nullable=False),
        sa.Column("has_errors", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["class_id"], ["classes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_student_import_batches_expires_at"),
        "student_import_batches",
        ["expires_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        op.f("ix_student_import_batches_expires_at"),
        table_name="student_import_batches",
    )
    op.drop_table("student_import_batches")
    op.drop_table("students")
