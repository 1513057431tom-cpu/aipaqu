from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from itertools import count


class DateRangeKind(str, Enum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    CUSTOM = "CUSTOM"


class BriefStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class DateRange:
    kind: DateRangeKind
    timezone: str
    reference_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None


@dataclass(frozen=True)
class ResearchBrief:
    id: str
    workspace_id: str
    title: str
    objective: str
    required_questions: list[str]
    date_range: DateRange
    status: BriefStatus
    created_by: str
    created_at: datetime
    updated_at: datetime


class InMemoryBriefStore:
    def __init__(self) -> None:
        self._sequence = count(1)
        self._briefs: dict[str, ResearchBrief] = {}

    def create(
        self,
        *,
        workspace_id: str,
        title: str,
        objective: str,
        required_questions: list[str],
        date_range: DateRange,
        created_by: str,
    ) -> ResearchBrief:
        now = datetime.now(timezone.utc)
        brief_id = f"brief_{next(self._sequence)}"
        brief = ResearchBrief(
            id=brief_id,
            workspace_id=workspace_id,
            title=title,
            objective=objective,
            required_questions=required_questions,
            date_range=date_range,
            status=BriefStatus.DRAFT,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._briefs[brief_id] = brief
        return brief

    def list_for_workspace(self, workspace_id: str) -> list[ResearchBrief]:
        return [
            brief
            for brief in self._briefs.values()
            if brief.workspace_id == workspace_id and brief.status != BriefStatus.ARCHIVED
        ]


brief_store = InMemoryBriefStore()

