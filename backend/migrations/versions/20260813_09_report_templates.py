"""Add configurable report templates."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_09"
down_revision: str | None = "20260813_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "period"),
    )
    op.create_index("ix_report_templates_workspace_id", "report_templates", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("report_templates")
