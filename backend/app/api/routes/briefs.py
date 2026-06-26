from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from app.core.auth import User, get_current_user
from app.core.briefs import DateRange, DateRangeKind, ResearchBrief, brief_store

router = APIRouter(prefix="/api/v1/briefs", tags=["briefs"])


class DateRangeInput(BaseModel):
    kind: DateRangeKind
    referenceDate: date | None = None
    startDate: date | None = None
    endDate: date | None = None
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_dates(self) -> "DateRangeInput":
        if self.kind == DateRangeKind.CUSTOM:
            if not self.startDate or not self.endDate:
                raise ValueError("CUSTOM date range requires startDate and endDate.")
            if self.startDate > self.endDate:
                raise ValueError("startDate must be earlier than or equal to endDate.")
        elif not self.referenceDate:
            raise ValueError(f"{self.kind.value} date range requires referenceDate.")
        return self

    def to_domain(self) -> DateRange:
        return DateRange(
            kind=self.kind,
            timezone=self.timezone,
            reference_date=self.referenceDate,
            start_date=self.startDate,
            end_date=self.endDate,
        )


class CreateBriefRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    objective: str = Field(min_length=1, max_length=2000)
    requiredQuestions: list[str] = Field(min_length=1, max_length=20)
    dateRange: DateRangeInput


class DateRangeResponse(BaseModel):
    kind: str
    referenceDate: date | None
    startDate: date | None
    endDate: date | None
    timezone: str


class BriefResponse(BaseModel):
    id: str
    workspaceId: str
    title: str
    objective: str
    requiredQuestions: list[str]
    dateRange: DateRangeResponse
    status: str
    createdBy: str
    createdAt: datetime
    updatedAt: datetime


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class BriefListResponse(BaseModel):
    data: list[BriefResponse]
    pagination: Pagination


def to_response(brief: ResearchBrief) -> BriefResponse:
    return BriefResponse(
        id=brief.id,
        workspaceId=brief.workspace_id,
        title=brief.title,
        objective=brief.objective,
        requiredQuestions=brief.required_questions,
        dateRange=DateRangeResponse(
            kind=brief.date_range.kind.value,
            referenceDate=brief.date_range.reference_date,
            startDate=brief.date_range.start_date,
            endDate=brief.date_range.end_date,
            timezone=brief.date_range.timezone,
        ),
        status=brief.status.value,
        createdBy=brief.created_by,
        createdAt=brief.created_at,
        updatedAt=brief.updated_at,
    )


@router.get("", response_model=BriefListResponse)
def list_briefs(user: User = Depends(get_current_user)) -> BriefListResponse:
    briefs = brief_store.list_for_workspace(user.workspace_id)
    return BriefListResponse(
        data=[to_response(brief) for brief in briefs],
        pagination=Pagination(
            page=1,
            pageSize=20,
            totalItems=len(briefs),
            totalPages=1 if briefs else 0,
        ),
    )


@router.post("", response_model=BriefResponse, status_code=status.HTTP_201_CREATED)
def create_brief(
    payload: CreateBriefRequest,
    user: User = Depends(get_current_user),
) -> BriefResponse:
    required_questions = [
        question.strip()
        for question in payload.requiredQuestions
        if question.strip()
    ]
    if not required_questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one required question is required.",
        )
    brief = brief_store.create(
        workspace_id=user.workspace_id,
        title=payload.title.strip(),
        objective=payload.objective.strip(),
        required_questions=required_questions,
        date_range=payload.dateRange.to_domain(),
        created_by=user.id,
    )
    return to_response(brief)
