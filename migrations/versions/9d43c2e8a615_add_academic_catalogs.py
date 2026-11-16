"""Add courses, curricular units, and classes.

Revision ID: 9d43c2e8a615
Revises: 851c54bf9e7d
Create Date: 2026-11-16 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9d43c2e8a615"
down_revision = "851c54bf9e7d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "curricular_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("workload_hours", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "course_id", "name", name="uq_curricular_units_course_name"
        ),
    )
    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "name", name="uq_classes_course_name"),
    )


def downgrade():
    op.drop_table("classes")
    op.drop_table("curricular_units")
    op.drop_table("courses")
