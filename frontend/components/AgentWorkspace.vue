<template>
  <div class="space-y-5">
    <header class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h2 class="text-xl font-semibold text-slate-900">智能体中心</h2>
        <p class="mt-1 text-sm text-slate-500">编排采集、情报分析、采购解释和报告撰写能力</p>
      </div>
      <div class="inline-flex w-fit rounded-md border border-slate-300 bg-white p-1" role="tablist" aria-label="智能体中心视图">
        <button v-for="item in tabs" :key="item.key" class="h-8 rounded px-3 text-sm font-medium" :class="activeTab === item.key ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'" type="button" @click="activeTab = item.key">
          {{ item.label }}
        </button>
      </div>
    </header>

    <div v-if="pageError" class="border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{{ pageError }}</div>
    <div v-if="loading" class="flex h-48 items-center justify-center border border-slate-200 bg-white text-sm text-slate-500"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载智能体...</div>

    <template v-else>
      <section v-if="activeTab === 'orchestration'" class="border border-slate-200 bg-white">
        <div class="border-b border-slate-200 px-5 py-4">
          <h3 class="font-semibold text-slate-900">物料情报工作流</h3>
          <p class="mt-1 text-xs text-slate-500">监测编排智能体负责调度，专业智能体只处理各自的受限任务</p>
        </div>
        <div class="overflow-x-auto px-5 py-6">
          <ol class="grid min-w-[900px] grid-cols-5 gap-0">
            <li v-for="(item, index) in agents" :key="item.key" class="relative pr-6 last:pr-0">
              <div v-if="index < agents.length - 1" class="absolute left-[calc(100%-24px)] top-5 h-px w-6 bg-slate-300" />
              <button class="w-full border px-4 py-4 text-left transition-colors" :class="selectedKey === item.key ? 'border-emerald-600 bg-emerald-50' : 'border-slate-200 hover:bg-slate-50'" type="button" @click="selectAgent(item.key)">
                <span class="text-xs font-semibold text-emerald-700">步骤 {{ index + 1 }}</span>
                <span class="mt-2 block text-sm font-semibold text-slate-900">{{ item.name }}</span>
                <span class="mt-2 block text-xs leading-5 text-slate-500">{{ item.description }}</span>
              </button>
            </li>
          </ol>
        </div>
        <div class="grid border-t border-slate-200 lg:grid-cols-[260px_minmax(0,1fr)]">
          <nav class="border-b border-slate-200 lg:border-b-0 lg:border-r">
            <button v-for="item in agents" :key="item.key" class="flex w-full items-center gap-3 border-b border-slate-100 px-4 py-3 text-left text-sm last:border-b-0" :class="selectedKey === item.key ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-50'" type="button" @click="selectAgent(item.key)">
              <Bot :size="17" /><span>{{ item.name }}</span>
            </button>
          </nav>
          <div v-if="selectedAgent" class="p-5">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div><h4 class="font-semibold text-slate-900">{{ selectedAgent.name }}</h4><p class="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{{ selectedAgent.description }}</p></div>
              <span class="w-fit rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-600">流程版本 {{ selectedAgent.workflowVersion }}</span>
            </div>
            <dl class="mt-5 grid gap-px bg-slate-200 sm:grid-cols-3">
              <div class="bg-white p-4"><dt class="text-xs text-slate-500">职责输入</dt><dd class="mt-1 text-sm font-medium">{{ roleInput(selectedAgent.key) }}</dd></div>
              <div class="bg-white p-4"><dt class="text-xs text-slate-500">结构化输出</dt><dd class="mt-1 text-sm font-medium">{{ roleOutput(selectedAgent.key) }}</dd></div>
              <div class="bg-white p-4"><dt class="text-xs text-slate-500">人工关口</dt><dd class="mt-1 text-sm font-medium">{{ roleGate(selectedAgent.key) }}</dd></div>
            </dl>
          </div>
        </div>
      </section>

      <div v-else-if="activeTab === 'configuration'" class="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <section class="border border-slate-200 bg-white">
          <div class="border-b border-slate-200 px-4 py-4"><h3 class="font-semibold">模型与智能体</h3></div>
          <button v-for="item in agents" :key="item.key" class="flex w-full items-center justify-between border-b border-slate-100 px-4 py-3 text-left text-sm last:border-b-0" :class="selectedKey === item.key ? 'bg-emerald-50 text-emerald-900' : 'hover:bg-slate-50'" type="button" @click="selectAgent(item.key)"><span>{{ item.name }}</span><ChevronRight :size="16" /></button>
        </section>
        <div class="space-y-5">
          <section v-if="modelConfig" class="border border-slate-200 bg-white">
            <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h3 class="font-semibold">共享模型连接</h3><p class="mt-1 text-xs text-slate-500">所有智能体共享 DeepSeek 连接，每个智能体保留独立任务规则</p></div><span class="rounded px-2 py-1 text-xs" :class="modelConfig.apiKeyConfigured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'">{{ modelConfig.apiKeyConfigured ? '已配置' : '未配置' }}</span></div>
            <form class="grid gap-4 p-5 md:grid-cols-2" @submit.prevent="saveModelConfiguration">
              <label class="text-sm"><span class="field-label">模型</span><select v-model="modelForm.model" class="field"><option value="deepseek-chat">DeepSeek 对话模型</option><option value="deepseek-reasoner">DeepSeek 推理模型</option></select></label>
              <label class="text-sm"><span class="field-label">接口地址</span><input v-model="modelForm.baseUrl" class="field" type="url" required></label>
              <label class="text-sm md:col-span-2"><span class="field-label">接口密钥</span><div class="relative"><input v-model="modelForm.apiKey" class="field pr-10 font-mono" :placeholder="modelConfig.apiKeyMasked || '输入接口密钥'" :type="showApiKey ? 'text' : 'password'"><button class="absolute right-1 top-2 flex h-8 w-8 items-center justify-center text-slate-500" :title="showApiKey ? '隐藏密钥' : '显示密钥'" type="button" @click="showApiKey = !showApiKey"><EyeOff v-if="showApiKey" :size="16" /><Eye v-else :size="16" /></button></div></label>
              <div class="flex gap-2 md:col-span-2"><button class="secondary-button" :disabled="testingConnection || !modelConfig.apiKeyConfigured" type="button" @click="testConnection">测试连接</button><button class="primary-button" :disabled="savingModel" type="submit">保存模型</button><span v-if="modelMessage" class="self-center text-sm" :class="modelMessageKind === 'success' ? 'text-emerald-700' : 'text-red-700'">{{ modelMessage }}</span></div>
            </form>
          </section>
          <section v-if="selectedAgent && agentConfig" class="border border-slate-200 bg-white">
            <div class="border-b border-slate-200 px-5 py-4"><h3 class="font-semibold">{{ selectedAgent.name }}</h3><p class="mt-1 text-xs text-slate-500">配置职责约束、工具边界和默认执行模式，不是简单聊天提示词</p></div>
            <form class="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_340px]" @submit.prevent="saveAgentConfiguration">
              <label class="text-sm"><span class="field-label">任务规则与安全边界</span><textarea v-model="agentForm.systemPrompt" class="textarea" maxlength="8000" required /><span class="mt-1 block text-right text-xs text-slate-400">{{ agentForm.systemPrompt.length }} / 8000</span></label>
              <div class="space-y-4">
                <fieldset><legend class="field-label text-sm">默认执行模式</legend><div class="mt-2 grid grid-cols-2 rounded-md border border-slate-300 bg-slate-50 p-1"><label v-for="mode in ['TEST', 'LIVE'] as const" :key="mode" class="cursor-pointer"><input v-model="agentForm.defaultExecutionMode" class="sr-only" type="radio" :value="mode"><span class="flex h-9 items-center justify-center rounded text-sm" :class="agentForm.defaultExecutionMode === mode ? 'bg-white font-medium shadow-sm' : 'text-slate-500'">{{ executionModeLabel(mode) }}</span></label></div></fieldset>
                <fieldset><legend class="field-label text-sm">工具权限</legend><label v-for="tool in agentConfig.availableToolKeys" :key="tool" class="mt-2 flex items-start justify-between gap-3 border border-slate-200 p-3 text-sm"><span><span class="font-medium">{{ toolLabel(tool) }}</span><span class="mt-1 block text-xs leading-5 text-slate-500">{{ toolDescription(tool) }}</span></span><input v-model="agentForm.toolKeys" class="mt-1 h-4 w-4 accent-emerald-700" type="checkbox" :value="tool"></label></fieldset>
                <button class="primary-button w-full" :disabled="savingAgent || !agentForm.toolKeys.length" type="submit">保存智能体配置</button>
                <p v-if="agentMessage" class="text-sm" :class="agentMessageKind === 'success' ? 'text-emerald-700' : 'text-red-700'">{{ agentMessage }}</p>
              </div>
            </form>
          </section>
        </div>
      </div>

      <section v-else-if="activeTab === 'templates'" class="border border-slate-200 bg-white">
        <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><h3 class="font-semibold">报告模板</h3><p class="mt-1 text-xs text-slate-500">日报直接使用当日情报；周报和月报聚合对应日期内已生成的日报快照</p></div><div class="inline-flex rounded-md border border-slate-300 p-1"><button v-for="item in templates" :key="item.period" class="h-8 rounded px-3 text-sm" :class="templatePeriod === item.period ? 'bg-slate-900 text-white' : 'text-slate-600'" type="button" @click="templatePeriod = item.period">{{ periodLabel(item.period) }}</button></div></div>
        <form v-if="activeTemplate" class="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_300px]" @submit.prevent="saveTemplate">
          <div class="space-y-4"><label class="text-sm"><span class="field-label">模板名称</span><input v-model="templateForm.name" class="field" maxlength="100" required></label><label class="text-sm"><span class="field-label">Markdown 模板内容</span><textarea v-model="templateForm.content" class="textarea min-h-[420px] font-mono text-xs" maxlength="30000" required /></label></div>
          <aside><h4 class="text-sm font-semibold text-slate-800">可用内容块</h4><div class="mt-3 divide-y divide-slate-100 border border-slate-200"><button v-for="variable in templateVariables" :key="variable.key" class="w-full px-3 py-3 text-left hover:bg-slate-50" type="button" @click="insertVariable(variable.key)"><code class="text-xs text-emerald-700">{{ variable.key }}</code><span class="mt-1 block text-xs text-slate-500">{{ variable.label }}</span></button></div><button class="primary-button mt-4 w-full" :disabled="savingTemplate" type="submit">保存{{ periodLabel(templatePeriod) }}模板</button><p v-if="templateMessage" class="mt-3 text-sm" :class="templateMessageKind === 'success' ? 'text-emerald-700' : 'text-red-700'">{{ templateMessage }}</p></aside>
        </form>
      </section>

      <section v-else class="border border-slate-200 bg-white">
        <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"><div><h3 class="font-semibold">执行记录</h3><p class="mt-1 text-xs text-slate-500">用于定位某次任务调用了哪些节点、模型和工具；真实业务由外部监控、采购建议和报告页面触发</p></div><button class="primary-button" :disabled="running" type="button" @click="runWorkflow"><Play :size="16" />{{ running ? '验证中...' : '验证编排配置' }}</button></div>
        <div v-if="!runs.length" class="flex h-40 items-center justify-center text-sm text-slate-500">尚无执行记录</div>
        <div v-else class="overflow-x-auto"><table class="w-full min-w-[760px] text-left text-sm"><thead class="bg-slate-50 text-xs text-slate-500"><tr><th class="px-5 py-3">执行编号</th><th class="px-5 py-3">模式</th><th class="px-5 py-3">状态</th><th class="px-5 py-3">模型调用</th><th class="px-5 py-3">摘要</th><th class="px-5 py-3">时间</th></tr></thead><tbody class="divide-y divide-slate-100"><tr v-for="run in runs" :key="run.id"><td class="px-5 py-3 font-mono text-xs">{{ run.id }}</td><td class="px-5 py-3">{{ executionModeLabel(run.executionMode) }}</td><td class="px-5 py-3">{{ runStatusLabel(run.status) }}</td><td class="px-5 py-3">{{ run.modelInvoked ? '是' : '否' }}</td><td class="max-w-sm truncate px-5 py-3 text-slate-600">{{ run.summary || run.errorMessage || '-' }}</td><td class="px-5 py-3 text-slate-500">{{ formatDateTime(run.startedAt) }}</td></tr></tbody></table></div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Bot, ChevronRight, Eye, EyeOff, LoaderCircle, Play } from "lucide-vue-next"
