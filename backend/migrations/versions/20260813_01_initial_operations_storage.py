"""Create catalog and internal data tables."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260813_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("external_code", sa.String(80), nullable=False),
        sa.Column("external_code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("specification", sa.String(500), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("base_unit", sa.String(32), nullable=False),
        sa.Column("safety_stock_qty", sa.Float(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "external_code_key"),
    )
    op.create_index("ix_materials_workspace_id", "materials", ["workspace_id"])
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("external_code", sa.String(80), nullable=False),
        sa.Column("external_code_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("website", sa.String(500)),
        sa.Column("country", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "external_code_key"),
    )
    op.create_index("ix_suppliers_workspace_id", "suppliers", ["workspace_id"])
    op.create_table(
        "internal_data_imports",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("data_type", sa.String(32), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("created_rows", sa.Integer(), nullable=False),
        sa.Column("failed_rows", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.Text(), nullable=False),
        sa.UniqueConstraint("workspace_id", "idempotency_key"),
    )
    op.create_index("ix_internal_data_imports_workspace_id", "internal_data_imports", ["workspace_id"])
    _create_internal_tables()


def _create_internal_tables() -> None:
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("location_code", sa.String(80), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(), nullable=False),
        sa.Column("on_hand_qty", sa.Float(), nullable=False),
        sa.Column("available_qty", sa.Float(), nullable=False),
        sa.Column("reserved_qty", sa.Float(), nullable=False),
        sa.Column("quality_hold_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("source_record_ref", sa.String(240), nullable=False),
        sa.Column("sync_job_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
    )
    op.create_index("ix_inventory_workspace_material_time", "inventory_snapshots", ["workspace_id", "material_id", "snapshot_at"])
    op.create_index("ix_inventory_snapshots_sync_job_id", "inventory_snapshots", ["sync_job_id"])
    op.create_table(
        "consumption_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("bucket_date", sa.Date(), nullable=False),
        sa.Column("actual_qty", sa.Float(), nullable=False),
        sa.Column("planned_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("source_record_ref", sa.String(240), nullable=False),
        sa.Column("sync_job_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
    )
    op.create_index("ix_consumption_workspace_material_date", "consumption_snapshots", ["workspace_id", "material_id", "bucket_date"])
    op.create_index("ix_consumption_snapshots_sync_job_id", "consumption_snapshots", ["sync_job_id"])
    op.create_table(
        "material_demands",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("required_at", sa.DateTime(), nullable=False),
        sa.Column("required_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("source_record_ref", sa.String(240), nullable=False),
        sa.Column("sync_job_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
    )
    op.create_index("ix_demand_workspace_material_time", "material_demands", ["workspace_id", "material_id", "required_at"])
    op.create_index("ix_material_demands_sync_job_id", "material_demands", ["sync_job_id"])
    op.create_table(
        "open_supply_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("material_id", sa.String(64), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("order_no", sa.String(120), nullable=False),
        sa.Column("order_line_no", sa.String(80), nullable=False),
        sa.Column("ordered_qty", sa.Float(), nullable=False),
        sa.Column("received_qty", sa.Float(), nullable=False),
        sa.Column("open_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("expected_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("source_record_ref", sa.String(240), nullable=False),
        sa.Column("sync_job_id", sa.String(64), nullable=False),
        sa.UniqueConstraint("workspace_id", "source_system", "source_record_ref"),
    )
    op.create_index("ix_supply_workspace_material_time", "open_supply_snapshots", ["workspace_id", "material_id", "expected_at"])
    op.create_index("ix_open_supply_snapshots_sync_job_id", "open_supply_snapshots", ["sync_job_id"])


def downgrade() -> None:
    op.drop_table("open_supply_snapshots")
    op.drop_table("material_demands")
    op.drop_table("consumption_snapshots")
    op.drop_table("inventory_snapshots")
    op.drop_table("internal_data_imports")
    op.drop_table("suppliers")
    op.drop_table("materials")
