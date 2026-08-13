"""Add signal review audit fields."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_03"
down_revision: str | None = "20260813_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "external_signals",
        sa.Column("reviewed_by", sa.String(64), nullable=True),
    )
    op.add_column(
        "external_signals",
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("external_signals", "reviewed_at")
    op.drop_column("external_signals", "reviewed_by")
