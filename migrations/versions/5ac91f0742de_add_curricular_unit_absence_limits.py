"""Store the 25% absence limit for curricular units.

Revision ID: 5ac91f0742de
Revises: 301ec1a9f070
Create Date: 2026-11-16 16:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "5ac91f0742de"
down_revision = "301ec1a9f070"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("curricular_units") as batch_op:
        batch_op.add_column(
            sa.Column("max_absence_hours", sa.Numeric(7, 2), nullable=True)
        )

    op.execute(
        "UPDATE curricular_units "
        "SET max_absence_hours = workload_hours * 0.25"
    )

    with op.batch_alter_table("curricular_units") as batch_op:
        batch_op.alter_column(
            "max_absence_hours",
            existing_type=sa.Numeric(7, 2),
            nullable=False,
        )

    with op.batch_alter_table("evaluation_sheets") as batch_op:
        batch_op.alter_column(
            "absence_limit_hours",
            existing_type=sa.Integer(),
            type_=sa.Numeric(7, 2),
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("evaluation_sheets") as batch_op:
        batch_op.alter_column(
            "absence_limit_hours",
            existing_type=sa.Numeric(7, 2),
            type_=sa.Integer(),
            existing_nullable=False,
        )

    with op.batch_alter_table("curricular_units") as batch_op:
        batch_op.drop_column("max_absence_hours")
