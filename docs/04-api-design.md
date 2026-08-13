# API 设计

## 1. 通用约定

- 基础路径：`/api/v1`
- 数据格式：JSON；文件上传使用 `multipart/form-data`
- 字段命名：`camelCase`
- 枚举值：`UPPER_SNAKE_CASE`
- 认证：安全 Cookie 会话
- 列表默认分页，最大 `pageSize=100`
- 修改接口使用 `PATCH`
- 创建任务、导出和发送支持 `Idempotency-Key`
- 写接口统一返回服务端生成的 `id`、`createdAt`、`updatedAt`
- 所有受保护接口必须校验会话、角色和 `workspaceId`

分页响应：

```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalItems": 0,
    "totalPages": 0
  }
}
```

错误响应：

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数不合法",
    "details": {},
    "requestId": "req_..."
  }
}
```

### 状态码

| 状态码 | 用途 |
| --- | --- |
| `200` | 查询、更新或动作执行成功 |
| `201` | 创建成功 |
| `202` | 长任务已接受，返回任务标识 |
| `204` | 删除或归档成功，无响应体 |
| `400` | 请求格式错误或非法状态转换 |
| `401` | 未登录 |
| `403` | 已登录但无权限 |
| `404` | 资源不存在或不属于当前工作空间 |
| `409` | 幂等键、版本号或唯一约束冲突 |
| `413` | 上传文件超过限制 |
| `415` | 上传文件类型不支持 |
| `422` | 字段校验失败 |
| `429` | 触发限流 |

### 权限约定

| 角色 | 权限 |
| --- | --- |
| `ADMIN` | 管理用户、连接器、字段映射、模型、采集凭据和安全配置；可查看和操作工作空间内所有资源 |
| `EDITOR` | 导入数据、维护实体映射、配置监控、审核信号和建议、编辑及导出报告；不能读取秘密明文或修改系统级配置 |

### 幂等约定

- `Idempotency-Key` 必须是客户端生成的随机字符串，推荐 UUID。
- 服务端按 `workspaceId + route + Idempotency-Key` 去重。
- 相同 key 且请求摘要一致时返回第一次操作结果。
- 相同 key 但请求摘要不一致时返回 `409 IDEMPOTENCY_CONFLICT`。
- 幂等记录至少保留 24 小时；发送邮件类操作保留时间不得短于 7 天。

### 列表查询

所有列表接口支持：

```text
page=1
pageSize=20
sortBy=createdAt
sortOrder=desc
status=...
createdAfter=2026-06-01T00:00:00Z
createdBefore=2026-06-30T23:59:59Z
q=...
```

服务端只允许白名单字段参与排序和过滤，未知参数返回 `422`。

### 文件上传限制

MVP 支持：

- `text/plain`
- `text/markdown`
- `application/pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `text/csv`
- `application/json`
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

默认限制：

- 单文件最大 50 MB。
- 单次上传最多 20 个文件。
- CSV/XLSX 最多 100,000 行。
- PDF 最多 300 页。
- 压缩文件不在 MVP 支持范围内。

上传接口必须同时校验扩展名、MIME、魔数和解析结果。

