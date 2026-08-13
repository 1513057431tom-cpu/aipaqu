"""Add material group hierarchy and agent run audit records."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_07"
down_revision: str | None = "20260813_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_groups",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("parent_id", sa.String(64), sa.ForeignKey("material_groups.id")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "code_key"),
    )
    op.create_index(
        "ix_material_groups_workspace_parent",
        "material_groups",
        ["workspace_id", "parent_id"],
    )
    op.add_column("materials", sa.Column("group_id", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_materials_group_id_material_groups",
        "materials",
        "material_groups",
        ["group_id"],
        ["id"],
    )
    op.create_index("ix_materials_group_id", "materials", ["group_id"])
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("agent_key", sa.String(80), nullable=False),
        sa.Column("execution_mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("material_ids_json", sa.Text(), nullable=False),
        sa.Column("steps_json", sa.Text(), nullable=False),
        sa.Column("model_invoked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
    )
    op.create_index(
        "ix_agent_runs_workspace_started",
        "agent_runs",
        ["workspace_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_index("ix_materials_group_id", table_name="materials")
    op.drop_constraint("fk_materials_group_id_material_groups", "materials", type_="foreignkey")
    op.drop_column("materials", "group_id")
    op.drop_table("material_groups")
