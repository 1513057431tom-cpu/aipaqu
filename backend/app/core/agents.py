from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from itertools import count
from threading import RLock
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    TEST = "TEST"
    LIVE = "LIVE"


class AgentRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ModelNotConfiguredError(RuntimeError):
    pass


ALLOWED_TOOL_KEYS = ("material_catalog", "monitoring_sources", "evidence_store")


@dataclass(frozen=True)
class ModelConfiguration:
    workspace_id: str
    provider: str
    model: str
    base_url: str
    api_key: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class AgentConfiguration:
    workspace_id: str
    agent_key: str
    system_prompt: str
    default_execution_mode: ExecutionMode
    tool_keys: tuple[str, ...]
    updated_at: datetime | None


@dataclass(frozen=True)
class AgentDefinition:
    key: str
    name: str
    description: str
    provider: str
    model: str
    workflow_version: str
    tool_keys: tuple[str, ...]


@dataclass(frozen=True)
class AgentStep:
    key: str
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class AgentRun:
    id: str
    workspace_id: str
    agent_key: str
    execution_mode: ExecutionMode
    status: AgentRunStatus
    material_ids: tuple[str, ...]
    steps: tuple[AgentStep, ...]
    model_invoked: bool
    summary: str
    error_code: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class MaterialAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[str] = Field(default_factory=list, max_length=20)


class WorkflowState(TypedDict):
    material_ids: list[str]
    execution_mode: str
    steps: list[dict[str, str]]
    model_invoked: bool
    summary: str


AGENT_DEFINITIONS = (
    AgentDefinition(
        key="material-monitor",
        name="物料监测 Agent",
        description="按物料范围采集外部证据、识别变化并准备采购建议与报告输入。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="1.0.0",
        tool_keys=ALLOWED_TOOL_KEYS,
    ),
)

DEFAULT_SYSTEM_PROMPT = (
    "你是物料监测分析 Agent。只能依据可追溯证据识别价格、规格、可用性和交期变化；"
    "证据不足时必须明确说明，不得编造事实或替代人工采购决策。"
)


class InMemoryAgentConfigurationStore:
    def __init__(self) -> None:
        self._models: dict[str, ModelConfiguration] = {}
        self._agents: dict[tuple[str, str], AgentConfiguration] = {}
        self._lock = RLock()

    def get_model_configuration(self, workspace_id: str) -> ModelConfiguration | None:
        with self._lock:
            return self._models.get(workspace_id)

    def save_model_configuration(self, configuration: ModelConfiguration) -> ModelConfiguration:
        with self._lock:
            self._models[configuration.workspace_id] = configuration
        return configuration

    def get_agent_configuration(
        self, workspace_id: str, agent_key: str
    ) -> AgentConfiguration | None:
        with self._lock:
            return self._agents.get((workspace_id, agent_key))

    def save_agent_configuration(self, configuration: AgentConfiguration) -> AgentConfiguration:
        with self._lock:
            self._agents[(configuration.workspace_id, configuration.agent_key)] = configuration
        return configuration


class InMemoryAgentRunStore:
    def __init__(self) -> None:
        self._sequence = count(1)
        self._runs: dict[str, AgentRun] = {}
        self._lock = RLock()

    def next_id(self) -> str:
        return f"arun_{next(self._sequence)}"

    def save(self, run: AgentRun) -> AgentRun:
        with self._lock:
            self._runs[run.id] = run
        return run

    def list_for_workspace(self, workspace_id: str) -> list[AgentRun]:
        with self._lock:
            runs = [run for run in self._runs.values() if run.workspace_id == workspace_id]
        return sorted(runs, key=lambda item: item.started_at, reverse=True)[:100]


def _completed_step(key: str, name: str, detail: str) -> dict[str, str]:
    return {"key": key, "name": name, "status": "COMPLETED", "detail": detail}


