from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.intelligence_pipeline import IntelligencePipelineService
from app.core.reports import ReportStatus


class PlanningEngineStub:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def generate(self, workspace_id, covered_date, horizon_days):
        self.calls.append((workspace_id, covered_date, horizon_days))
        return SimpleNamespace(recommendations=[object(), object()], skipped=[{"reason": "NO_DATA"}])


class ReportStoreStub:
    def __init__(self) -> None:
        self.reports: list = []

    def list(self, _workspace_id):
        return self.reports


class ReportServiceStub:
    def __init__(self, store: ReportStoreStub) -> None:
        self.store = store
        self.calls: list[tuple] = []
        self.refresh_calls: list[tuple] = []

    def create(self, *args):
        self.calls.append(args)
        report = SimpleNamespace(id="report-daily-1")
        self.store.reports.append(
            SimpleNamespace(
                id=report.id,
                report_period=args[3],
                period_start=args[4],
                status=ReportStatus.DRAFT,
            )
        )
        return report, SimpleNamespace(id="version-1")

    def refresh_daily(self, *args):
        self.refresh_calls.append(args)
        return SimpleNamespace(id=args[1]), SimpleNamespace(id="version-2")


class AgentServiceStub:
    @staticmethod
    def get_report_template(_workspace_id, _period):
        return SimpleNamespace(content="# {{title}}")


def test_pipeline_generates_planning_and_only_one_daily_report() -> None:
    planning = PlanningEngineStub()
    report_store = ReportStoreStub()
    report_service = ReportServiceStub(report_store)
    pipeline = IntelligencePipelineService(
        planning,
        report_service,
        report_store,
        AgentServiceStub(),
    )
    observed_at = datetime(2026, 8, 13, 16, 30, tzinfo=timezone.utc)

    first = pipeline.run("default", "user-1", observed_at)
    second = pipeline.run("default", "user-1", observed_at)

    assert planning.calls[0][1].isoformat() == "2026-08-14"
    assert first.recommendation_count == 2
    assert first.recommendation_skipped_count == 1
    assert first.report_created is True
    assert first.report_id == "report-daily-1"
    assert second.report_created is False
    assert len(report_service.calls) == 1
    assert len(report_service.refresh_calls) == 1