import type { AgentConfiguration, AgentDefinition, AgentRun, ModelConfiguration, ModelConnectionTest, ReportTemplate } from "~/types/catalog"

const { request, errorMessage } = useApiClient()
const tabs = [{ key: "orchestration", label: "智能体编排" }, { key: "configuration", label: "模型与工具" }, { key: "templates", label: "报告模板" }, { key: "runs", label: "执行记录" }] as const
const activeTab = ref<(typeof tabs)[number]["key"]>("orchestration")
const agents = ref<AgentDefinition[]>([])
const selectedKey = ref("material-monitor")
const modelConfig = ref<ModelConfiguration | null>(null)
const agentConfig = ref<AgentConfiguration | null>(null)
const templates = ref<ReportTemplate[]>([])
const templatePeriod = ref<ReportTemplate["period"]>("DAILY")
const runs = ref<AgentRun[]>([])
const loading = ref(true)
const pageError = ref("")
const showApiKey = ref(false)
const savingModel = ref(false)
const testingConnection = ref(false)
const savingAgent = ref(false)
const savingTemplate = ref(false)
const running = ref(false)
const modelMessage = ref("")
const modelMessageKind = ref<"success" | "error">("success")
const agentMessage = ref("")
const agentMessageKind = ref<"success" | "error">("success")
const templateMessage = ref("")
const templateMessageKind = ref<"success" | "error">("success")
const modelForm = reactive({ provider: "DEEPSEEK", model: "deepseek-chat", baseUrl: "https://api.deepseek.com", apiKey: "" })
const agentForm = reactive({ systemPrompt: "", defaultExecutionMode: "TEST" as "TEST" | "LIVE", toolKeys: [] as string[] })
const templateForm = reactive({ name: "", content: "" })
const selectedAgent = computed(() => agents.value.find(item => item.key === selectedKey.value) || null)
const activeTemplate = computed(() => templates.value.find(item => item.period === templatePeriod.value) || null)
const templateVariables = [{ key: "{{title}}", label: "报告标题" }, { key: "{{highlights}}", label: "重点摘要" }, { key: "{{material_intelligence}}", label: "按物料组织的情报" }, { key: "{{recommendations}}", label: "采购建议与依据" }, { key: "{{evidence}}", label: "证据引用" }]
const toolPresentations: Record<string, { label: string; description: string }> = {
  material_catalog: { label: "物料主数据", description: "读取物料编码、规格与分组" }, monitoring_sources: { label: "外部监控来源", description: "读取网站、监测范围和导航目标" }, evidence_store: { label: "证据库", description: "保存和读取网页证据快照" }, browser_navigation: { label: "智能浏览器", description: "执行站内搜索、标签、分页和详情导航" }, internal_operations: { label: "内部经营数据", description: "读取库存、需求、消耗和在途数据" }, procurement_rules: { label: "采购规则引擎", description: "调用确定性数量与日期计算" }, report_templates: { label: "报告模板", description: "读取日报、周报和月报结构" },
}

