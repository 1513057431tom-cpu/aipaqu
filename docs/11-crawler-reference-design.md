# 爬虫与浏览器采集参考设计

本文档参考 `crawl4ai`、AdsPower Local API、GoLogin API 等项目的公开能力，沉淀本项目后续采集增强设计。目标是支持授权、可审计、可恢复的资料采集，以及验证码、付费墙、登录权限等访问挑战的识别、暂停、人工接管和审计，而不是提供自动绕过能力。

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

这些能力只能用于用户有权访问的数据源。系统不得提供自动破解验证码、绕过付费墙、规避风控或越权访问的功能。

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

## 5. 访问挑战处理

验证码、付费墙、二次登录、权限不足和风控页面属于 `AccessChallenge`，由系统检测、记录并交给人工或授权流程处理。

### AccessChallenge 类型

- `CAPTCHA_REQUIRED`：页面要求验证码或人机验证。
- `PAYWALL_REQUIRED`：页面提示订阅、购买或机构授权。
- `LOGIN_REQUIRED`：登录态失效或需要重新登录。
- `MFA_REQUIRED`：需要短信、邮箱、TOTP、硬件密钥等二次验证。
- `FORBIDDEN`：HTTP 403 或页面提示无访问权限。
- `RATE_LIMITED`：HTTP 429 或来源明确限流。
- `ROBOTS_DISALLOWED`：robots 或站点规则禁止采集。

### 处理策略

- 自动采集任务遇到挑战后必须暂停，不得自行尝试绕过。
- 系统保存截图、DOM 摘要、URL、状态码、Profile、适配器版本和策略快照。
- `ADMIN` 或具备授权的 `EDITOR` 可以打开人工接管会话，在受控浏览器中完成登录、订阅确认或验证码输入。
- 人工接管完成后，系统只保存新的授权状态引用和审计记录，不保存验证码答案或二次验证一次性密码。
- 对付费来源，必须记录 `AccessGrant`：授权主体、来源、用途、有效期、许可说明和确认人。
- 无法确认授权时，任务进入 `FAILED_FINAL` 或 `WAITING_HUMAN`，报告中不得引用该来源。

### ManualVerificationSession

人工接管会话必须满足：

- 会话短期有效，超时自动关闭。
- 仅允许访问当前数据源的白名单域名。
- 操作过程记录审计事件，但不记录密码、验证码和一次性 Token 明文。
- 完成后触发一次受限重试，从失败节点继续。

## 6. 验收标准

- 授权登录来源可以复用加密登录态采集页面。
- 凭据失效、验证码、403/429、robots 禁止时任务进入可解释失败状态。
- 付费来源必须绑定有效 `AccessGrant` 才能进入自动采集。
- 人工接管会话可以完成合法登录或授权确认，但不会保存验证码答案、MFA 一次性密码或绕过脚本。
- 每个采集结果保留 URL、时间、Profile、策略、适配器版本和内容摘要。
- Browser 任务在隔离容器运行，不能访问内网管理地址。
- 页面内容、模型输出和适配器输出均经过 Schema 校验后才进入工作流。