## 2. 认证

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/auth/login` | 登录并建立会话 |
| POST | `/auth/logout` | 注销当前会话 |
| GET | `/auth/me` | 当前用户 |
| PATCH | `/auth/password` | 修改密码 |

## 3. 物料与供应情报

### 企业连接与同步

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| GET | `/enterprise-connections` | 查询内部数据连接 | `ADMIN`, `EDITOR` |
| POST | `/enterprise-connections` | 创建只读连接 | `ADMIN` |
| PATCH | `/enterprise-connections/{connectionId}` | 修改连接元数据或调度 | `ADMIN` |
| POST | `/enterprise-connections/{connectionId}/test` | 测试连接，不返回秘密 | `ADMIN` |
| GET | `/enterprise-connections/{connectionId}/field-mappings` | 查询字段映射版本 | `ADMIN`, `EDITOR` |
| POST | `/enterprise-connections/{connectionId}/field-mappings` | 创建映射草稿 | `ADMIN`, `EDITOR` |
| POST | `/enterprise-connections/{connectionId}/sync-jobs` | 启动只读同步 | `ADMIN`, `EDITOR` |
| GET | `/data-sync-jobs/{jobId}` | 查询同步结果与错误行 | `ADMIN`, `EDITOR` |
| POST | `/imports` | 上传 Excel/CSV 并创建导入任务 | `ADMIN`, `EDITOR` |

创建连接时只能提交秘密引用，API 不接受或返回可重复读取的明文凭据：

```json
{
  "name": "生产 ERP 只读连接",
  "systemType": "ERP",
  "adapterKey": "generic-jdbc-v1",
  "configRef": "secret://workspace/ws_1/erp_readonly",
  "syncMode": "READ_ONLY",
  "schedule": "0 */6 * * *"
}
```

创建同步和导入任务必须携带 `Idempotency-Key`，成功返回 `202`：

```json
{
  "jobId": "sync_01...",
  "status": "QUEUED",
  "connectionId": "conn_01...",
  "fieldMappingVersion": 3,
  "createdAt": "2026-07-16T08:00:00Z"
}
```

### 物料、供应商与实体映射

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/materials` | 查询物料，支持编码、名称、分类、状态过滤 |
| POST | `/materials` | 创建物料 |
| GET | `/materials/{materialId}` | 查看物料聚合详情 |
| PATCH | `/materials/{materialId}` | 修改未版本化的主数据字段 |
| GET | `/materials/{materialId}/timeline` | 查询库存、消耗、在途、信号和建议时间线 |
| GET | `/suppliers` | 查询供应商 |
| POST | `/suppliers` | 创建供应商 |
| GET | `/suppliers/{supplierId}` | 查看供应商详情 |
| PATCH | `/suppliers/{supplierId}` | 修改供应商主数据 |
| GET | `/supplier-materials` | 查询供货关系 |
| POST | `/supplier-materials` | 创建供货关系 |
| GET | `/entity-mapping-candidates` | 查询待确认映射 |
| POST | `/entity-mapping-candidates/{candidateId}/confirm` | 确认映射 |
| POST | `/entity-mapping-candidates/{candidateId}/reject` | 拒绝映射 |

物料更新可修改编码、名称、规格、分类、基础单位、安全库存和参考交期。空请求或显式 `null` 返回 `422`；编码冲突返回 `409 MATERIAL_CODE_CONFLICT`；不存在或跨工作空间访问返回 `404 MATERIAL_NOT_FOUND`。历史库存、建议和报告快照不会随主数据修改而改写。

`MaterialResponse`：

```json
{
  "id": "mat_01...",
  "externalCode": "RM-000128",
  "name": "基础原料 A",
  "specification": "工业级 25kg",
  "category": "原材料",
  "baseUnit": "kg",
  "safetyStockQty": 1200,
  "leadTimeDays": 14,
  "dataFreshness": {
    "inventoryAt": "2026-07-16T00:00:00Z",
    "consumptionThrough": "2026-07-15",
    "openSupplyAt": "2026-07-16T00:00:00Z"
  },
  "status": "ACTIVE"
}
```

### 内部快照与外部信号

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/inventory-snapshots` | 查询库存快照 |
| GET | `/consumption-snapshots` | 查询消耗快照 |
| GET | `/material-demands` | 查询需求记录 |
| GET | `/open-supply-snapshots` | 查询在途订单快照 |
| GET | `/external-signals` | 查询外部变化信号 |
| GET | `/external-signals/{signalId}` | 查看结构化变化和原始证据 |
| POST | `/external-signals/{signalId}/confirm` | 确认信号 |
| POST | `/external-signals/{signalId}/reject` | 拒绝信号 |
| GET | `/daily-intelligence-snapshots` | 查询每日情报快照 |
| POST | `/daily-intelligence-snapshots/build` | 创建每日快照与建议计算任务 |
| GET | `/daily-intelligence-snapshots/{snapshotId}` | 查看快照覆盖与内容摘要 |

外部信号列表支持 `materialId`、`supplierId`、`signalType`、`occurredAfter`、`occurredBefore`、`reviewStatus` 和 `minConfidence` 过滤。证据下载使用短期签名 URL，不直接暴露存储路径。

### 采购建议与人工决策

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/procurement-recommendations` | 查询建议，支持风险、状态、日期和物料过滤 |
| GET | `/procurement-recommendations/{recommendationId}` | 查看建议、计算过程和证据 |
| POST | `/procurement-recommendations/{recommendationId}/decisions` | 批准、调整或拒绝建议 |
| POST | `/procurement-recommendations/export` | 导出已选择建议，不创建采购订单 |

