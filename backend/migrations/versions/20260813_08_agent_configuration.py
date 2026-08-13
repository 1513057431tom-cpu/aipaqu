"""Add encrypted model and editable agent configuration."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_08"
down_revision: str | None = "20260813_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_configurations",
        sa.Column("workspace_id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("encrypted_api_key", sa.Text()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "agent_configurations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("agent_key", sa.String(80), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("default_execution_mode", sa.String(16), nullable=False),
        sa.Column("tool_keys_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "agent_key"),
    )
    op.create_index("ix_agent_configurations_workspace_id", "agent_configurations", ["workspace_id"])


def downgrade() -> None:
    op.drop_table("agent_configurations")
    op.drop_table("model_configurations")
