from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.core.auth import User, get_current_user
from app.core.errors import api_error
from app.core.monitoring import (
    CollectionJob,
    CollectionMode,
    CollectionResult,
    CollectionStatus,
    Document,
    DuplicateSourceUrlError,
    ExternalSignal,
    MonitoringService,
    ReviewStatus,
    SignalType,
    Source,
    SourceStatus,
    validate_public_url,
)
from app.core.browser_collection import CloakBrowserFetcher, LangChainSignalAnalyzer
from app.core.intelligence_pipeline import IntelligencePipelineService
from app.core.recommendations import PlanningEngine
from app.core.reports import ReportService
from app.core.stores import (
    agent_service,
    catalog_store,
    internal_data_store,
    monitoring_store,
    recommendation_store,
    report_store,
)

router = APIRouter(prefix="/api/v1", tags=["monitoring"])


class Pagination(BaseModel):
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class CreateSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    targetUrl: HttpUrl
    allowedDomain: str = Field(min_length=1, max_length=253)
    scheduleMinutes: int = Field(ge=15, le=43_200)
    signalType: SignalType
    materialId: str | None = None
    materialGroupId: str | None = None
    supplierId: str | None = None
    extractionSelector: str = Field(default="body", max_length=200)
    collectionMode: CollectionMode = CollectionMode.HTTP
    navigationGoal: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_one_binding(self) -> "CreateSourceRequest":
        if sum(bool(value) for value in (self.materialId, self.materialGroupId, self.supplierId)) != 1:
            raise ValueError("Exactly one material group, material, or legacy supplier binding is required.")
        return self


class UpdateSourceRequest(CreateSourceRequest):
    status: SourceStatus = SourceStatus.ACTIVE


class SourceResponse(BaseModel):
    id: str
    name: str
    targetUrl: str
    allowedDomain: str
    scheduleMinutes: int
    signalType: SignalType
    materialId: str | None
    materialGroupId: str | None
    supplierId: str | None
    extractionSelector: str
    collectionMode: CollectionMode
    navigationGoal: str
    status: str
    lastCollectedAt: datetime | None
    lastCollectionStatus: str | None
    createdAt: datetime
    updatedAt: datetime


class SourceListResponse(BaseModel):
    data: list[SourceResponse]
    pagination: Pagination


class CollectionJobResponse(BaseModel):
    id: str
    sourceId: str
    status: str
    startedAt: datetime
    finishedAt: datetime
    statusCode: int | None
    documentId: str | None
    contentChanged: bool
    errorCode: str | None
    errorMessage: str | None


class CollectionJobListResponse(BaseModel):
    data: list[CollectionJobResponse]
    pagination: Pagination


class DocumentResponse(BaseModel):
    id: str
    sourceId: str
    collectionJobId: str
    finalUrl: str
    statusCode: int
    contentType: str
    title: str
    extractedText: str
    contentDigest: str
    previousContentDigest: str | None
    changed: bool
    collectedAt: datetime


class ExternalSignalResponse(BaseModel):
    id: str
    sourceId: str
    documentId: str
    signalType: SignalType
    materialId: str | None
    supplierId: str | None
    occurredAt: datetime
    observedAt: datetime
    previousValue: str
    currentValue: str
    confidence: float
    evidenceRef: str
    reviewStatus: str
    reviewedBy: str | None
    reviewedAt: datetime | None
    summary: str
    analysisRationale: str
    analysisModel: str
    aiAnalyzed: bool


class ExternalSignalListResponse(BaseModel):
    data: list[ExternalSignalResponse]
    pagination: Pagination


class ReviewSignalRequest(BaseModel):
    reviewStatus: ReviewStatus

    @model_validator(mode="after")
    def require_final_status(self) -> "ReviewSignalRequest":
        if self.reviewStatus == ReviewStatus.PENDING:
            raise ValueError("Review status must be CONFIRMED or DISMISSED.")
        return self