`ProcurementRecommendationResponse`：

```json
{
  "id": "rec_01...",
  "materialId": "mat_01...",
  "supplierId": "sup_01...",
  "asOfDate": "2026-07-16",
  "horizonEnd": "2026-08-15",
  "recommendedOrderDate": "2026-07-18",
  "latestOrderDate": "2026-07-21",
  "recommendedQty": 5000,
  "unit": "kg",
  "riskLevel": "HIGH",
  "reasonCodes": ["PROJECTED_SHORTAGE", "LEAD_TIME_INCREASED"],
  "calculation": {
    "availableQty": 2200,
    "openSupplyQty": 1000,
    "demandQty": 7100,
    "safetyStockQty": 1100,
    "leadTimeDays": 17,
    "orderMultiple": 500
  },
  "inputDigest": "sha256:...",
  "algorithm": {"key": "reorder-point", "version": "1.0.0"},
  "evidenceRefs": ["signal_01...", "inventory_01..."],
  "status": "PROPOSED"
}
```

`DecideRecommendationRequest`：

```json
{
  "decision": "ADJUST",
  "adjustedOrderDate": "2026-07-19",
  "adjustedQty": 4500,
  "reason": "结合最小运输批量和现场盘点调整"
}
```

决策接口要求 `If-Match` 版本或当前建议版本号，过期修改返回 `409 VERSION_CONFLICT`。批准或调整只改变平台内决策状态，不写回 ERP。

