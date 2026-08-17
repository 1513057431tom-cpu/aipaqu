from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.reports import DuplicateDailyReportError, ReportPeriod, ReportStatus


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntelligencePipelineResult:
    recommendation_count: int
    recommendation_skipped_count: int
    report_id: str | None
    report_created: bool
    errors: tuple[str, ...]


class IntelligencePipelineService:
    """Runs the downstream planning and reporting stages after collection."""

    def __init__(
        self,
        planning_engine,
        report_service,
        report_store,
        agent_service,
        horizon_days: int = 30,
    ) -> None:
        self.planning_engine = planning_engine
        self.report_service = report_service
        self.report_store = report_store
        self.agent_service = agent_service
        self.horizon_days = horizon_days

    def run(
        self,
        workspace_id: str,
        actor_id: str,
        observed_at: datetime,
    ) -> IntelligencePipelineResult:
        covered_date = observed_at.astimezone(ZoneInfo("Asia/Shanghai")).date()
        recommendation_count = 0
        skipped_count = 0
        errors: list[str] = []

        try:
            generation = self.planning_engine.generate(
                workspace_id,
                covered_date,
                self.horizon_days,
            )
            recommendation_count = len(generation.recommendations)
            skipped_count = len(generation.skipped)
        except Exception as exc:
            errors.append(f"采购建议生成失败：{type(exc).__name__}")
            logger.exception("Procurement planning failed after collection")

        existing = next(
            (
                report
                for report in self.report_store.list(workspace_id)
                if report.report_period == ReportPeriod.DAILY
                and report.period_start == covered_date
            ),
            None,
        )
        if existing is not None:
            if existing.status == ReportStatus.DRAFT:
                try:
                    template = self.agent_service.get_report_template(
                        workspace_id,
                        ReportPeriod.DAILY.value,
                    )
                    self.report_service.refresh_daily(
                        workspace_id,
                        existing.id,
                        actor_id,
                        template.content,
                    )
                except Exception as exc:
                    errors.append(f"日报刷新失败：{type(exc).__name__}")
                    logger.exception("Daily report refresh failed after collection")
            return IntelligencePipelineResult(
                recommendation_count=recommendation_count,
                recommendation_skipped_count=skipped_count,
                report_id=existing.id,
                report_created=False,
                errors=tuple(errors),
            )

        try:
            template = self.agent_service.get_report_template(
                workspace_id,
                ReportPeriod.DAILY.value,
            )
            report, _ = self.report_service.create(
                workspace_id,
                actor_id,
                f"{covered_date.isoformat()} 物料情报日报",
                ReportPeriod.DAILY,
                covered_date,
                covered_date,
                template.content,
            )
            return IntelligencePipelineResult(
                recommendation_count=recommendation_count,
                recommendation_skipped_count=skipped_count,
                report_id=report.id,
                report_created=True,
                errors=tuple(errors),
            )
        except DuplicateDailyReportError:
            existing = next(
                (
                    report
                    for report in self.report_store.list(workspace_id)
                    if report.report_period == ReportPeriod.DAILY
                    and report.period_start == covered_date
                ),
                None,
            )
            return IntelligencePipelineResult(
                recommendation_count=recommendation_count,
                recommendation_skipped_count=skipped_count,
                report_id=existing.id if existing else None,
                report_created=False,
                errors=tuple(errors),
            )
        except Exception as exc:
            errors.append(f"日报生成失败：{type(exc).__name__}")
            logger.exception("Daily report generation failed after collection")
            return IntelligencePipelineResult(
                recommendation_count=recommendation_count,
                recommendation_skipped_count=skipped_count,
                report_id=None,
                report_created=False,
                errors=tuple(errors),
            )
