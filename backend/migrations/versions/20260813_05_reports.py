"""Add reports, immutable versions, and daily intelligence snapshots."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_05"
down_revision: str | None = "20260813_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_intelligence_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("covered_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("structured_data_json", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approved_by", sa.String(64)),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "covered_date"),
    )
    op.create_index(
        "ix_daily_snapshots_workspace_status_date",
        "daily_intelligence_snapshots",
        ["workspace_id", "status", "covered_date"],
    )
    op.create_table(
        "reports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("report_period", sa.String(16), nullable=False),
        sa.Column("input_mode", sa.String(40), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("current_version_id", sa.String(64), nullable=False),
        sa.Column("input_snapshot_ids_json", sa.Text(), nullable=False),
        sa.Column("input_snapshot_dates_json", sa.Text(), nullable=False),
        sa.Column("approved_by", sa.String(64)),
        sa.Column("approved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_reports_workspace_period_start",
        "reports",
        ["workspace_id", "report_period", "period_start"],
    )
    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("report_id", sa.String(64), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(80), nullable=False),
        sa.Column("change_source", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("report_id", "version"),
    )
    op.create_index(
        "ix_report_versions_report_created",
        "report_versions",
        ["report_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("report_versions")
    op.drop_table("reports")
    op.drop_table("daily_intelligence_snapshots")
