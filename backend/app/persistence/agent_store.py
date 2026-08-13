from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.agents import AgentRun, AgentRunStatus, AgentStep, ExecutionMode
from app.persistence.models import AgentRunModel
from app.persistence.stores import utc_aware, utc_naive


def agent_run_from_model(model: AgentRunModel) -> AgentRun:
    return AgentRun(
        id=model.id,
        workspace_id=model.workspace_id,
        agent_key=model.agent_key,
        execution_mode=ExecutionMode(model.execution_mode),
        status=AgentRunStatus(model.status),
        material_ids=tuple(json.loads(model.material_ids_json)),
        steps=tuple(AgentStep(**step) for step in json.loads(model.steps_json)),
        model_invoked=bool(model.model_invoked),
        summary=model.summary,
        error_code=model.error_code,
        error_message=model.error_message,
        started_at=utc_aware(model.started_at),
        finished_at=utc_aware(model.finished_at) if model.finished_at else None,
    )


class SqlAlchemyAgentRunStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @staticmethod
    def next_id() -> str:
        return f"arun_{uuid4().hex}"

    def save(self, run: AgentRun) -> AgentRun:
        model = AgentRunModel(
            id=run.id,
            workspace_id=run.workspace_id,
            agent_key=run.agent_key,
            execution_mode=run.execution_mode.value,
            status=run.status.value,
            material_ids_json=json.dumps(run.material_ids),
            steps_json=json.dumps([step.__dict__ for step in run.steps], ensure_ascii=False),
            model_invoked=int(run.model_invoked),
            summary=run.summary,
            error_code=run.error_code,
            error_message=run.error_message,
            started_at=utc_naive(run.started_at),
            finished_at=utc_naive(run.finished_at) if run.finished_at else None,
        )
        with Session(self.engine) as session:
            session.merge(model)
            session.commit()
        return run

    def list_for_workspace(self, workspace_id: str) -> list[AgentRun]:
        with Session(self.engine) as session:
            models = session.scalars(
                select(AgentRunModel)
                .where(AgentRunModel.workspace_id == workspace_id)
                .order_by(AgentRunModel.started_at.desc())
                .limit(100)
            ).all()
        return [agent_run_from_model(model) for model in models]
