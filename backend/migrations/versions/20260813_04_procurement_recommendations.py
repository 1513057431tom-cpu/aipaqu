"""Add procurement recommendations and decision audit."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_04"
down_revision: str | None = "20260813_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "procurement_recommendations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("recommended_order_date", sa.Date(), nullable=False),
        sa.Column("latest_order_date", sa.Date(), nullable=False),
        sa.Column("recommended_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("calculation_json", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("input_digest", sa.String(80), nullable=False),
        sa.Column("algorithm_key", sa.String(80), nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("external_signal_ids_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "material_id", "input_digest"),
    )
    op.create_index(
        "ix_recommendations_workspace_status_risk",
        "procurement_recommendations",
        ["workspace_id", "status", "risk_level"],
    )
    op.create_table(
        "recommendation_decisions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("recommendation_id", sa.String(64), sa.ForeignKey("procurement_recommendations.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("adjusted_order_date", sa.Date()),
        sa.Column("adjusted_qty", sa.Float()),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_recommendation_decisions_recommendation_created",
        "recommendation_decisions",
        ["recommendation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("recommendation_decisions")
    op.drop_table("procurement_recommendations")