## 4. 自定义分析工作台

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/briefs` | 查询采集需求 |
| POST | `/briefs` | 创建采集需求 |
| GET | `/briefs/{briefId}` | 查看需求 |
| PATCH | `/briefs/{briefId}` | 修改需求 |
| DELETE | `/briefs/{briefId}` | 归档需求 |
| POST | `/briefs/{briefId}/clone` | 复制为新需求 |
| POST | `/briefs/{briefId}/validate` | 校验时间、来源和规则完整性 |
| GET | `/briefs/{briefId}/sources` | 查询指定网站、URL、关键词 |
| POST | `/briefs/{briefId}/sources` | 添加指定网站、URL、关键词 |
| POST | `/briefs/{briefId}/attachments` | 上传或粘贴补充资料 |
| GET | `/briefs/{briefId}/datasets` | 查询用户数据集 |
| POST | `/briefs/{briefId}/datasets` | 创建用户数据集 |
| POST | `/briefs/{briefId}/run` | 创建一次报告任务 |

创建需求的时间范围示例：

```json
{
  "title": "基础原料 A 供应变化专题",
  "objective": "分析价格、供货状态、交期和供应商动态",
  "dateRange": {
    "kind": "WEEK",
    "referenceDate": "2026-06-25",
    "timezone": "Asia/Shanghai"
  },
  "requiredQuestions": [
    "本周价格和交期发生了哪些可验证变化？",
    "哪些变化可能影响未来三十天的供应？"
  ]
}
```

自定义期间使用 `kind=CUSTOM`、`startDate` 和 `endDate`。

### 核心 Schema

`CreateBriefRequest`：

```json
{
  "title": "基础原料 A 供应变化专题",
  "objective": "分析价格、供货状态、交期和供应商动态",
  "requiredQuestions": ["本周价格和交期发生了哪些可验证变化？"],
  "dateRange": {
    "kind": "WEEK",
    "referenceDate": "2026-06-25",
    "timezone": "Asia/Shanghai"
  },
  "analysisConstraints": {
    "metricRules": ["价格统一换算为基础单位"],
    "exclusions": ["不使用未经证实的社交媒体传言"],
    "outputRequirements": ["每条关键结论必须带引用"]
  }
}
```

`BriefResponse`：

```json
{
  "id": "brief_...",
  "workspaceId": "ws_...",
  "title": "基础原料 A 供应变化专题",
  "objective": "分析价格、供货状态、交期和供应商动态",
  "requiredQuestions": ["本周价格和交期发生了哪些可验证变化？"],
  "dateRange": {
    "kind": "WEEK",
    "referenceDate": "2026-06-25",
    "timezone": "Asia/Shanghai",
    "collectionStart": "2026-06-22T00:00:00+08:00",
    "collectionEnd": "2026-06-28T23:59:59+08:00",
    "analysisStart": "2026-06-22T00:00:00+08:00",
    "analysisEnd": "2026-06-28T23:59:59+08:00"
  },
  "status": "DRAFT",
  "createdAt": "2026-06-25T10:20:30Z",
  "updatedAt": "2026-06-25T10:20:30Z"
}
```

`RunBriefRequest`：

```json
{
  "templateVersionId": "tplv_...",
  "workflowKey": "MVP_REPORT",
  "budget": {
    "maxModelCalls": 30,
    "maxInputTokens": 200000,
    "maxOutputTokens": 30000
  }
}
```

`RunBriefResponse` 返回 `202`：

```json
{
  "taskId": "task_...",
  "status": "QUEUED",
  "reportId": null,
  "currentNode": "BRIEF",
  "eventsUrl": "/api/v1/events?workspaceId=ws_...&cursor=evt_..."
}
```

## 5. 数据源与采集

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/sources` | 查询数据源列表 |
| POST | `/sources` | 创建数据源 |
| GET | `/sources/{sourceId}` | 查看数据源详情 |
| PATCH | `/sources/{sourceId}` | 更新数据源 |
| DELETE | `/sources/{sourceId}` | 停用数据源 |
| POST | `/sources/{sourceId}/test` | 测试连接和解析 |
| POST | `/sources/{sourceId}/credentials` | 保存加密凭据 |
| GET | `/sources/{sourceId}/browser-profiles` | 查询浏览器 Profile |
| POST | `/sources/{sourceId}/browser-profiles` | 创建浏览器 Profile 引用 |
| GET | `/sources/{sourceId}/site-adapters` | 查询站点适配器版本 |
| POST | `/sources/{sourceId}/site-adapters` | 保存站点适配器草稿 |
| POST | `/sources/{sourceId}/site-adapters/{adapterId}/test` | 测试适配器抽取结果 |
| GET | `/sources/{sourceId}/access-grants` | 查询来源授权记录 |
| POST | `/sources/{sourceId}/access-grants` | 创建来源授权记录 |
| GET | `/access-challenges` | 查询访问挑战 |
| POST | `/access-challenges/{challengeId}/manual-sessions` | 创建人工接管会话 |
| POST | `/access-challenges/{challengeId}/resolve` | 标记挑战已人工处理 |
| POST | `/sources/{sourceId}/collect` | 手动发起采集 |
| GET | `/collection-jobs` | 查询采集任务 |
| POST | `/collection-jobs/{jobId}/retry` | 从检查点重试 |

`CreateSiteAdapterRequest`：

```json
{
  "entryUrls": ["https://example.com/news"],
  "allowedDomains": ["example.com"],
  "selectors": {
    "title": "h1",
    "publishedAt": "time",
    "content": "article",
    "exclude": [".ad", ".related"]
  },
  "actions": [
    {
      "type": "WAIT_FOR_SELECTOR",
      "selector": "article",
      "timeoutMs": 10000
    }
  ],
  "crawlPolicyId": "policy_..."
}
```

`SiteAdapterTestResponse`：

