from __future__ import annotations

import json
import logging
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


ALLOWED_TOOL_KEYS = (
    "material_catalog",
    "monitoring_sources",
    "evidence_store",
    "browser_navigation",
    "internal_operations",
    "procurement_rules",
    "report_templates",
)


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
class ReportTemplate:
    workspace_id: str
    period: str
    name: str
    content: str
    updated_at: datetime | None


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


class ProcurementNarrative(BaseModel):
    explanation: str = Field(min_length=1, max_length=3000)
    risk_factors: list[str] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list, max_length=10)


class ReportDraft(BaseModel):
    markdown: str = Field(min_length=1, max_length=50_000)


logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    material_ids: list[str]
    execution_mode: str
    steps: list[dict[str, str]]
    model_invoked: bool
    summary: str


AGENT_DEFINITIONS = (
    AgentDefinition(
        key="material-monitor",
        name="监测编排智能体",
        description="按物料范围协调网页采集、情报分析、采购解释和报告任务。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="2.0.0",
        tool_keys=("material_catalog", "monitoring_sources", "evidence_store"),
    ),
    AgentDefinition(
        key="web-navigator",
        name="页面导航智能体",
        description="理解网页结构，规划搜索、标签切换、分页和详情页导航。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="1.0.0",
        tool_keys=("material_catalog", "monitoring_sources", "browser_navigation"),
    ),
    AgentDefinition(
        key="intelligence-analyst",
        name="情报分析智能体",
        description="基于新旧证据识别与物料相关的价格、规格、供应和交期变化。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="1.0.0",
        tool_keys=("material_catalog", "evidence_store"),
    ),
    AgentDefinition(
        key="procurement-advisor",
        name="采购解释智能体",
        description="结合确定性库存计算和外部情报，解释风险与建议依据。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="1.0.0",
        tool_keys=("material_catalog", "internal_operations", "procurement_rules", "evidence_store"),
    ),
    AgentDefinition(
        key="report-writer",
        name="报告撰写智能体",
        description="按日报、周报和月报模板组织已审核情报与采购建议。",
        provider="DEEPSEEK",
        model="deepseek-chat",
        workflow_version="1.0.0",
        tool_keys=("material_catalog", "evidence_store", "report_templates"),
    ),
)

DEFAULT_AGENT_PROMPTS = {
    "material-monitor": "你是监测编排智能体。按物料范围调度采集、分析、采购解释和报告任务，并记录每个节点的输入、输出与证据。",
    "web-navigator": "你是页面导航智能体。根据物料名称、编码和监测目标理解网页结构，只规划站内搜索、标签、分页和详情页等必要操作，不访问允许域名之外的页面。",
    "intelligence-analyst": "你是物料情报分析智能体。只能依据可追溯的新旧证据识别价格、规格、可用性和交期变化；输出物料关联、变化摘要、前后值、可信度和依据，证据不足时不得生成情报。",
    "procurement-advisor": "你是采购解释智能体。采购数量和日期以确定性库存规则为准；你负责结合外部情报解释风险、假设和证据，不得自行覆盖规则计算结果。",
    "report-writer": "你是供应情报报告撰写智能体。严格按所选模板组织已审核情报和采购建议，保留证据引用，不得将未确认内容写成事实。",
}
DEFAULT_SYSTEM_PROMPT = DEFAULT_AGENT_PROMPTS["material-monitor"]

DEFAULT_REPORT_TEMPLATES = {
    "DAILY": "# {{title}}\n\n## 今日重点\n{{highlights}}\n\n## 物料情报\n{{material_intelligence}}\n\n## 采购建议\n{{recommendations}}\n\n## 证据引用\n{{evidence}}",
    "WEEKLY": "# {{title}}\n\n## 本周概览\n{{highlights}}\n\n## 物料趋势\n{{material_intelligence}}\n\n## 采购建议变化\n{{recommendations}}\n\n## 日报引用\n{{evidence}}",
    "MONTHLY": "# {{title}}\n\n## 月度摘要\n{{highlights}}\n\n## 物料趋势与异常\n{{material_intelligence}}\n\n## 采购策略回顾\n{{recommendations}}\n\n## 日报引用\n{{evidence}}",
}


class InMemoryAgentConfigurationStore:
    def __init__(self) -> None:
        self._models: dict[str, ModelConfiguration] = {}
        self._agents: dict[tuple[str, str], AgentConfiguration] = {}
        self._report_templates: dict[tuple[str, str], ReportTemplate] = {}
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

    def get_report_template(self, workspace_id: str, period: str) -> ReportTemplate | None:
        return self._report_templates.get((workspace_id, period))

    def save_report_template(self, template: ReportTemplate) -> ReportTemplate:
        with self._lock:
            self._report_templates[(template.workspace_id, template.period)] = template
        return template


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
        definition = next((item for item in AGENT_DEFINITIONS if item.key == agent_key), None)
        if definition is None:
            raise LookupError("Agent was not found.")
        return self.configuration_store.get_agent_configuration(
            workspace_id, agent_key
        ) or AgentConfiguration(
            workspace_id=workspace_id,
            agent_key=agent_key,
            system_prompt=DEFAULT_AGENT_PROMPTS[agent_key],
            default_execution_mode=ExecutionMode.TEST,
            tool_keys=definition.tool_keys,
            updated_at=None,
        )

    def save_agent_configuration(self, configuration: AgentConfiguration) -> AgentConfiguration:
        return self.configuration_store.save_agent_configuration(configuration)

    def get_report_template(self, workspace_id: str, period: str) -> ReportTemplate:
        return self.configuration_store.get_report_template(workspace_id, period) or ReportTemplate(
            workspace_id=workspace_id,
            period=period,
            name={"DAILY": "默认日报模板", "WEEKLY": "默认周报模板", "MONTHLY": "默认月报模板"}[period],
            content=DEFAULT_REPORT_TEMPLATES[period],
            updated_at=None,
        )

    def list_report_templates(self, workspace_id: str) -> tuple[ReportTemplate, ...]:
        return tuple(self.get_report_template(workspace_id, period) for period in ("DAILY", "WEEKLY", "MONTHLY"))

    def save_report_template(self, template: ReportTemplate) -> ReportTemplate:
        return self.configuration_store.save_report_template(template)

    def invoke_structured(self, workspace_id: str, agent_key: str, schema, context: dict):
        model_configuration = self.get_model_configuration(workspace_id)
        if not model_configuration.api_key:
            return None
        configuration = self.get_agent_configuration(workspace_id, agent_key)
        try:
            from langchain_deepseek import ChatDeepSeek

            model = ChatDeepSeek(
                api_key=model_configuration.api_key,
                base_url=model_configuration.base_url,
                model=model_configuration.model,
                temperature=0,
            ).with_structured_output(schema)
            return model.invoke(
                [
                    ("system", configuration.system_prompt),
                    ("human", json.dumps(context, ensure_ascii=False, default=str)),
                ]
            )
        except Exception as exc:
            logger.warning(
                "Agent %s invocation failed: %s",
                agent_key,
                type(exc).__name__,
            )
            return None

    def explain_procurement(self, workspace_id: str, context: dict) -> str | None:
        result = self.invoke_structured(
            workspace_id,
            "procurement-advisor",
            ProcurementNarrative,
            context,
        )
        return result.explanation if result else None

    def write_report(self, workspace_id: str, context: dict) -> str | None:
        result = self.invoke_structured(
            workspace_id,
            "report-writer",
            ReportDraft,
            context,
        )
        return result.markdown if result else None

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
