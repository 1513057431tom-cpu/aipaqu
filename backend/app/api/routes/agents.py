from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from fastapi import APIRouter, Depends, status
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from app.core.agents import (
    AgentDefinition,
    AgentConfiguration,
    AgentRun,
    ALLOWED_TOOL_KEYS,
    ExecutionMode,
    ModelConfiguration,
    ModelNotConfiguredError,
)
from app.core.auth import Role, User, get_current_user, require_role
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


class ModelConfigurationResponse(BaseModel):
    provider: str
    model: str
    baseUrl: str
    apiKeyConfigured: bool
    apiKeyMasked: str | None
    updatedAt: datetime | None


class UpdateModelConfigurationRequest(BaseModel):
    provider: str = "DEEPSEEK"
    model: str = Field(min_length=1, max_length=120)
    baseUrl: AnyHttpUrl
    apiKey: str | None = Field(default=None, min_length=8, max_length=500)
    clearApiKey: bool = False

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if value.upper() != "DEEPSEEK":
            raise ValueError("Only DEEPSEEK is currently supported.")
        return "DEEPSEEK"

    @field_validator("model")
    @classmethod
    def strip_model(cls, value: str) -> str:
        return value.strip()


class ModelConnectionTestResponse(BaseModel):
    success: bool
    provider: str
    model: str
    latencyMs: int
    message: str


class AgentConfigurationResponse(BaseModel):
    agentKey: str
    systemPrompt: str
    defaultExecutionMode: str
    toolKeys: list[str]
    availableToolKeys: list[str]
    updatedAt: datetime | None


