# 智能情报与周期报告平台

面向个人和小团队的资料采集、联合分析与周期报告生成平台。

平台支持从公开网站、RSS、开放 API 和授权登录网站采集资料，也支持用户上传文档、URL 清单和结构化数据。系统按照用户定义的报告规则，通过可追溯的 AI 工作流生成日报、周报、月报或自定义期间报告，经人工审核后导出 DOCX/PDF，并可通过 SMTP 邮件发送。

## 当前阶段

项目当前处于“文档与架构设计”阶段。开始业务实现前，应先评审并确认 `docs/` 中的产品、架构、数据和接口设计。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [产品需求](docs/01-product-requirements.md) | 用户、场景、功能范围和验收标准 |
| [系统架构](docs/02-system-architecture.md) | 分层架构、组件边界和数据流 |
| [数据模型](docs/03-data-model.md) | 核心实体、关系、状态和存储分工 |
| [API 设计](docs/04-api-design.md) | REST、WebSocket、分页、错误和幂等约定 |
| [LangGraph 工作流](docs/05-langgraph-workflow.md) | Agent 节点、状态、返工与恢复策略 |
| [前端信息架构](docs/06-frontend-ux.md) | 页面结构和关键交互 |
| [安全与合规](docs/07-security.md) | 凭据、SSRF、上传、提示注入和审计 |
| [部署与运维](docs/08-deployment-operations.md) | Docker Compose、配置、监控和备份 |
| [实施路线](docs/09-implementation-roadmap.md) | 分阶段任务、检查点和完成标准 |
| [工程基线](docs/10-engineering-baseline.md) | Git、目录结构、环境变量、Compose 草案、测试和 CI |
| [架构决策](docs/decisions/README.md) | ADR 索引及关键技术决策 |

## 目标技术栈

- Nuxt 3、Vue 3、Tailwind CSS、ECharts
- FastAPI、SQLAlchemy、Celery
- LangGraph、LangChain
- DeepSeek 默认模型，可切换模型供应商
- MySQL、Redis、Elasticsearch 8.x
- Playwright、RSS、HTTP API 采集器
- Docker Compose 单机部署

## 设计原则

- 用户提供的采集需求是一次研究任务的唯一入口。
- 网络资料、用户文档和用户数据必须在同一分析流程中使用。
- 每条关键结论和每个图表数字都必须可追溯。
- 报告默认先生成草稿，必须经过人工审核才能发布。
- 采集器、模型、Agent、存储和交付通道均通过稳定接口扩展。

## MVP 闭环

首版优先交付最小可信闭环：登录、创建 `ResearchBrief`、上传资料、生成带引用的报告草稿、人工审核、Markdown/DOCX 导出。RSS/API/网页采集、图表编辑、PDF 和 SMTP 交付在 MVP 稳定后逐步增强。
