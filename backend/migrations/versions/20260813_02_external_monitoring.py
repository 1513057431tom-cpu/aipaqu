"""Add external monitoring and evidence tables."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_02"
down_revision: str | None = "20260813_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("target_url_key", sa.String(64), nullable=False),
        sa.Column("allowed_domain", sa.String(253), nullable=False),
        sa.Column("schedule_minutes", sa.Integer(), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("material_id", sa.String(64)),
        sa.Column("supplier_id", sa.String(64)),
        sa.Column("extraction_selector", sa.String(200), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_collected_at", sa.DateTime()),
        sa.Column("last_collection_status", sa.String(32)),
        sa.Column("last_content_digest", sa.String(64)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "target_url_key"),
    )
    op.create_index("ix_sources_workspace_id", "sources", ["workspace_id"])
    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("document_id", sa.String(64)),
        sa.Column("content_changed", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message", sa.String(500)),
    )
    op.create_index(
        "ix_collection_jobs_workspace_source_started",
        "collection_jobs",
        ["workspace_id", "source_id", "started_at"],
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("collection_job_id", sa.String(64), nullable=False, unique=True),
        sa.Column("final_url", sa.String(2048), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("previous_content_digest", sa.String(64)),
        sa.Column("changed", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_documents_workspace_source_collected",
        "documents",
        ["workspace_id", "source_id", "collected_at"],
    )
    op.create_table(
        "external_signals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(64), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("document_id", sa.String(64), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("material_id", sa.String(64)),
        sa.Column("supplier_id", sa.String(64)),
        sa.Column("binding_key", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=False),
        sa.Column("current_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_ref", sa.String(255), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("source_id", "signal_type", "binding_key", "content_digest"),
    )
    op.create_index(
        "ix_external_signals_workspace_observed",
        "external_signals",
        ["workspace_id", "observed_at"],
    )
    op.create_index(
        "ix_external_signals_material_type",
        "external_signals",
        ["material_id", "signal_type", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("external_signals")
    op.drop_table("documents")
    op.drop_table("collection_jobs")
    op.drop_table("sources")