class UpdateAgentConfigurationRequest(BaseModel):
    systemPrompt: str | None = Field(default=None, min_length=20, max_length=8000)
    defaultExecutionMode: ExecutionMode | None = None
    toolKeys: list[str] | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("systemPrompt")
    @classmethod
    def strip_prompt(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("toolKeys")
    @classmethod
    def validate_tools(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) != len(set(value)) or any(key not in ALLOWED_TOOL_KEYS for key in value):
            raise ValueError("Tool list contains a duplicate or unsupported tool.")
        return value


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


def definition_response(
    definition: AgentDefinition,
    model_configuration: ModelConfiguration,
    agent_configuration: AgentConfiguration,
) -> AgentDefinitionResponse:
    return AgentDefinitionResponse(
        key=definition.key,
        name=definition.name,
        description=definition.description,
        provider=definition.provider,
        model=model_configuration.model,
        modelConfigured=bool(model_configuration.api_key),
        workflowVersion=definition.workflow_version,
        toolKeys=list(agent_configuration.tool_keys),
    )


def mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    return f"********{api_key[-4:]}"


def model_configuration_response(
    configuration: ModelConfiguration,
) -> ModelConfigurationResponse:
    return ModelConfigurationResponse(
        provider=configuration.provider,
        model=configuration.model,
        baseUrl=configuration.base_url,
        apiKeyConfigured=bool(configuration.api_key),
        apiKeyMasked=mask_api_key(configuration.api_key),
        updatedAt=configuration.updated_at,
    )


def agent_configuration_response(
    configuration: AgentConfiguration,
) -> AgentConfigurationResponse:
    return AgentConfigurationResponse(
        agentKey=configuration.agent_key,
        systemPrompt=configuration.system_prompt,
        defaultExecutionMode=configuration.default_execution_mode.value,
        toolKeys=list(configuration.tool_keys),
        availableToolKeys=list(ALLOWED_TOOL_KEYS),
        updatedAt=configuration.updated_at,
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
def list_agents(user: User = Depends(get_current_user)) -> AgentDefinitionListResponse:
    model_configuration = agent_service.get_model_configuration(user.workspace_id)
    agent_configuration = agent_service.get_agent_configuration(
        user.workspace_id, "material-monitor"
    )
    return AgentDefinitionListResponse(
        data=[
            definition_response(definition, model_configuration, agent_configuration)
            for definition in agent_service.list_definitions()
        ]
    )


@router.get("/model-configuration", response_model=ModelConfigurationResponse)
def get_model_configuration(
    user: User = Depends(get_current_user),
) -> ModelConfigurationResponse:
    return model_configuration_response(agent_service.get_model_configuration(user.workspace_id))


@router.put("/model-configuration", response_model=ModelConfigurationResponse)
def update_model_configuration(
    payload: UpdateModelConfigurationRequest,
    user: User = Depends(get_current_user),
) -> ModelConfigurationResponse:
    require_role(user, {Role.ADMIN})
    existing = agent_service.get_model_configuration(user.workspace_id)
    api_key = None if payload.clearApiKey else payload.apiKey or existing.api_key
    configuration = ModelConfiguration(
        workspace_id=user.workspace_id,
        provider=payload.provider,
        model=payload.model,
        base_url=str(payload.baseUrl).rstrip("/"),
        api_key=api_key,
        updated_at=datetime.now(timezone.utc),
    )
    return model_configuration_response(agent_service.save_model_configuration(configuration))


@router.post(
    "/model-configuration/test",
    response_model=ModelConnectionTestResponse,
)
def test_model_connection(
    user: User = Depends(get_current_user),
) -> ModelConnectionTestResponse:
    require_role(user, {Role.ADMIN})
    configuration = agent_service.get_model_configuration(user.workspace_id)
    if not configuration.api_key:
        raise api_error(
            status.HTTP_409_CONFLICT,
            "MODEL_NOT_CONFIGURED",
            "Save a DeepSeek API key before testing the connection.",
        )
    from langchain_deepseek import ChatDeepSeek

    started = perf_counter()
    try:
        response = ChatDeepSeek(
            api_key=configuration.api_key,
            base_url=configuration.base_url,
            model=configuration.model,
            temperature=0,
            max_tokens=8,
            timeout=30,
        ).invoke("Reply with OK only.")
    except Exception as exc:
        raise api_error(
            status.HTTP_502_BAD_GATEWAY,
            "MODEL_CONNECTION_FAILED",
            "DeepSeek connection test failed.",
            {"reason": type(exc).__name__},
        ) from exc
    success = bool(getattr(response, "content", ""))
    return ModelConnectionTestResponse(
        success=success,
        provider=configuration.provider,
        model=configuration.model,
        latencyMs=int((perf_counter() - started) * 1000),
        message="DeepSeek connection succeeded." if success else "DeepSeek returned an empty response.",
    )


def ensure_agent_exists(agent_key: str) -> None:
    if agent_key != "material-monitor":
        raise api_error(status.HTTP_404_NOT_FOUND, "AGENT_NOT_FOUND", "Agent was not found.")


@router.get(
    "/agents/{agent_key}/configuration",
    response_model=AgentConfigurationResponse,
)
def get_agent_configuration(
    agent_key: str,
    user: User = Depends(get_current_user),
) -> AgentConfigurationResponse:
    ensure_agent_exists(agent_key)
    return agent_configuration_response(
        agent_service.get_agent_configuration(user.workspace_id, agent_key)
    )


@router.patch(
    "/agents/{agent_key}/configuration",
    response_model=AgentConfigurationResponse,
)
def update_agent_configuration(
    agent_key: str,
    payload: UpdateAgentConfigurationRequest,
    user: User = Depends(get_current_user),
) -> AgentConfigurationResponse:
    require_role(user, {Role.ADMIN})
    ensure_agent_exists(agent_key)
    existing = agent_service.get_agent_configuration(user.workspace_id, agent_key)
    configuration = AgentConfiguration(
        workspace_id=user.workspace_id,
        agent_key=agent_key,
        system_prompt=payload.systemPrompt or existing.system_prompt,
        default_execution_mode=payload.defaultExecutionMode or existing.default_execution_mode,
        tool_keys=tuple(payload.toolKeys) if payload.toolKeys is not None else existing.tool_keys,
        updated_at=datetime.now(timezone.utc),
    )
    return agent_configuration_response(agent_service.save_agent_configuration(configuration))


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
    ensure_agent_exists(agent_key)
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
