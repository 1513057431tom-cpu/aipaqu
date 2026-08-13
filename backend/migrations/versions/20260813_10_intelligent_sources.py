"""Add intelligent browser collection and material group bindings."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_10"
down_revision: str | None = "20260813_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("sources")}
    indexes = {index["name"] for index in inspector.get_indexes("sources")}
    if "material_group_id" not in columns:
        op.add_column("sources", sa.Column("material_group_id", sa.String(64)))
    if "collection_mode" not in columns:
        op.add_column(
            "sources",
            sa.Column("collection_mode", sa.String(32), nullable=False, server_default="HTTP"),
        )
    if "navigation_goal" not in columns:
        op.add_column("sources", sa.Column("navigation_goal", sa.Text(), nullable=True))
        op.execute(sa.text("UPDATE sources SET navigation_goal = '' WHERE navigation_goal IS NULL"))
        op.alter_column("sources", "navigation_goal", existing_type=sa.Text(), nullable=False)
    if "ix_sources_material_group_id" not in indexes:
        op.create_index("ix_sources_material_group_id", "sources", ["material_group_id"])


def downgrade() -> None:
    op.drop_index("ix_sources_material_group_id", table_name="sources")
    op.drop_column("sources", "navigation_goal")
    op.drop_column("sources", "collection_mode")
    op.drop_column("sources", "material_group_id")
