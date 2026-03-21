"""Add ingestion foundation tables for automated source pipelines.

Revision ID: 011
Revises: 010
Create Date: 2026-03-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


data_source_type_enum = sa.Enum(
    "api",
    "file",
    "database",
    "webhook",
    name="data_source_type_enum",
    native_enum=False,
)
ingestion_run_type_enum = sa.Enum(
    "full",
    "incremental",
    "backfill",
    name="ingestion_run_type_enum",
    native_enum=False,
)
ingestion_run_status_enum = sa.Enum(
    "pending",
    "running",
    "succeeded",
    "partial",
    "failed",
    name="ingestion_run_status_enum",
    native_enum=False,
)
ingestion_payload_type_enum = sa.Enum(
    "record",
    "batch",
    "json",
    name="ingestion_payload_type_enum",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", data_source_type_enum, nullable=False),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", name="uq_data_sources_source_name"),
    )
    op.create_index(op.f("ix_data_sources_id"), "data_sources", ["id"], unique=False)
    op.create_index(op.f("ix_data_sources_source_name"), "data_sources", ["source_name"], unique=False)

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("run_type", ingestion_run_type_enum, nullable=False),
        sa.Column("status", ingestion_run_status_enum, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_skipped", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("records_fetched >= 0", name="ck_ingestion_runs_records_fetched_non_negative"),
        sa.CheckConstraint("records_inserted >= 0", name="ck_ingestion_runs_records_inserted_non_negative"),
        sa.CheckConstraint("records_skipped >= 0", name="ck_ingestion_runs_records_skipped_non_negative"),
        sa.CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_ingestion_runs_finished_after_started",
        ),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_runs_data_source_id"), "ingestion_runs", ["data_source_id"], unique=False)
    op.create_index(op.f("ix_ingestion_runs_id"), "ingestion_runs", ["id"], unique=False)

    op.create_table(
        "raw_ingestion_payloads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=False),
        sa.Column("payload_type", ingestion_payload_type_enum, nullable=False),
        sa.Column("source_identifier", sa.String(length=255), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_raw_ingestion_payloads_id"), "raw_ingestion_payloads", ["id"], unique=False)
    op.create_index(
        op.f("ix_raw_ingestion_payloads_ingestion_run_id"),
        "raw_ingestion_payloads",
        ["ingestion_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_raw_ingestion_payloads_source_identifier"),
        "raw_ingestion_payloads",
        ["source_identifier"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_raw_ingestion_payloads_source_identifier"), table_name="raw_ingestion_payloads")
    op.drop_index(op.f("ix_raw_ingestion_payloads_ingestion_run_id"), table_name="raw_ingestion_payloads")
    op.drop_index(op.f("ix_raw_ingestion_payloads_id"), table_name="raw_ingestion_payloads")
    op.drop_table("raw_ingestion_payloads")

    op.drop_index(op.f("ix_ingestion_runs_id"), table_name="ingestion_runs")
    op.drop_index(op.f("ix_ingestion_runs_data_source_id"), table_name="ingestion_runs")
    op.drop_table("ingestion_runs")

    op.drop_index(op.f("ix_data_sources_source_name"), table_name="data_sources")
    op.drop_index(op.f("ix_data_sources_id"), table_name="data_sources")
    op.drop_table("data_sources")