class CollectionResultResponse(BaseModel):
    job: CollectionJobResponse
    document: DocumentResponse | None
    signal: ExternalSignalResponse | None
    downstreamStatus: str
    downstreamMessage: str


def get_monitoring_service() -> MonitoringService:
    return MonitoringService(
        monitoring_store,
        browser_fetcher=CloakBrowserFetcher(agent_service, catalog_store),
        signal_analyzer=LangChainSignalAnalyzer(agent_service, catalog_store),
    )


def get_intelligence_pipeline() -> IntelligencePipelineService:
    planning_engine = PlanningEngine(
        catalog_store,
        internal_data_store,
        monitoring_store,
        recommendation_store,
        agent_service,
    )
    report_service = ReportService(
        report_store,
        catalog_store,
        internal_data_store,
        monitoring_store,
        recommendation_store,
        agent_service,
    )
    return IntelligencePipelineService(
        planning_engine,
        report_service,
        report_store,
        agent_service,
    )


def pagination(page: int, page_size: int, total: int) -> Pagination:
    return Pagination(
        page=page,
        pageSize=page_size,
        totalItems=total,
        totalPages=(total + page_size - 1) // page_size if total else 0,
    )


def page_records(records: list, page: int, page_size: int):
    start = (page - 1) * page_size
    return records[start : start + page_size]


def source_response(item: Source) -> SourceResponse:
    return SourceResponse(
        id=item.id,
        name=item.name,
        targetUrl=item.target_url,
        allowedDomain=item.allowed_domain,
        scheduleMinutes=item.schedule_minutes,
        signalType=item.signal_type,
        materialId=item.material_id,
        materialGroupId=item.material_group_id,
        supplierId=item.supplier_id,
        extractionSelector=item.extraction_selector,
        collectionMode=item.collection_mode,
        navigationGoal=item.navigation_goal,
        status=item.status.value,
        lastCollectedAt=item.last_collected_at,
        lastCollectionStatus=item.last_collection_status.value if item.last_collection_status else None,
        createdAt=item.created_at,
        updatedAt=item.updated_at,
    )


def job_response(item: CollectionJob) -> CollectionJobResponse:
    return CollectionJobResponse(
        id=item.id,
        sourceId=item.source_id,
        status=item.status.value,
        startedAt=item.started_at,
        finishedAt=item.finished_at,
        statusCode=item.status_code,
        documentId=item.document_id,
        contentChanged=item.content_changed,
        errorCode=item.error_code,
        errorMessage=item.error_message,
    )


def document_response(item: Document) -> DocumentResponse:
    return DocumentResponse(
        id=item.id,
        sourceId=item.source_id,
        collectionJobId=item.collection_job_id,
        finalUrl=item.final_url,
        statusCode=item.status_code,
        contentType=item.content_type,
        title=item.title,
        extractedText=item.extracted_text,
        contentDigest=item.content_digest,
        previousContentDigest=item.previous_content_digest,
        changed=item.changed,
        collectedAt=item.collected_at,
    )


