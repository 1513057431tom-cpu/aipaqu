# 通用物料与供应情报平台

面向制造企业的内外部数据联合分析与供应情报平台。

平台从 ERP、MES、WMS、数据库或 Excel/CSV 获取物料、库存、消耗、需求、在途订单和供应商数据，同时定时监控供应商网站、价格页面、市场平台和新闻来源。系统将内外部数据映射到统一的物料与供应商主数据，形成可追溯的变化信号、采购建议和日报、周报、月报。

确定性规则负责计算库存可支撑天数、缺料风险、补货日期和建议数量；AI 负责抽取、辅助匹配、解释和报告撰写。所有采购建议都需要人工审核，首版不自动创建采购订单或写回企业系统。

## 当前阶段

首个可运行的 v0.1 核心闭环已完成：FastAPI、Nuxt、MySQL 持久化、物料与供应商、CSV 内部快照导入、外部定向监控、信号审核、确定性采购建议、日报快照、周报/月报聚合、人工版本和 Markdown/DOCX 导出。`ResearchBrief` 保留为后续自定义分析能力。

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

本地开发：

```bash
cd backend
python -m pytest

cd ../frontend
npm install
npm run dev
```

使用本机 MySQL 时，在未提交的 `.env` 中配置 `MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DATABASE`、`MYSQL_USER` 和 `MYSQL_PASSWORD`，再于 `backend/` 执行 `python -m alembic upgrade head`。业务进程应使用独立低权限账号，不使用 MySQL root 账号。

## Commands

| 命令 | 说明 |
| --- | --- |
| `python -m pytest` | 在 `backend/` 运行后端测试 |
| `npm test` | 在 `frontend/` 运行 Nuxt 类型检查 |
| `npm run build` | 在 `frontend/` 构建 Nuxt 应用 |
| `docker compose up --build` | 启动 API、前端、MySQL、Redis 和 Elasticsearch |
| `alembic upgrade head` | 在 `backend/` 初始化或升级 MySQL 业务表 |

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [产品需求](docs/01-product-requirements.md) | 用户、场景、功能范围和验收标准 |
| [系统架构](docs/02-system-architecture.md) | 分层架构、组件边界和数据流 |
| [数据模型](docs/03-data-model.md) | 核心实体、关系、状态和存储分工 |
| [API 设计](docs/04-api-design.md) | REST、WebSocket、分页、错误和幂等约定 |
| [工作流执行引擎](docs/05-workflow-engine.md) | 节点契约、状态、返工、适配器与恢复策略 |
| [前端信息架构](docs/06-frontend-ux.md) | 页面结构和关键交互 |
| [安全与合规](docs/07-security.md) | 凭据、SSRF、上传、提示注入和审计 |
| [部署与运维](docs/08-deployment-operations.md) | Docker Compose、配置、监控和备份 |
| [实施路线](docs/09-implementation-roadmap.md) | 分阶段任务、检查点和完成标准 |
| [工程基线](docs/10-engineering-baseline.md) | Git、目录结构、环境变量、Compose 草案、测试和 CI |
| [爬虫参考设计](docs/11-crawler-reference-design.md) | 浏览器采集、站点适配器、Profile、策略和合规边界 |
| [产品一页纸](docs/ideas/material-supply-intelligence-platform.md) | 问题、产品方向、MVP、假设和明确不做事项 |
| [架构决策](docs/decisions/README.md) | ADR 索引及关键技术决策 |

## 目标技术栈

- Nuxt 3、Vue 3、Tailwind CSS、ECharts
- FastAPI、SQLAlchemy、Celery
- 平台工作流引擎契约，可选适配 LangGraph、Temporal、Prefect 或自研执行器
- DeepSeek 默认模型，可切换模型供应商
- MySQL、Redis、Elasticsearch 8.x
- Playwright、RSS、HTTP API 采集器
- Docker Compose 单机部署

## 设计原则

- ERP、MES、WMS 等企业系统仍是事实与交易来源，平台首版只读接入。
- 内部经营数据和外部网站信号必须映射到统一的物料与供应商实体。
- 外部采集只访问公开或用户已授权的资源，不绕过验证码、付费墙和访问控制。
- 每条变化、建议和报告结论都必须追溯到结构化快照或原始证据。
- 规则和统计模型负责可复现计算，AI 不直接执行高风险采购决策。
- 周报和月报只聚合日报结构化快照，不自动启动内部同步或浏览器采集。
- 连接器、采集器、模型和工作流执行器均通过稳定接口扩展。

## MVP 闭环

v0.1 核心闭环已交付：登录、CSV 内部数据导入、物料与供应商、指定公开页面的手动采集、变化信号、每日情报快照、可解释采购建议、人工审核，以及日报/周报/月报的 Markdown/DOCX 导出。Excel 原生解析、定时调度、ERP/MES/WMS 标准连接器、自动写回、高级预测、PDF、消息交付和复杂浏览器站点适配器在闭环稳定后逐步增强。
