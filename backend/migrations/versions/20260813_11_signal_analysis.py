"""Persist structured AI signal analysis."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_11"
down_revision: str | None = "20260813_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name, column_type, value in (
        ("summary", sa.Text(), ""),
        ("analysis_rationale", sa.Text(), ""),
        ("analysis_model", sa.String(100), ""),
        ("ai_analyzed", sa.Integer(), 0),
    ):
        op.add_column("external_signals", sa.Column(name, column_type, nullable=True))
        op.execute(
            sa.text(f"UPDATE external_signals SET {name} = :value WHERE {name} IS NULL")
            .bindparams(value=value)
        )
        op.alter_column(
            "external_signals",
            name,
            existing_type=column_type,
            nullable=False,
        )


def downgrade() -> None:
    op.drop_column("external_signals", "ai_analyzed")
    op.drop_column("external_signals", "analysis_model")
    op.drop_column("external_signals", "analysis_rationale")
    op.drop_column("external_signals", "summary")
