from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.core.agents import (
    AgentDefinition,
    AgentRun,
    ExecutionMode,
    ModelNotConfiguredError,
)
from app.core.auth import User, get_current_user
from app.core.config import get_settings
from app.core.errors import api_error
from app.core.stores import agent_service, catalog_store

router = APIRouter(prefix="/api/v1", tags=["agents"])


class AgentDefinitionResponse(BaseModel):
    key: str
    name: str
    description: str
    provider: str
    model: str
    modelConfigured: bool
    workflowVersion: str
    toolKeys: list[str]


class AgentDefinitionListResponse(BaseModel):
    data: list[AgentDefinitionResponse]


class RunAgentRequest(BaseModel):
    executionMode: ExecutionMode = ExecutionMode.TEST
    materialIds: list[str] = Field(default_factory=list, max_length=500)


class AgentStepResponse(BaseModel):
    key: str
    name: str
    status: str
    detail: str


class AgentRunResponse(BaseModel):
    id: str
    agentKey: str
    executionMode: str
    status: str
    materialIds: list[str]
    steps: list[AgentStepResponse]
    modelInvoked: bool
    summary: str
    errorCode: str | None
    errorMessage: str | None
    startedAt: datetime
    finishedAt: datetime | None


class AgentRunListResponse(BaseModel):
    data: list[AgentRunResponse]


def definition_response(definition: AgentDefinition) -> AgentDefinitionResponse:
    settings = get_settings()
    model_configured = bool(
        settings.deepseek_api_key
        and settings.deepseek_api_key.get_secret_value().strip()
    )
    return AgentDefinitionResponse(
        key=definition.key,
        name=definition.name,
        description=definition.description,
        provider=definition.provider,
        model=settings.deepseek_model,
        modelConfigured=model_configured,
        workflowVersion=definition.workflow_version,
        toolKeys=list(definition.tool_keys),
    )


def run_response(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=run.id,
        agentKey=run.agent_key,
        executionMode=run.execution_mode.value,
        status=run.status.value,
        materialIds=list(run.material_ids),
        steps=[AgentStepResponse(**step.__dict__) for step in run.steps],
        modelInvoked=run.model_invoked,
        summary=run.summary,
        errorCode=run.error_code,
        errorMessage=run.error_message,
        startedAt=run.started_at,
        finishedAt=run.finished_at,
    )


@router.get("/agents", response_model=AgentDefinitionListResponse)
def list_agents(_user: User = Depends(get_current_user)) -> AgentDefinitionListResponse:
    return AgentDefinitionListResponse(
        data=[definition_response(definition) for definition in agent_service.list_definitions()]
    )


@router.post(
    "/agents/{agent_key}/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_agent(
    agent_key: str,
    payload: RunAgentRequest,
    user: User = Depends(get_current_user),
) -> AgentRunResponse:
    if agent_key != "material-monitor":
        raise api_error(status.HTTP_404_NOT_FOUND, "AGENT_NOT_FOUND", "Agent was not found.")
    for material_id in payload.materialIds:
        if catalog_store.get_material(user.workspace_id, material_id) is None:
            raise api_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "INVALID_MATERIAL_SCOPE",
                "Material scope contains an invalid identifier.",
            )
    try:
        run = agent_service.run_material_monitor(
            workspace_id=user.workspace_id,
            execution_mode=payload.executionMode,
            material_ids=payload.materialIds,
        )
    except ModelNotConfiguredError as exc:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MODEL_NOT_CONFIGURED",
            "DeepSeek is not configured. Add DEEPSEEK_API_KEY before a LIVE run.",
        ) from exc
    return run_response(run)


@router.get("/agent-runs", response_model=AgentRunListResponse)
def list_agent_runs(user: User = Depends(get_current_user)) -> AgentRunListResponse:
    return AgentRunListResponse(
        data=[run_response(run) for run in agent_service.run_store.list_for_workspace(user.workspace_id)]
    )
