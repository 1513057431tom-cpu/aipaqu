# 架构决策记录

| ADR | 状态 | 决策 |
| --- | --- | --- |
| [ADR-001](ADR-001-modular-monolith.md) | Accepted | 首版采用模块化单体与独立 Worker |
| [ADR-002](ADR-002-storage-responsibilities.md) | Accepted | MySQL、Redis、Elasticsearch 和文件存储分工 |
| [ADR-003](ADR-003-versioned-workflows.md) | Accepted | 模板与工作流版本化并固定到任务 |
| [ADR-004](ADR-004-mvp-closed-loop.md) | Accepted | 首版先交付最小可信闭环 |
| [ADR-005](ADR-005-controlled-access-challenges.md) | Accepted | 访问挑战采用人工接管与授权记录 |
| [ADR-006](ADR-006-framework-neutral-workflow-engine.md) | Accepted | 工作流内核保持框架中立 |
| [ADR-007](ADR-007-periodic-reports-use-daily-snapshots.md) | Accepted | 周报和月报默认聚合日报快照 |