```json
{
  "adapterId": "adapter_...",
  "status": "SUCCEEDED",
  "markdownPreview": "# 标题\n\n正文摘要...",
  "metadata": {
    "title": "标题",
    "publishedAt": "2026-06-26T08:00:00Z"
  },
  "warnings": []
}
```

`CreateAccessGrantRequest`：

```json
{
  "grantType": "PAID_SUBSCRIPTION",
  "grantedTo": "workspace",
  "purpose": "生成行业周报",
  "licenseNote": "用户确认该账号拥有访问和内部分析授权",
  "validFrom": "2026-06-26",
  "validTo": "2027-06-25"
}
```

`AccessChallengeResponse`：

```json
{
  "id": "challenge_...",
  "sourceId": "src_...",
  "jobId": "job_...",
  "challengeType": "CAPTCHA_REQUIRED",
  "url": "https://example.com/article",
  "statusCode": 200,
  "status": "WAITING_HUMAN",
  "screenshotUrl": "/api/v1/access-challenges/challenge_.../screenshot",
  "createdAt": "2026-06-26T08:00:00Z"
}
```

## 6. 文档与检索

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/documents` | 查询文档 |
| POST | `/documents` | 上传文档 |
| GET | `/documents/{documentId}` | 文档元数据和正文摘要 |
| GET | `/documents/{documentId}/source` | 查看来源或下载原文件 |
| POST | `/documents/search` | 全文、向量和过滤联合检索 |
| POST | `/documents/{documentId}/reindex` | 重新解析并索引 |

`UploadMaterialResponse`：

```json
{
  "materialId": "mat_...",
  "documentId": "doc_...",
  "originType": "USER_DOCUMENT",
  "fileName": "industry-notes.docx",
  "status": "PARSING",
  "sourceName": "用户上传",
  "occurredAt": "2026-06-25",
  "createdAt": "2026-06-25T10:20:30Z"
}
```

## 7. 报告模板

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/templates` | 查询模板列表 |
| POST | `/templates` | 创建模板 |
| POST | `/templates/{templateId}/extract` | 从范例文档抽取规则草稿 |
| GET | `/templates/{templateId}/versions` | 查询模板版本 |
| POST | `/templates/{templateId}/versions` | 创建模板版本 |
| POST | `/templates/{templateId}/versions/{version}/publish` | 发布模板版本 |

