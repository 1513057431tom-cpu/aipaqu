"""Allow large report bodies and snapshot payloads."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "20260813_06"
down_revision: str | None = "20260813_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "daily_intelligence_snapshots",
        "structured_data_json",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT(),
        existing_nullable=False,
    )
    op.alter_column(
        "report_versions",
        "markdown",
        existing_type=sa.Text(),
        type_=mysql.LONGTEXT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "report_versions",
        "markdown",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "daily_intelligence_snapshots",
        "structured_data_json",
        existing_type=mysql.LONGTEXT(),
        type_=sa.Text(),
        existing_nullable=False,
    )