watch(activeTemplate, value => { if (value) Object.assign(templateForm, { name: value.name, content: value.content }) }, { immediate: true })
function roleInput(key: string) { return ({ "material-monitor": "物料范围与任务目标", "web-navigator": "页面结构与物料检索词", "intelligence-analyst": "新旧证据与物料上下文", "procurement-advisor": "库存计算与已确认情报", "report-writer": "日报快照、建议与模板" } as Record<string, string>)[key] }
function roleOutput(key: string) { return ({ "material-monitor": "节点执行计划", "web-navigator": "受限页面动作与证据", "intelligence-analyst": "结构化物料变化", "procurement-advisor": "建议解释与风险依据", "report-writer": "带引用的报告草稿" } as Record<string, string>)[key] }
function roleGate(key: string) { return ({ "material-monitor": "正式运行确认", "web-navigator": "访问挑战转人工", "intelligence-analyst": "情报确认或忽略", "procurement-advisor": "批准、调整或驳回", "report-writer": "报告审核发布" } as Record<string, string>)[key] }
function toolLabel(key: string) { return toolPresentations[key]?.label || key }
function toolDescription(key: string) { return toolPresentations[key]?.description || "扩展工具" }
function executionModeLabel(value: "TEST" | "LIVE") { return value === "TEST" ? "测试模式" : "正式运行" }
function runStatusLabel(value: AgentRun["status"]) { return ({ RUNNING: "执行中", COMPLETED: "已完成", FAILED: "失败" } as const)[value] }
function periodLabel(value: ReportTemplate["period"]) { return ({ DAILY: "日报", WEEKLY: "周报", MONTHLY: "月报" } as const)[value] }
function formatDateTime(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value)) }