def signal_response(item: ExternalSignal) -> ExternalSignalResponse:
    return ExternalSignalResponse(
        id=item.id,
        sourceId=item.source_id,
        documentId=item.document_id,
        signalType=item.signal_type,
        materialId=item.material_id,
        supplierId=item.supplier_id,
        occurredAt=item.occurred_at,
        observedAt=item.observed_at,
        previousValue=item.previous_value,
        currentValue=item.current_value,
        confidence=item.confidence,
        evidenceRef=item.evidence_ref,
        reviewStatus=item.review_status.value,
        reviewedBy=item.reviewed_by,
        reviewedAt=item.reviewed_at,
        summary=item.summary,
        analysisRationale=item.analysis_rationale,
        analysisModel=item.analysis_model,
        aiAnalyzed=item.ai_analyzed,
    )


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(payload: CreateSourceRequest, user: User = Depends(get_current_user)) -> SourceResponse:
    try:
        target_url, allowed_domain = validate_public_url(str(payload.targetUrl), payload.allowedDomain)
    except ValueError as exc:
        raise api_error(422, "SOURCE_URL_INVALID", str(exc)) from exc
    if payload.materialId and catalog_store.get_material(user.workspace_id, payload.materialId) is None:
        raise api_error(409, "MATERIAL_REFERENCE_INVALID", "Material is unavailable in this workspace.")
    if payload.materialGroupId and catalog_store.get_material_group(user.workspace_id, payload.materialGroupId) is None:
        raise api_error(409, "MATERIAL_GROUP_REFERENCE_INVALID", "Material group is unavailable in this workspace.")
    if payload.supplierId and not any(
        item.id == payload.supplierId
        for item in catalog_store.list_suppliers(user.workspace_id)
    ):
        raise api_error(409, "SUPPLIER_REFERENCE_INVALID", "Supplier is unavailable in this workspace.")
    now = datetime.now(timezone.utc)
    source = Source(
        id=f"src_{uuid4().hex}",
        workspace_id=user.workspace_id,
        name=payload.name.strip(),
        target_url=target_url,
        allowed_domain=allowed_domain,
        schedule_minutes=payload.scheduleMinutes,
        signal_type=payload.signalType,
        material_id=payload.materialId,
        material_group_id=payload.materialGroupId,
        supplier_id=payload.supplierId,
        extraction_selector=payload.extractionSelector.strip() or "body",
        collection_mode=payload.collectionMode,
        navigation_goal=payload.navigationGoal.strip(),
        status=SourceStatus.ACTIVE,
        last_collected_at=None,
        last_collection_status=None,
        last_content_digest=None,
        created_at=now,
        updated_at=now,
    )
    try:
        return source_response(monitoring_store.create_source(source))
    except DuplicateSourceUrlError as exc:
        raise api_error(409, "SOURCE_URL_DUPLICATE", str(exc)) from exc


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: str,
    payload: UpdateSourceRequest,
    user: User = Depends(get_current_user),
) -> SourceResponse:
    existing = monitoring_store.get_source(user.workspace_id, source_id)
    if existing is None:
        raise api_error(404, "SOURCE_NOT_FOUND", "Source was not found.")
    try:
        target_url, allowed_domain = validate_public_url(str(payload.targetUrl), payload.allowedDomain)
    except ValueError as exc:
        raise api_error(422, "SOURCE_URL_INVALID", str(exc)) from exc
    if payload.materialId and catalog_store.get_material(user.workspace_id, payload.materialId) is None:
        raise api_error(409, "MATERIAL_REFERENCE_INVALID", "Material is unavailable in this workspace.")
    if payload.materialGroupId and catalog_store.get_material_group(user.workspace_id, payload.materialGroupId) is None:
        raise api_error(409, "MATERIAL_GROUP_REFERENCE_INVALID", "Material group is unavailable in this workspace.")
    if payload.supplierId and not any(
        item.id == payload.supplierId for item in catalog_store.list_suppliers(user.workspace_id)
    ):
        raise api_error(409, "SUPPLIER_REFERENCE_INVALID", "Supplier is unavailable in this workspace.")
    updated = Source(
        **{
            **existing.__dict__,
            "name": payload.name.strip(),
            "target_url": target_url,
            "allowed_domain": allowed_domain,
            "schedule_minutes": payload.scheduleMinutes,
            "signal_type": payload.signalType,
            "material_id": payload.materialId,
            "material_group_id": payload.materialGroupId,
            "supplier_id": payload.supplierId,
            "extraction_selector": payload.extractionSelector.strip() or "body",
            "collection_mode": payload.collectionMode,
            "navigation_goal": payload.navigationGoal.strip(),
            "status": payload.status,
            "updated_at": datetime.now(timezone.utc),
        }
    )
    try:
        return source_response(monitoring_store.update_source(updated))
    except DuplicateSourceUrlError as exc:
        raise api_error(409, "SOURCE_URL_DUPLICATE", str(exc)) from exc


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_source(
    source_id: str,
    user: User = Depends(get_current_user),
) -> Response:
    existing = monitoring_store.get_source(user.workspace_id, source_id)
    if existing is None:
        raise api_error(404, "SOURCE_NOT_FOUND", "Source was not found.")
    monitoring_store.update_source(Source(**{
        **existing.__dict__,
        "status": SourceStatus.ARCHIVED,
        "updated_at": datetime.now(timezone.utc),
    }))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sources", response_model=SourceListResponse)