## 8. 报告任务、报告和图表

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/report-tasks` | 查询任务 |
| POST | `/report-tasks` | 创建任务 |
| POST | `/report-tasks/{taskId}/pause` | 暂停 |
| POST | `/report-tasks/{taskId}/resume` | 恢复 |
| POST | `/report-tasks/{taskId}/retry` | 从失败节点重试 |
| GET | `/reports` | 报告列表 |
| GET | `/reports/{reportId}` | 查看报告详情 |
| PATCH | `/reports/{reportId}` | 更新报告元数据 |
| GET | `/reports/{reportId}/versions` | 查询报告版本 |
| POST | `/reports/{reportId}/versions` | 保存人工编辑版本 |
| POST | `/reports/{reportId}/sections/{sectionId}/regenerate` | 重生成单章节 |
| POST | `/reports/{reportId}/submit-review` | 提交审核 |
| POST | `/reports/{reportId}/approve` | 审核通过 |
| POST | `/reports/{reportId}/publish` | 发布 |
| POST | `/reports/{reportId}/exports` | 创建导出任务 |
| GET | `/charts/{chartId}` | 查看图表 |
| PATCH | `/charts/{chartId}` | 编辑图表 |
| POST | `/charts/{chartId}/render` | 渲染图表图片 |

`CreateReportTaskRequest`：

```json
{
  "briefId": "brief_...",
  "templateVersionId": "tplv_...",
  "reportPeriod": "WEEKLY",
  "periodStart": "2026-06-22",
  "periodEnd": "2026-06-28",
  "inputMode": "AGGREGATE_DAILY_SNAPSHOTS",
  "allowBackfillDailyReports": false,
  "idempotencyKey": "report-task:brief_...:2026-W26"
}
```

约束：

- `reportPeriod=DAILY` 默认 `inputMode=COLLECT_AND_ANALYZE`。
- `reportPeriod=WEEKLY` 或 `MONTHLY` 默认 `inputMode=AGGREGATE_DAILY_SNAPSHOTS`。
- 周报/月报创建任务时只读取覆盖日期内已批准的 `DailyIntelligenceSnapshot` 和已审核或已发布的日报版本。
- 当日报快照缺失且 `allowBackfillDailyReports=false` 时返回 `409 PERIOD_INPUT_INCOMPLETE`，响应中包含 `missingDates`。
- 即使 `allowBackfillDailyReports=true`，也只能创建“补生成日报”任务；不得在周报/月报点击动作中直接打开浏览器。

`PeriodInputIncompleteResponse`：

```json
{
  "error": {
    "code": "PERIOD_INPUT_INCOMPLETE",
    "message": "Weekly or monthly report requires daily report snapshots.",
    "details": {
      "missingDates": ["2026-06-24", "2026-06-25"],
      "requiredDailySnapshotStatus": ["APPROVED"],
      "requiredReportStatus": ["APPROVED", "PUBLISHED"]
    }
  }
}
```

`ReportDetailResponse`：

```json
{
  "id": "report_...",
  "taskId": "task_...",
  "title": "物料与供应情报周报",
  "status": "DRAFT",
  "currentVersion": {
    "id": "rpv_...",
    "version": 1,
    "contentJson": {
      "sections": [
        {
          "sectionId": "summary",
          "title": "摘要",
          "bodyMarkdown": "本周共有 3 项高风险缺料建议...",
          "claimIds": ["claim_1"]
        }
      ]
    },
    "markdown": "# 物料与供应情报周报\n\n...",
    "htmlSnapshotRef": "files/reports/rpv_.../snapshot.html",
    "changeSource": "AI_DRAFT"
  },
  "inputSnapshots": [
    {
      "dailySnapshotId": "daily_intel_...",
      "sourceReportId": "report_daily_...",
      "sourceVersionId": "rpv_daily_...",
      "sourcePeriod": "DAILY",
      "coveredDate": "2026-06-24",
      "structuredDataRef": "snapshots/daily/2026-06-24.json",
      "contentDigest": "sha256:...",
      "htmlSnapshotRef": "files/reports/rpv_daily_.../snapshot.html"
    }
  ],
  "citations": [
    {
      "claimId": "claim_1",
      "sectionId": "summary",
      "documentId": "doc_...",
      "chunkId": "chk_...",
      "supportType": "DIRECT",
      "quoteDigest": "sha256:..."
    }
  ]
}
```

## 9. SMTP 交付

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/delivery-configs` | 查询交付配置 |
| POST | `/delivery-configs` | 创建交付配置 |
| PATCH | `/delivery-configs/{configId}` | 更新 SMTP 配置 |
| POST | `/delivery-configs/{configId}/test` | 发送测试邮件 |
| POST | `/reports/{reportId}/deliveries` | 创建正式发送任务 |
| GET | `/delivery-records` | 查看发送记录 |
| POST | `/delivery-records/{recordId}/retry` | 幂等重试 |

## 10. 实时事件

WebSocket：`/api/v1/events?workspaceId=...&cursor=...`

事件统一格式：

```json
{
  "eventId": "evt_...",
  "cursor": "evt_...",
  "type": "WORKFLOW_NODE_COMPLETED",
  "resourceType": "REPORT_TASK",
  "resourceId": "task_...",
  "occurredAt": "2026-06-25T10:20:30Z",
  "data": {
    "node": "ANALYZE",
    "progress": 62
  }
}
```

客户端首次连接可以不传 `cursor`；重连时传入最后收到的 `cursor`。服务端尽力补发保留窗口内事件；如果 cursor 过期，服务端返回 `EVENT_CURSOR_EXPIRED`，客户端必须通过 REST 获取真实状态。

事件只用于改善实时体验。业务真相仍以 REST 查询和数据库持久化状态为准。
