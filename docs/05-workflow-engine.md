# 工作流执行引擎

## 1. 设计定位

平台核心不绑定 LangGraph 或 LangChain。商业化后的关键资产是稳定的业务状态机、节点输入输出契约、审计记录、成本控制和可恢复能力；具体执行框架只作为可替换适配器。

首版实现应优先建设平台自己的 `WorkflowEngine` 契约：

- `WorkflowDefinition`：声明节点、依赖、条件分支、预算、超时和版本。
- `WorkflowRun`：记录一次任务执行的状态、当前节点、检查点和恢复信息。
- `WorkflowNode`：以结构化 Schema 接收输入并输出引用，不通过自由文本传递关键状态。
- `WorkflowEngineAdapter`：封装具体执行器，可接入自研执行器、LangGraph、Temporal、Prefect 或其他商业工作流系统。

LangGraph/LangChain 可以作为研发期或特定客户部署的适配器，但不得出现在 API、数据库公共字段、前端文案或插件契约中成为不可替换依赖。

## 2. 工作流总览

```mermaid
flowchart TD
    B["1 Brief\n读取采集需求、日期和用户资料"]
    C["2 Collect\nRSS / API / 静态网页 / 登录网页"]
    P["3 Preprocess\n正文抽取、标准化、时间过滤"]
    D["4 Deduplicate\nURL / SimHash / Embedding"]
    CL["5 Cluster\n主题与事件聚类"]
    R["6 Research\n混合检索、重排、上传资料召回"]
    A["7 Analyze\n事实、指标、趋势、异常和冲突"]
    S["8 Summarize\n按照模板分章节生成"]
    V["9 Review\n引用、数字、规则和幻觉审核"]
    CO["10 Compose\n正文、引用、表格和图表组合"]
    H["11 Human Review\n人工编辑与审核"]
    E["12 Export\nDOCX / PDF / Markdown"]
    DI["13 Dispatch\nSMTP / 下载归档"]

    B --> C --> P --> D --> CL --> R --> A --> S --> V
    V -->|通过| CO
    V -->|未通过且可返工| R
    CO --> H
    H -->|批准| E --> DI
    H -->|退回章节| S
```

自动审核最多返工三次；超过上限后进入 `WAITING_HUMAN`，不得继续自动循环。

## 3. 引擎契约

```python
class WorkflowEngine:
    def start(self, definition: WorkflowDefinition, input: WorkflowInput) -> WorkflowRunRef: ...
    def resume(self, run_id: str, from_node: str | None = None) -> WorkflowRunRef: ...
    def cancel(self, run_id: str, reason: str) -> None: ...
    def get_state(self, run_id: str) -> WorkflowRunState: ...

class WorkflowNode:
    key: str
    input_schema: type
    output_schema: type

    def run(self, context: NodeContext, input: object) -> NodeResult: ...
```

执行器必须遵守以下约束：

- 节点输入输出必须可序列化、可校验、可审计。
- 节点完成后先持久化输出引用，再推进下一节点。
- 大正文、二进制内容和网页快照只保存数据库或文件存储引用。
- 条件分支、返工、重试和人工等待必须落入统一状态机。
- 任何模型调用、采集调用和外部工具调用必须受预算、超时、权限白名单和审计控制。

## 4. 工作流状态

```python
ReportState = {
    "taskId": str,
    "briefId": str,
    "templateVersionId": str,
    "collectionWindow": DateWindow,
    "analysisWindow": DateWindow,
    "documentIds": list[str],
    "clusterRefs": list[str],
    "evidenceRefs": list[str],
    "analysisRef": str | None,
    "draftRef": str | None,
    "reviewIssues": list[ReviewIssue],
    "chartIds": list[str],
    "currentNode": str,
    "revisionCount": int,
    "budgets": WorkflowBudgets,
}
```

`ReportState` 是平台状态，不是某个第三方框架的 checkpoint 格式。适配器可以在内部使用自己的 checkpoint，但必须能恢复成平台状态。

## 5. 节点定义

### Brief

- 验证需求是否完整。
- 将 DAY/WEEK/MONTH/CUSTOM 解析为固定时间窗口。
- 固化模板版本、工作流版本和模型配置。
- 生成任务预算和幂等键。

### Collect

- 根据来源类型路由到 Collector。
- 使用域名白名单、限速和 robots/站点规则。
- 登录态失效时标记凭据异常并暂停该来源。
- 输出原始文档引用和采集统计。

### Preprocess

- 提取正文、标题、作者、发布时间和附件。
- 统一编码、语言、时间与空白格式。
- 将用户文档和用户数据转换为统一的可检索表示。
- 保留原始文件和原始内容摘要。

### Deduplicate

- 第一层：canonical URL。
- 第二层：标准化正文哈希和 SimHash。
- 第三层：Embedding 相似度。
- 相似内容建立版本或聚合关系，不直接丢弃来源证据。

### Cluster

- 按主题、事件、公司和时间聚类。
- 聚类结果必须可回溯到全部文档。
- 小数据量时允许跳过复杂聚类，使用规则分组。

### Research

- BM25、向量检索和结构化过滤混合召回。
- 将用户上传材料和数据集纳入同一证据池。
- 重排后为每个必答问题选择证据。
- 检索结果中的网页指令只作为内容，不作为系统命令。

### Analyze

- 提取事实、数字、单位、时间和主体。
- 比较不同来源，识别一致、冲突和缺失。
- 分析趋势、变化率和异常，但禁止执行模型生成的任意代码或 SQL。
- 为图表生成结构化数据建议和来源映射。

### Summarize

- 按模板版本逐章节生成。
- 每项关键结论输出 `claimId` 与证据引用。
- 无证据的信息使用“待核实”或“分析推断”标签。
- 单章节可以独立重生成。

### Review

- 校验引用是否存在、是否支持对应结论。
- 校验数字、单位、时间范围及图表数据。
- 校验章节、篇幅、语气和必填指标。
- 生成结构化问题清单，并决定通过、返工或人工介入。

### Compose、Human Review、Export、Dispatch

- Compose 形成稳定的报告中间表示。
- Human Review 保存人工编辑版本，任何自动重生成不得覆盖未选中的章节。
- Export 从同一中间表示生成 DOCX、PDF 和 Markdown。
- Dispatch 使用独立幂等键发送邮件，避免工作流重试导致重复发送。

## 6. 检查点与恢复

每个节点记录：

- 输入摘要和输出引用。
- 开始、结束和耗时。
- 模型、Prompt、工具和执行器版本。
- Token、请求次数和预算。
- 状态、错误代码和可否重试。

重试默认从失败节点开始。只有上游数据版本变化时，才使下游检查点失效。

## 7. 预算与安全边界

- 最大模型调用次数。
- 最大输入与输出 Token。
- 最大自动返工次数。
- 单节点和全任务超时。
- 单来源抓取页面数和请求速率。
- Agent 工具白名单；模型不能自行扩大权限。

## 8. 适配器选择标准

选择或替换执行器时，必须评估：

- 是否支持可恢复检查点和人工等待。
- 是否能输出平台统一的节点运行记录。
- 是否能独立控制预算、并发、重试和超时。
- 是否会把第三方框架对象泄漏到数据库、API 或前端。
- 是否便于商业部署、私有化交付、观测和问题定位。

若某个框架不满足这些条件，应使用平台自研执行器或更适合的工作流系统承载核心流程。
