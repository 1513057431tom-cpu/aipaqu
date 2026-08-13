from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.agents import (
    AgentConfiguration,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    ExecutionMode,
    ModelConfiguration,
)
from app.core.secrets import SecretCipher
from app.persistence.models import AgentConfigurationModel, AgentRunModel, ModelConfigurationModel
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


class SqlAlchemyAgentConfigurationStore:
    def __init__(self, engine: Engine, cipher: SecretCipher) -> None:
        self.engine = engine
        self.cipher = cipher

    def get_model_configuration(self, workspace_id: str) -> ModelConfiguration | None:
        with Session(self.engine) as session:
            model = session.get(ModelConfigurationModel, workspace_id)
        if model is None:
            return None
        return ModelConfiguration(
            workspace_id=model.workspace_id,
            provider=model.provider,
            model=model.model,
            base_url=model.base_url,
            api_key=self.cipher.decrypt(model.encrypted_api_key) if model.encrypted_api_key else None,
            updated_at=utc_aware(model.updated_at),
        )

    def save_model_configuration(self, configuration: ModelConfiguration) -> ModelConfiguration:
        model = ModelConfigurationModel(
            workspace_id=configuration.workspace_id,
            provider=configuration.provider,
            model=configuration.model,
            base_url=configuration.base_url,
            encrypted_api_key=(
                self.cipher.encrypt(configuration.api_key) if configuration.api_key else None
            ),
            updated_at=utc_naive(configuration.updated_at),
        )
        with Session(self.engine) as session:
            session.merge(model)
            session.commit()
        return configuration

    def get_agent_configuration(
        self, workspace_id: str, agent_key: str
    ) -> AgentConfiguration | None:
        with Session(self.engine) as session:
            model = session.scalar(
                select(AgentConfigurationModel).where(
                    AgentConfigurationModel.workspace_id == workspace_id,
                    AgentConfigurationModel.agent_key == agent_key,
                )
            )
        if model is None:
            return None
        return AgentConfiguration(
            workspace_id=model.workspace_id,
            agent_key=model.agent_key,
            system_prompt=model.system_prompt,
            default_execution_mode=ExecutionMode(model.default_execution_mode),
            tool_keys=tuple(json.loads(model.tool_keys_json)),
            updated_at=utc_aware(model.updated_at),
        )

    def save_agent_configuration(self, configuration: AgentConfiguration) -> AgentConfiguration:
        with Session(self.engine) as session:
            model = session.scalar(
                select(AgentConfigurationModel).where(
                    AgentConfigurationModel.workspace_id == configuration.workspace_id,
                    AgentConfigurationModel.agent_key == configuration.agent_key,
                )
            )
            if model is None:
                model = AgentConfigurationModel(
                    id=f"acfg_{uuid4().hex}",
                    workspace_id=configuration.workspace_id,
                    agent_key=configuration.agent_key,
                )
                session.add(model)
            model.system_prompt = configuration.system_prompt
            model.default_execution_mode = configuration.default_execution_mode.value
            model.tool_keys_json = json.dumps(configuration.tool_keys)
            model.updated_at = utc_naive(configuration.updated_at)
            session.commit()
        return configuration