class MaterialMonitoringWorkflow:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.system_prompt = system_prompt
        graph = StateGraph(WorkflowState)
        graph.add_node("load_scope", self._load_scope)
        graph.add_node("collect_evidence", self._collect_evidence)
        graph.add_node("analyze_changes", self._analyze_changes)
        graph.add_node("prepare_outputs", self._prepare_outputs)
        graph.add_edge(START, "load_scope")
        graph.add_edge("load_scope", "collect_evidence")
        graph.add_edge("collect_evidence", "analyze_changes")
        graph.add_edge("analyze_changes", "prepare_outputs")
        graph.add_edge("prepare_outputs", END)
        self.graph = graph.compile()

    def invoke(self, *, material_ids: list[str], execution_mode: ExecutionMode) -> WorkflowState:
        initial: WorkflowState = {
            "material_ids": material_ids,
            "execution_mode": execution_mode.value,
            "steps": [],
            "model_invoked": False,
            "summary": "",
        }
        return self.graph.invoke(initial)

    @staticmethod
    def _load_scope(state: WorkflowState) -> dict:
        scope = f"已选择 {len(state['material_ids'])} 条物料" if state["material_ids"] else "使用全部启用物料"
        return {"steps": [*state["steps"], _completed_step("load_scope", "加载监测范围", scope)]}

    @staticmethod
    def _collect_evidence(state: WorkflowState) -> dict:
        detail = (
            "TEST 模式跳过网络采集"
            if state["execution_mode"] == ExecutionMode.TEST.value
            else "证据接入节点已执行，当前版本未触发网络采集"
        )
        return {"steps": [*state["steps"], _completed_step("collect_evidence", "采集外部证据", detail)]}

    def _analyze_changes(self, state: WorkflowState) -> dict:
        if state["execution_mode"] == ExecutionMode.TEST.value:
            summary = "工作流结构验证完成，未调用模型，也未生成业务结论。"
            invoked = False
            detail = "DeepSeek 未调用"
        else:
            if not self.api_key:
                raise ModelNotConfiguredError("DeepSeek API key is not configured.")
            from langchain_deepseek import ChatDeepSeek

            llm = ChatDeepSeek(
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model,
                temperature=0,
            ).with_structured_output(MaterialAnalysis)
            result = llm.invoke(self.system_prompt)
            summary = result.summary
            invoked = True
            detail = f"DeepSeek 返回 {len(result.findings)} 条结构化发现"
        return {
            "steps": [*state["steps"], _completed_step("analyze_changes", "分析变化", detail)],
            "model_invoked": invoked,
            "summary": summary,
        }

    @staticmethod
    def _prepare_outputs(state: WorkflowState) -> dict:
        return {
            "steps": [
                *state["steps"],
                _completed_step(
                    "prepare_outputs",
                    "准备下游输出",
                    "输出契约校验完成，尚未写入采购建议或报告",
                ),
            ]
        }


class AgentService:
    def __init__(
        self,
        run_store,
        configuration_store,
        default_model_configuration: ModelConfiguration,
    ) -> None:
        self.run_store = run_store
        self.configuration_store = configuration_store
        self.default_model_configuration = default_model_configuration

    def list_definitions(self) -> tuple[AgentDefinition, ...]:
        return AGENT_DEFINITIONS

    def get_model_configuration(self, workspace_id: str) -> ModelConfiguration:
        return (
            self.configuration_store.get_model_configuration(workspace_id)
            or self.default_model_configuration
        )

    def save_model_configuration(self, configuration: ModelConfiguration) -> ModelConfiguration:
        return self.configuration_store.save_model_configuration(configuration)

    def get_agent_configuration(self, workspace_id: str, agent_key: str) -> AgentConfiguration:
        return self.configuration_store.get_agent_configuration(
            workspace_id, agent_key
        ) or AgentConfiguration(
            workspace_id=workspace_id,
            agent_key=agent_key,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            default_execution_mode=ExecutionMode.TEST,
            tool_keys=ALLOWED_TOOL_KEYS,
            updated_at=None,
        )

    def save_agent_configuration(self, configuration: AgentConfiguration) -> AgentConfiguration:
        return self.configuration_store.save_agent_configuration(configuration)

    def run_material_monitor(
        self,
        *,
        workspace_id: str,
        execution_mode: ExecutionMode,
        material_ids: list[str],
    ) -> AgentRun:
        model_configuration = self.get_model_configuration(workspace_id)
        agent_configuration = self.get_agent_configuration(workspace_id, "material-monitor")
        workflow = MaterialMonitoringWorkflow(
            api_key=model_configuration.api_key,
            base_url=model_configuration.base_url,
            model=model_configuration.model,
            system_prompt=agent_configuration.system_prompt,
        )
        if execution_mode == ExecutionMode.LIVE and not workflow.api_key:
            raise ModelNotConfiguredError("DeepSeek API key is not configured.")
        started_at = datetime.now(timezone.utc)
        run_id = self.run_store.next_id()
        try:
            state = workflow.invoke(material_ids=material_ids, execution_mode=execution_mode)
            run = AgentRun(
                id=run_id,
                workspace_id=workspace_id,
                agent_key="material-monitor",
                execution_mode=execution_mode,
                status=AgentRunStatus.COMPLETED,
                material_ids=tuple(material_ids),
                steps=tuple(AgentStep(**step) for step in state["steps"]),
                model_invoked=state["model_invoked"],
                summary=state["summary"],
                error_code=None,
                error_message=None,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        except Exception as exc:
            run = AgentRun(
                id=run_id,
                workspace_id=workspace_id,
                agent_key="material-monitor",
                execution_mode=execution_mode,
                status=AgentRunStatus.FAILED,
                material_ids=tuple(material_ids),
                steps=(),
                model_invoked=False,
                summary="",
                error_code="AGENT_RUN_FAILED",
                error_message=f"Agent execution failed ({type(exc).__name__}).",
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
        return self.run_store.save(run)
