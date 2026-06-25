# 工程基线

本文档定义开始源码实现前必须落地的仓库结构、配置模板、Docker Compose 草案、测试脚本和 CI 检查项。

## 1. Git 与仓库结构

项目应初始化为 Git 仓库，并提交以下基线文件：

```text
.
├── backend/
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── app/
│   ├── components/
│   ├── tests/
│   └── package.json
├── docs/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

`backend` 和 `frontend` 目录在真正引入源码时创建；当前阶段只维护文档、环境模板和工程约束。

## 2. 环境变量模板

`.env.example` 必须只包含占位值，不包含真实秘密。实现时至少覆盖：

- 应用：`APP_ENV`、`APP_PUBLIC_URL`、`APP_TIMEZONE`、`ALLOWED_ORIGINS`
- 安全：`SESSION_SECRET`、`MASTER_ENCRYPTION_KEY`、`CSRF_COOKIE_NAME`
- 数据：`MYSQL_*`、`REDIS_URL`、`ELASTICSEARCH_URL`
- 模型：`LLM_PROVIDER`、`DEEPSEEK_API_KEY`、`EMBEDDING_PROVIDER`
- 文件：`FILE_STORAGE_PATH`、`MAX_UPLOAD_MB`
- 采集：`CRAWLER_MAX_CONCURRENCY`、`CRAWLER_REQUEST_TIMEOUT_SECONDS`
- SMTP：`SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`

生产启动必须拒绝默认密钥和空秘密。

## 3. Docker Compose 草案

首版 Compose 服务：

```yaml
services:
  frontend:
    build: ./frontend
    env_file: .env
    depends_on:
      - api

  api:
    build: ./backend
    env_file: .env
    depends_on:
      - mysql
      - redis
      - elasticsearch

  worker:
    build: ./backend
    command: celery -A app.worker worker --queues default
    env_file: .env

  crawler-worker:
    build: ./backend
    command: celery -A app.worker worker --queues crawler
    env_file: .env

  beat:
    build: ./backend
    command: celery -A app.worker beat
    env_file: .env

  mysql:
    image: mysql:8.4

  redis:
    image: redis:7

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.14.0
```

实现时不得使用 `latest` 镜像标签；所有持久化目录必须声明命名卷。

## 4. 测试脚本约定

后端：

```bash
cd backend
python -m pytest
python -m ruff check .
python -m mypy app
```

前端：

```bash
cd frontend
npm test
npm run lint
npm run build
```

端到端：

```bash
cd frontend
npm run test:e2e
```

## 5. CI 检查清单

每次合并前必须通过：

- 后端单元测试。
- 前端单元测试。
- 前端构建。
- API Schema 或 OpenAPI 生成检查。
- 数据库迁移检查。
- `npm audit` 或等价依赖审计。
- Secret 扫描。
- 文档一致性检查：状态名、接口路径、角色名和核心实体名一致。

MVP 交付前必须额外通过：

- 创建 Brief 到导出 DOCX 的端到端测试。
- 上传恶意文件、SSRF URL、提示注入样本文本的安全回归测试。
- Worker 中断后从失败节点恢复的集成测试。
