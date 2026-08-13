from datetime import date, datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.core.reports import (
    DailyIntelligenceSnapshot,
    Report,
    ReportPeriod,
    ReportStatus,
    ReportVersion,
    SnapshotStatus,
)
from app.persistence.models import Base
from app.persistence.stores import SqlAlchemyReportStore


def create_test_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


def test_report_version_and_approved_snapshot_survive_store_recreation() -> None:
    now = datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc)
    snapshot = DailyIntelligenceSnapshot(
        id="daily-db-001",
        workspace_id="storage-test",
        covered_date=date(2026, 8, 13),
        timezone="Asia/Shanghai",
        structured_data_json='{"coveredDate":"2026-08-13"}',
        content_digest="sha256:snapshot",
        status=SnapshotStatus.READY,
        approved_by=None,
        approved_at=None,
        created_at=now,
    )
    version = ReportVersion(
        id="rpv-db-001",
        report_id="report-db-001",
        version=1,
        markdown="# Daily report",
        content_digest="sha256:version",
        change_source="SYSTEM_DRAFT",
        created_by="user-1",
        created_at=now,
    )
    report = Report(
        id="report-db-001",
        workspace_id="storage-test",
        title="Daily report",
        report_period=ReportPeriod.DAILY,
        input_mode="COLLECT_AND_ANALYZE",
        period_start=date(2026, 8, 13),
        period_end=date(2026, 8, 13),
        status=ReportStatus.DRAFT,
        current_version_id=version.id,
        input_snapshot_ids=(snapshot.id,),
        input_snapshot_dates=(snapshot.covered_date,),
        approved_by=None,
        approved_at=None,
        created_at=now,
        updated_at=now,
    )
    engine = create_test_engine()
    SqlAlchemyReportStore(engine).create(report, version, snapshot)

    recreated = SqlAlchemyReportStore(engine)
    assert recreated.get("storage-test", report.id) == report
    assert recreated.get_version(version.id) == version

    approved_report = Report(
        **{
            **report.__dict__,
            "status": ReportStatus.APPROVED,
            "approved_by": "user-1",
            "approved_at": now,
        }
    )
    approved_snapshot = DailyIntelligenceSnapshot(
        **{
            **snapshot.__dict__,
            "status": SnapshotStatus.APPROVED,
            "approved_by": "user-1",
            "approved_at": now,
        }
    )
    recreated.approve(approved_report, approved_snapshot)

    assert recreated.get("storage-test", report.id).status == ReportStatus.APPROVED
    assert recreated.get_daily_snapshot(
        "storage-test", date(2026, 8, 13)
    ).status == SnapshotStatus.APPROVED