def list_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> SourceListResponse:
    records = monitoring_store.list_sources(user.workspace_id)
    return SourceListResponse(
        data=[source_response(item) for item in page_records(records, page, page_size)],
        pagination=pagination(page, page_size, len(records)),
    )


@router.post("/sources/{source_id}/collect", response_model=CollectionResultResponse)
def collect_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    service: MonitoringService = Depends(get_monitoring_service),
    pipeline: IntelligencePipelineService = Depends(get_intelligence_pipeline),
) -> CollectionResultResponse:
    try:
        result: CollectionResult = service.collect(user.workspace_id, source_id)
    except LookupError as exc:
        raise api_error(404, "SOURCE_NOT_FOUND", "Source was not found.") from exc
    downstream_status = "SKIPPED"
    downstream_message = "采集未成功，下游分析未启动。"
    if result.job.status == CollectionStatus.SUCCEEDED and result.document is not None:
        background_tasks.add_task(
            pipeline.run,
            user.workspace_id,
            user.id,
            result.document.collected_at,
        )
        downstream_status = "QUEUED"
        downstream_message = "采购建议测算和当日情报报告已进入后台生成队列。"
    return CollectionResultResponse(
        job=job_response(result.job),
        document=document_response(result.document) if result.document else None,
        signal=signal_response(result.signal) if result.signal else None,
        downstreamStatus=downstream_status,
        downstreamMessage=downstream_message,
    )


@router.get("/collection-jobs", response_model=CollectionJobListResponse)
def list_collection_jobs(
    source_id: str | None = Query(default=None, alias="sourceId"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> CollectionJobListResponse:
    records = monitoring_store.list_jobs(user.workspace_id, source_id)
    return CollectionJobListResponse(
        data=[job_response(item) for item in page_records(records, page, page_size)],
        pagination=pagination(page, page_size, len(records)),
    )


@router.get("/external-signals", response_model=ExternalSignalListResponse)
def list_external_signals(
    source_id: str | None = Query(default=None, alias="sourceId"),
    review_status: ReviewStatus | None = Query(default=None, alias="reviewStatus"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    user: User = Depends(get_current_user),
) -> ExternalSignalListResponse:
    records = monitoring_store.list_signals(user.workspace_id, source_id)
    if review_status is not None:
        records = [item for item in records if item.review_status == review_status]
    return ExternalSignalListResponse(
        data=[signal_response(item) for item in page_records(records, page, page_size)],
        pagination=pagination(page, page_size, len(records)),
    )


@router.patch("/external-signals/{signal_id}", response_model=ExternalSignalResponse)
def review_external_signal(
    signal_id: str,
    payload: ReviewSignalRequest,
    user: User = Depends(get_current_user),
    service: MonitoringService = Depends(get_monitoring_service),
) -> ExternalSignalResponse:
    try:
        signal = service.review_signal(
            user.workspace_id,
            signal_id,
            payload.reviewStatus,
            user.id,
        )
    except LookupError as exc:
        raise api_error(404, "SIGNAL_NOT_FOUND", "Signal was not found.") from exc
    return signal_response(signal)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, user: User = Depends(get_current_user)) -> DocumentResponse:
    document = monitoring_store.get_document(user.workspace_id, document_id)
    if document is None:
        raise api_error(404, "DOCUMENT_NOT_FOUND", "Evidence document was not found.")
    return document_response(document)
