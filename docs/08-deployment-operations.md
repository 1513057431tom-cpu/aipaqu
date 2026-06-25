# 部署与运维

## 1. 首版部署拓扑

单机 Docker Compose 包含：

```text
frontend        Nuxt 服务
api             FastAPI 服务
worker          Celery 普通任务
crawler-worker  Playwright 隔离采集任务
beat            定时调度
mysql           业务数据库
redis           队列、缓存和锁
elasticsearch   全文和向量检索
```

上传、网页快照和报告导出使用独立持久化卷。后续可将 `StorageProvider` 切换到 MinIO/S3。

## 2. 环境配置

配置按类别拆分：

- 应用：环境、时区、公开地址、CORS。
- 数据：MySQL、Redis、Elasticsearch。
- 安全：会话密钥、主加密密钥。
- 模型：DeepSeek 地址、Key、模型名、Embedding Provider。
- 采集：并发、超时、速率和页面上限。
- 文件：目录、大小、类型和保留策略。
- SMTP：主机、端口、TLS、账号和默认发件人。

启动时必须验证必填配置；生产环境禁止使用默认密钥。

## 3. 健康检查

- `/health/live`：进程可响应。
- `/health/ready`：MySQL、Redis 和 Elasticsearch 可用。
- Worker 心跳：最近一次心跳时间和当前队列。
- 浏览器采集检查：Playwright 浏览器是否可启动。
- SMTP 检查只在用户主动测试时执行，不作为常规就绪条件。

## 4. 可观测性

结构化日志至少包含：

- `requestId`
- `workspaceId`
- `userId`
- `taskId`
- `workflowRunId`
- `nodeKey`
- `durationMs`
- `errorCode`

核心指标：

- API 延迟与错误率。
- 队列长度和等待时间。
- 采集成功率、页面数和被限流次数。
- 工作流成功率、节点耗时和返工次数。
- 模型请求数、Token 和成本估算。
- 邮件发送成功率与重试次数。

## 5. 备份与恢复

- MySQL：每日全量备份，保留最近 7 天；发布报告前可选创建逻辑快照。
- 文件存储：每日增量备份。
- Elasticsearch：可由 MySQL 元数据和原始文件重建，但生产仍建议周期快照。
- Redis：不作为业务唯一事实来源，不要求从备份恢复任务真相。

恢复演练必须验证：

- 用户与配置可恢复。
- 报告、版本、引用和导出物可恢复。
- 文档索引可重建。
- 未完成任务可识别并重新排队。

## 6. 升级策略

- 数据库变化使用可回滚迁移。
- API 采用 `/api/v1`，新增字段优先保持可选。
- 工作流和模板均版本化，运行中的任务固定使用启动时版本。
- Docker 镜像固定版本，不使用不可追踪的 `latest`。

