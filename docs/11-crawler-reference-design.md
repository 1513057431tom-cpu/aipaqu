# 爬虫与浏览器采集参考设计

本文档参考 `crawl4ai`、AdsPower Local API、GoLogin API 等项目的公开能力，沉淀本项目后续采集增强设计。目标是支持授权、可审计、可恢复的资料采集，而不是提供验证码、付费墙或访问控制绕过能力。

## 1. 可借鉴能力

### crawl4ai 类能力

- 将网页转换为适合 LLM/RAG 使用的 Markdown、结构化摘要和元数据。
- 支持浏览器配置、CrawlerRun 配置、会话复用、缓存策略和截图。
- 通过 hooks 或策略扩展滚动、点击、等待、抽取和过滤逻辑。
- 将采集与内容清洗、去重、分块、引用保留结合。

### 反检测浏览器类能力

这类工具通常以“浏览器 Profile”为核心，封装浏览器指纹、代理、Cookie、LocalStorage、启动/停止、远程调试端口和自动化连接信息。对本项目有价值的是工程抽象：

- `BrowserProfile`：保存授权采集所需的浏览器环境标识。
- `ProxyProfile`：为不同来源配置出口网络和限速策略。
- `RemoteBrowserSession`：通过本地 API 或 CDP 连接到外部浏览器实例。
- `SessionVault`：保存登录态、Cookie 和授权 Token 的加密引用。

这些能力只能用于用户有权访问的数据源。系统不得提供绕过验证码、付费墙、风控或访问控制的功能。

## 2. 采集架构扩展

```text
Collector
  ├── HttpCollector
  ├── RssCollector
  ├── ApiCollector
  └── BrowserCollector
        ├── PlaywrightRuntimeProvider
        ├── ManagedBrowserRuntimeProvider
        ├── SiteAdapterRegistry
        └── ExtractionPipeline
```

### BrowserRuntimeProvider

负责启动或连接浏览器运行时：

- `LOCAL_PLAYWRIGHT`：本地隔离容器运行 Playwright。
- `REMOTE_CDP`：连接外部浏览器的 CDP 地址。
- `MANAGED_PROFILE`：通过外部浏览器管理 API 启动指定 Profile。

接口输入：

- `sourceId`
- `profileId`
- `crawlPolicyId`
- `allowedDomains`
- `credentialRef`

接口输出：

- `sessionId`
- `debugEndpointRef`
- `browserVersion`
- `profileFingerprintRef`
- `startedAt`

### SiteAdapter

站点适配器描述“如何合法采集某个来源”：

- 允许域名和入口 URL。
- 登录态要求和凭据类型。
- 列表页、详情页、分页、滚动和等待策略。
- 内容选择器、排除选择器、发布时间选择器。
- 附件发现规则。
- robots/站点规则处理方式。
- 失败重试、限速和暂停条件。

适配器应尽量声明式配置；必须使用脚本时，只允许服务端审核过的内置动作，不允许用户上传任意 JavaScript。

### ExtractionPipeline

统一输出：

- `rawHtmlRef`
- `screenshotRef`
- `mainText`
- `markdown`
- `metadata`
- `links`
- `attachments`
- `sourceDigest`

输出进入既有 `Preprocess → Deduplicate → Index → Analyze` 流程。

## 3. CrawlPolicy

每个数据源必须绑定采集策略：

- 最大页面数。
- 最大深度。
- 每域名并发数。
- 请求间隔和退避策略。
- 单页面超时。
- 最大响应体大小。
- 是否允许下载附件。
- 是否允许执行页面脚本。
- 是否允许远程浏览器 Profile。

策略由 `ADMIN` 配置，任务运行时固化快照，避免历史任务不可复现。

## 4. 逆向与调试工作台边界

后续可提供面向管理员的“采集调试工作台”：

- 打开授权页面并记录 DOM 快照。
- 选择正文、标题、时间、分页和附件选择器。
- 查看网络请求摘要和响应状态。
- 生成或更新 `SiteAdapter` 草稿。
- 测试抽取结果和 Markdown 质量。

禁止能力：

- 自动破解验证码。
- 绕过付费墙、登录授权、IP 封禁或风控策略。
- 生成规避检测的对抗脚本。
- 执行用户提交的任意 JavaScript、Python、Shell 或 SQL。

## 5. 验收标准

- 授权登录来源可以复用加密登录态采集页面。
- 凭据失效、验证码、403/429、robots 禁止时任务进入可解释失败状态。
- 每个采集结果保留 URL、时间、Profile、策略、适配器版本和内容摘要。
- Browser 任务在隔离容器运行，不能访问内网管理地址。
- 页面内容、模型输出和适配器输出均经过 Schema 校验后才进入工作流。
