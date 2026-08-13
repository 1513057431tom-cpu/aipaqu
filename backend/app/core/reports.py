from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo


class ReportPeriod(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ReportStatus(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"


class SnapshotStatus(str, Enum):
    READY = "READY"
    APPROVED = "APPROVED"


class PeriodInputIncompleteError(ValueError):
    def __init__(self, missing_dates: list[date]) -> None:
        super().__init__("所选周期缺少已审核的日报快照。")
        self.missing_dates = missing_dates


class DuplicateDailyReportError(ValueError):
    pass


@dataclass(frozen=True)
class DailyIntelligenceSnapshot:
    id: str
    workspace_id: str
    covered_date: date
    timezone: str
    structured_data_json: str
    content_digest: str
    status: SnapshotStatus
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class ReportVersion:
    id: str
    report_id: str
    version: int
    markdown: str
    content_digest: str
    change_source: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class Report:
    id: str
    workspace_id: str
    title: str
    report_period: ReportPeriod
    input_mode: str
    period_start: date
    period_end: date
    status: ReportStatus
    current_version_id: str
    input_snapshot_ids: tuple[str, ...]
    input_snapshot_dates: tuple[date, ...]
    approved_by: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReportStore(Protocol):
    def create(self, report: Report, version: ReportVersion, snapshot: DailyIntelligenceSnapshot | None) -> Report: ...
    def list(self, workspace_id: str) -> list[Report]: ...
    def get(self, workspace_id: str, report_id: str) -> Report | None: ...
    def get_version(self, version_id: str) -> ReportVersion | None: ...
    def save_version(self, report: Report, version: ReportVersion) -> Report: ...
    def approve(self, report: Report, snapshot: DailyIntelligenceSnapshot | None) -> Report: ...
    def get_daily_snapshot(self, workspace_id: str, covered_date: date) -> DailyIntelligenceSnapshot | None: ...
    def list_daily_snapshots(self, workspace_id: str, start: date, end: date) -> list[DailyIntelligenceSnapshot]: ...


class InMemoryReportStore:
    def __init__(self) -> None:
        self._reports: dict[str, Report] = {}
        self._versions: dict[str, ReportVersion] = {}
        self._snapshots: dict[str, DailyIntelligenceSnapshot] = {}
        self._lock = RLock()

    def create(self, report: Report, version: ReportVersion, snapshot: DailyIntelligenceSnapshot | None) -> Report:
        with self._lock:
            if snapshot and self.get_daily_snapshot(snapshot.workspace_id, snapshot.covered_date):
                raise DuplicateDailyReportError("该日期已存在日报。")
            self._reports[report.id] = report
            self._versions[version.id] = version
            if snapshot:
                self._snapshots[snapshot.id] = snapshot
        return report

    def list(self, workspace_id: str) -> list[Report]:
        return sorted((r for r in self._reports.values() if r.workspace_id == workspace_id), key=lambda r: (r.period_start, r.id), reverse=True)

    def get(self, workspace_id: str, report_id: str) -> Report | None:
        report = self._reports.get(report_id)
        return report if report and report.workspace_id == workspace_id else None

    def get_version(self, version_id: str) -> ReportVersion | None:
        return self._versions.get(version_id)

    def save_version(self, report: Report, version: ReportVersion) -> Report:
        with self._lock:
            self._versions[version.id] = version
            self._reports[report.id] = report
        return report

    def approve(self, report: Report, snapshot: DailyIntelligenceSnapshot | None) -> Report:
        with self._lock:
            self._reports[report.id] = report
            if snapshot:
                self._snapshots[snapshot.id] = snapshot
        return report

    def get_daily_snapshot(self, workspace_id: str, covered_date: date) -> DailyIntelligenceSnapshot | None:
        return next((s for s in self._snapshots.values() if s.workspace_id == workspace_id and s.covered_date == covered_date), None)

    def list_daily_snapshots(self, workspace_id: str, start: date, end: date) -> list[DailyIntelligenceSnapshot]:
        return sorted((s for s in self._snapshots.values() if s.workspace_id == workspace_id and start <= s.covered_date <= end), key=lambda s: s.covered_date)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def _dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


class ReportService:
    def __init__(self, store: ReportStore, catalog_store, internal_store, monitoring_store, recommendation_store) -> None:
        self.store = store
        self.catalog_store = catalog_store
        self.internal_store = internal_store
        self.monitoring_store = monitoring_store
        self.recommendation_store = recommendation_store

    def create(self, workspace_id: str, actor_id: str, title: str, period: ReportPeriod, start: date, end: date) -> tuple[Report, ReportVersion]:
        if end < start:
            raise ValueError("Period end cannot be before period start.")
        if period == ReportPeriod.DAILY and start != end:
            raise ValueError("Daily reports must cover exactly one date.")
        snapshot: DailyIntelligenceSnapshot | None = None
        if period == ReportPeriod.DAILY:
            structured = self._daily_structured_data(workspace_id, start)
            structured_json = json.dumps(structured, sort_keys=True, ensure_ascii=False)
            now = datetime.now(timezone.utc)
            snapshot = DailyIntelligenceSnapshot(
                id=f"daily_{uuid4().hex}", workspace_id=workspace_id, covered_date=start,
                timezone="Asia/Shanghai", structured_data_json=structured_json,
                content_digest=_digest(structured_json), status=SnapshotStatus.READY,
                approved_by=None, approved_at=None, created_at=now,
            )
            snapshots = [snapshot]
            input_mode = "COLLECT_AND_ANALYZE"
        else:
            expected = _dates(start, end)
            snapshots = self.store.list_daily_snapshots(workspace_id, start, end)
            approved_by_date = {s.covered_date: s for s in snapshots if s.status == SnapshotStatus.APPROVED}
            missing = [day for day in expected if day not in approved_by_date]
            if missing:
                raise PeriodInputIncompleteError(missing)
            snapshots = [approved_by_date[day] for day in expected]
            input_mode = "AGGREGATE_DAILY_SNAPSHOTS"
            now = datetime.now(timezone.utc)
        report_id = f"report_{uuid4().hex}"
        markdown = self._markdown(title, period, start, end, snapshots)
        version = ReportVersion(
            id=f"rpv_{uuid4().hex}", report_id=report_id, version=1,
            markdown=markdown, content_digest=_digest(markdown), change_source="SYSTEM_DRAFT",
            created_by=actor_id, created_at=now,
        )
        report = Report(
            id=report_id, workspace_id=workspace_id, title=title.strip(), report_period=period,
            input_mode=input_mode, period_start=start, period_end=end, status=ReportStatus.DRAFT,
            current_version_id=version.id, input_snapshot_ids=tuple(s.id for s in snapshots),
            input_snapshot_dates=tuple(s.covered_date for s in snapshots), approved_by=None,
            approved_at=None, created_at=now, updated_at=now,
        )
        self.store.create(report, version, snapshot)
        return report, version

    def save_version(self, workspace_id: str, report_id: str, actor_id: str, markdown: str) -> tuple[Report, ReportVersion]:
        report = self._report(workspace_id, report_id)
        current = self.store.get_version(report.current_version_id)
        if report.status == ReportStatus.APPROVED:
            raise ValueError("Approved reports cannot be edited.")
        now = datetime.now(timezone.utc)
        version = ReportVersion(
            id=f"rpv_{uuid4().hex}", report_id=report.id,
            version=(current.version if current else 0) + 1, markdown=markdown,
            content_digest=_digest(markdown), change_source="MANUAL_EDIT",
            created_by=actor_id, created_at=now,
        )
        report = replace(report, current_version_id=version.id, updated_at=now)
        self.store.save_version(report, version)
        return report, version

    def approve(self, workspace_id: str, report_id: str, actor_id: str) -> tuple[Report, ReportVersion]:
        report = self._report(workspace_id, report_id)
        now = datetime.now(timezone.utc)
        report = replace(report, status=ReportStatus.APPROVED, approved_by=actor_id, approved_at=now, updated_at=now)
        snapshot = None
        if report.report_period == ReportPeriod.DAILY:
            snapshot = self.store.get_daily_snapshot(workspace_id, report.period_start)
            if snapshot:
                snapshot = replace(snapshot, status=SnapshotStatus.APPROVED, approved_by=actor_id, approved_at=now)
        self.store.approve(report, snapshot)
        version = self.store.get_version(report.current_version_id)
        if version is None:
            raise LookupError("Report version was not found.")
        return report, version

    def get(self, workspace_id: str, report_id: str) -> tuple[Report, ReportVersion]:
        report = self._report(workspace_id, report_id)
        version = self.store.get_version(report.current_version_id)
        if version is None:
            raise LookupError("Report version was not found.")
        return report, version

    def _report(self, workspace_id: str, report_id: str) -> Report:
        report = self.store.get(workspace_id, report_id)
        if report is None:
            raise LookupError("Report was not found.")
        return report

    def _daily_structured_data(self, workspace_id: str, covered_date: date) -> dict:
        local_timezone = ZoneInfo("Asia/Shanghai")
        signals = [
            signal
            for signal in self.monitoring_store.list_signals(workspace_id)
            if signal.observed_at.astimezone(local_timezone).date() == covered_date
        ]
        recommendations = [r for r in self.recommendation_store.list(workspace_id) if r.as_of_date == covered_date]
        return {
            "coveredDate": covered_date.isoformat(),
            "inventoryCount": len(self.internal_store.list_inventory(workspace_id)),
            "demandCount": len(self.internal_store.list_demands(workspace_id)),
            "openSupplyCount": len(self.internal_store.list_open_supply(workspace_id)),
            "confirmedSignals": [
                {"id": signal.id, "evidenceRef": signal.evidence_ref}
                for signal in signals
                if signal.review_status.value == "CONFIRMED"
            ],
            "recommendations": [
                {
                    "id": recommendation.id,
                    "materialId": recommendation.material_id,
                    "qty": recommendation.recommended_qty,
                    "unit": recommendation.unit,
                    "status": recommendation.status.value,
                    "evidenceRefs": list(recommendation.evidence_refs),
                }
                for recommendation in recommendations
            ],
        }

    @staticmethod
    def _markdown(title: str, period: ReportPeriod, start: date, end: date, snapshots: list[DailyIntelligenceSnapshot]) -> str:
        lines = [f"# {title}", "", f"- 周期：{period.value}", f"- 分析区间：{start.isoformat()} 至 {end.isoformat()}", f"- 日报快照：{len(snapshots)} 个", "", "## 情报摘要", ""]
        for snapshot in snapshots:
            data = json.loads(snapshot.structured_data_json)
            lines.append(f"### {snapshot.covered_date.isoformat()}")
            lines.append(f"- 库存记录：{data.get('inventoryCount', 0)}")
            lines.append(f"- 需求记录：{data.get('demandCount', 0)}")
            lines.append(f"- 在途记录：{data.get('openSupplyCount', 0)}")
            signals = data.get("confirmedSignals", [])
            recommendations = data.get("recommendations", [])
            lines.append(f"- 已确认外部信号：{len(signals)}")
            lines.append(f"- 采购建议：{len(recommendations)}")
            lines.extend(["", "#### 引用"])
            references = [
                f"- 外部信号 `{signal['id']}`：{signal['evidenceRef']}"
                for signal in signals
            ]
            for recommendation in recommendations:
                refs = "、".join(recommendation.get("evidenceRefs", [])) or "无外部证据"
                references.append(f"- 采购建议 `{recommendation['id']}`：{refs}")
            lines.extend(references or ["- 本日无已确认外部信号或采购建议。"])
            lines.append("")
        return "\n".join(lines).rstrip()
