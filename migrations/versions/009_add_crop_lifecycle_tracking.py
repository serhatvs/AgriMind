"""Add crop lifecycle tracking to crop profiles and fields.

Revision ID: 009
Revises: 008
Create Date: 2026-03-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "growth_stages",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )

    op.create_table(
        "field_crop_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("crop_id", sa.Integer(), nullable=False),
        sa.Column("sowing_date", sa.Date(), nullable=False),
        sa.Column("current_stage", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crop_id"], ["crop_profiles.id"]),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("field_id", name="uq_field_crop_cycles_field_id"),
    )
    op.create_index("ix_field_crop_cycles_crop_id", "field_crop_cycles", ["crop_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_field_crop_cycles_crop_id", table_name="field_crop_cycles")
    op.drop_table("field_crop_cycles")

    with op.batch_alter_table("crop_profiles") as batch_op:
        batch_op.drop_column("growth_stages")