async function selectAgent(key: string) { selectedKey.value = key; agentMessage.value = ""; try { agentConfig.value = await request<AgentConfiguration>(`/api/v1/agents/${key}/configuration`); Object.assign(agentForm, { systemPrompt: agentConfig.value.systemPrompt, defaultExecutionMode: agentConfig.value.defaultExecutionMode, toolKeys: [...agentConfig.value.toolKeys] }) } catch (error) { pageError.value = errorMessage(error, "智能体配置加载失败。") } }
async function refresh() { loading.value = true; pageError.value = ""; try { const [definitionResult, modelResult, templateResult, runResult] = await Promise.all([request<{ data: AgentDefinition[] }>("/api/v1/agents"), request<ModelConfiguration>("/api/v1/model-configuration"), request<{ data: ReportTemplate[] }>("/api/v1/report-templates"), request<{ data: AgentRun[] }>("/api/v1/agent-runs")]); agents.value = definitionResult.data; modelConfig.value = modelResult; templates.value = templateResult.data; runs.value = runResult.data; Object.assign(modelForm, { provider: modelResult.provider, model: modelResult.model, baseUrl: modelResult.baseUrl, apiKey: "" }); await selectAgent(selectedKey.value) } catch (error) { pageError.value = errorMessage(error, "智能体中心加载失败。") } finally { loading.value = false } }
async function saveModelConfiguration() { savingModel.value = true; modelMessage.value = ""; try { modelConfig.value = await request<ModelConfiguration>("/api/v1/model-configuration", { method: "PUT", body: { ...modelForm, apiKey: modelForm.apiKey || undefined } }); modelForm.apiKey = ""; modelMessageKind.value = "success"; modelMessage.value = "模型连接已保存。" } catch (error) { modelMessageKind.value = "error"; modelMessage.value = errorMessage(error, "模型保存失败。") } finally { savingModel.value = false } }
async function testConnection() { testingConnection.value = true; modelMessage.value = ""; try { const result = await request<ModelConnectionTest>("/api/v1/model-configuration/test", { method: "POST" }); modelMessageKind.value = "success"; modelMessage.value = `连接成功，耗时 ${result.latencyMs} 毫秒。` } catch (error) { modelMessageKind.value = "error"; modelMessage.value = errorMessage(error, "连接测试失败。") } finally { testingConnection.value = false } }
async function saveAgentConfiguration() { savingAgent.value = true; agentMessage.value = ""; try { agentConfig.value = await request<AgentConfiguration>(`/api/v1/agents/${selectedKey.value}/configuration`, { method: "PATCH", body: agentForm }); agentMessageKind.value = "success"; agentMessage.value = "智能体职责与工具边界已保存。" } catch (error) { agentMessageKind.value = "error"; agentMessage.value = errorMessage(error, "智能体配置保存失败。") } finally { savingAgent.value = false } }
async function saveTemplate() { savingTemplate.value = true; templateMessage.value = ""; try { const saved = await request<ReportTemplate>(`/api/v1/report-templates/${templatePeriod.value}`, { method: "PUT", body: templateForm }); const index = templates.value.findIndex(item => item.period === saved.period); if (index >= 0) templates.value[index] = saved; templateMessageKind.value = "success"; templateMessage.value = "模板已保存，后续报告草稿会使用该版本。" } catch (error) { templateMessageKind.value = "error"; templateMessage.value = errorMessage(error, "模板保存失败。") } finally { savingTemplate.value = false } }
function insertVariable(key: string) { templateForm.content = `${templateForm.content.trimEnd()}\n\n${key}` }
async function runWorkflow() { running.value = true; pageError.value = ""; try { await request<AgentRun>("/api/v1/agents/material-monitor/runs", { method: "POST", body: { executionMode: "TEST", materialIds: [] } }); runs.value = (await request<{ data: AgentRun[] }>("/api/v1/agent-runs")).data } catch (error) { pageError.value = errorMessage(error, "编排配置验证失败。") } finally { running.value = false } }
onMounted(refresh)
</script>

<style scoped>
.field { @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100; }
.field-label { @apply font-medium text-slate-700; }
.textarea { @apply mt-1 min-h-52 w-full resize-y rounded-md border border-slate-300 bg-white p-3 text-sm leading-6 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100; }
.primary-button { @apply inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50; }
.secondary-button { @apply inline-flex h-10 items-center justify-center rounded-md border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50; }
</style>
