<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 class="text-xl font-semibold text-slate-900">Agent 中心</h2>
        <p class="mt-1 text-sm text-slate-500">配置模型、Agent 行为与运行策略</p>
      </div>
      <div class="inline-flex h-10 w-fit rounded-md border border-slate-300 bg-white p-1" role="tablist" aria-label="Agent 中心视图">
        <button
          v-for="item in tabs"
          :key="item.key"
          class="h-8 rounded px-3 text-sm font-medium"
          :class="activeTab === item.key ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100'"
          role="tab"
          :aria-selected="activeTab === item.key"
          type="button"
          @click="activeTab = item.key"
        >
          {{ item.label }}
        </button>
      </div>
    </div>

    <div v-if="pageError" class="border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      {{ pageError }}
    </div>
    <div v-if="loading" class="flex h-48 items-center justify-center border border-slate-200 bg-white text-sm text-slate-500">
      <LoaderCircle class="mr-2 animate-spin" :size="18" aria-hidden="true" />
      正在加载 Agent 配置...
    </div>

    <template v-else-if="agent && modelConfig && agentConfig">
      <template v-if="activeTab === 'configuration'">
        <section class="border border-slate-200 bg-white" aria-labelledby="model-config-title">
          <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 id="model-config-title" class="font-semibold">模型配置</h3>
              <p class="mt-1 text-xs text-slate-500">凭据加密保存，页面不会返回 API Key 明文</p>
            </div>
            <span
              class="inline-flex w-fit items-center gap-2 rounded px-2.5 py-1 text-xs font-medium"
              :class="modelConfig.apiKeyConfigured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'"
            >
              <span class="h-1.5 w-1.5 rounded-full" :class="modelConfig.apiKeyConfigured ? 'bg-emerald-600' : 'bg-amber-600'" />
              {{ modelConfig.apiKeyConfigured ? "已配置" : "未配置" }}
            </span>
          </div>

          <form class="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" @submit.prevent="saveModelConfiguration">
            <label class="block text-sm">
              <span class="font-medium text-slate-700">模型提供方</span>
              <select v-model="modelForm.provider" class="field">
                <option value="DEEPSEEK">DeepSeek</option>
              </select>
            </label>
            <label class="block text-sm">
              <span class="font-medium text-slate-700">模型</span>
              <select v-model="modelForm.model" class="field">
                <option value="deepseek-chat">deepseek-chat</option>
                <option value="deepseek-reasoner">deepseek-reasoner</option>
              </select>
            </label>
            <label class="block text-sm md:col-span-2">
              <span class="font-medium text-slate-700">Base URL</span>
              <input v-model="modelForm.baseUrl" class="field font-mono text-xs" maxlength="500" required type="url">
            </label>
            <label class="block text-sm md:col-span-2 xl:col-span-3">
              <span class="font-medium text-slate-700">API Key</span>
              <div class="relative mt-1">
                <input
                  v-model="modelForm.apiKey"
                  class="h-10 w-full rounded-md border border-slate-300 bg-white px-3 pr-10 font-mono text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                  :placeholder="modelConfig.apiKeyMasked || '输入 DeepSeek API Key'"
                  :type="showApiKey ? 'text' : 'password'"
                  autocomplete="new-password"
                  maxlength="500"
                >
                <button class="absolute right-1 top-1 flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-slate-100" :title="showApiKey ? '隐藏密钥' : '显示密钥'" type="button" @click="showApiKey = !showApiKey">
                  <EyeOff v-if="showApiKey" :size="16" aria-hidden="true" />
                  <Eye v-else :size="16" aria-hidden="true" />
                </button>
              </div>
              <p class="mt-1 text-xs text-slate-400">留空表示保留当前密钥</p>
            </label>
            <div class="flex items-end gap-2">
              <button class="h-10 flex-1 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium hover:bg-slate-50 disabled:opacity-60" :disabled="testingConnection || savingModel || !modelConfig.apiKeyConfigured" type="button" @click="testConnection">
                {{ testingConnection ? "测试中..." : "测试连接" }}
              </button>
              <button class="h-10 flex-1 rounded-md bg-emerald-700 px-3 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60" :disabled="savingModel" type="submit">
                {{ savingModel ? "保存中..." : "保存" }}
              </button>
            </div>
            <p v-if="modelMessage" class="text-sm md:col-span-2 xl:col-span-4" :class="modelMessageKind === 'success' ? 'text-emerald-700' : 'text-red-700'" role="status">
              {{ modelMessage }}
            </p>
          </form>
        </section>

        <section class="border border-slate-200 bg-white" aria-labelledby="agent-config-title">
          <div class="border-b border-slate-200 px-5 py-4">
            <h3 id="agent-config-title" class="font-semibold">Agent 配置</h3>
            <p class="mt-1 text-xs text-slate-500">定义物料监测 Agent 的职责、默认执行模式与工具边界</p>
          </div>
          <form class="grid gap-5 p-5 xl:grid-cols-[minmax(0,1fr)_340px]" @submit.prevent="saveAgentConfiguration">
            <label class="block text-sm">
              <span class="font-medium text-slate-700">系统提示词</span>
              <textarea v-model="agentForm.systemPrompt" class="mt-1 min-h-44 w-full resize-y rounded-md border border-slate-300 bg-white p-3 text-sm leading-6 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100" maxlength="8000" required />
              <span class="mt-1 block text-right text-xs tabular-nums text-slate-400">{{ agentForm.systemPrompt.length }} / 8000</span>
            </label>
            <div class="space-y-5">
              <fieldset>
                <legend class="text-sm font-medium text-slate-700">默认执行模式</legend>
                <div class="mt-2 grid grid-cols-2 rounded-md border border-slate-300 bg-slate-50 p-1">
                  <label v-for="mode in ['TEST', 'LIVE'] as const" :key="mode" class="cursor-pointer">
                    <input v-model="agentForm.defaultExecutionMode" class="sr-only" name="executionMode" type="radio" :value="mode">
                    <span class="flex h-9 items-center justify-center rounded text-sm font-medium" :class="agentForm.defaultExecutionMode === mode ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'">{{ mode }}</span>
                  </label>
                </div>
              </fieldset>
              <fieldset>
                <legend class="text-sm font-medium text-slate-700">工具权限</legend>
                <div class="mt-2 divide-y divide-slate-100 border border-slate-200">
                  <label v-for="tool in agentConfig.availableToolKeys" :key="tool" class="flex cursor-pointer items-center justify-between gap-3 px-3 py-3 text-sm hover:bg-slate-50">
                    <span class="flex min-w-0 items-center gap-2"><Wrench :size="15" class="text-slate-400" /><span class="truncate font-mono text-xs">{{ tool }}</span></span>
                    <input v-model="agentForm.toolKeys" class="h-4 w-4 accent-emerald-700" type="checkbox" :value="tool">
                  </label>
                </div>
              </fieldset>
              <button class="h-10 w-full rounded-md bg-slate-900 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60" :disabled="savingAgent || agentForm.toolKeys.length === 0" type="submit">
                {{ savingAgent ? "保存中..." : "保存 Agent 配置" }}
              </button>
              <p v-if="agentMessage" class="text-sm" :class="agentMessageKind === 'success' ? 'text-emerald-700' : 'text-red-700'" role="status">{{ agentMessage }}</p>
            </div>
          </form>
        </section>
      </template>

      <template v-else>
        <div class="flex justify-end">
          <button class="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60" :disabled="running" type="button" @click="runWorkflow">
            <LoaderCircle v-if="running" class="animate-spin" :size="17" aria-hidden="true" />
            <Play v-else :size="17" aria-hidden="true" />
            {{ running ? "运行中..." : `运行 ${agentConfig.defaultExecutionMode} 工作流` }}
          </button>
        </div>
        <div class="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
          <section class="border border-slate-200 bg-white" aria-labelledby="workflow-title">
            <div class="border-b border-slate-200 px-5 py-4"><h3 id="workflow-title" class="font-semibold">物料监测工作流</h3></div>
            <ol class="divide-y divide-slate-100">
              <li v-for="(node, index) in workflowNodes" :key="node.key" class="flex items-start gap-4 px-5 py-4">
                <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">{{ index + 1 }}</span>
                <div class="min-w-0 flex-1"><div class="flex items-center justify-between gap-3"><p class="font-medium">{{ node.name }}</p><span v-if="latestStep(node.key)" class="text-xs font-medium text-emerald-700">已完成</span></div><p class="mt-1 text-sm text-slate-500">{{ latestStep(node.key)?.detail || node.description }}</p></div>
              </li>
            </ol>
          </section>
          <section class="border border-slate-200 bg-white" aria-labelledby="runtime-title">
            <div class="border-b border-slate-200 px-5 py-4"><h3 id="runtime-title" class="font-semibold">当前运行配置</h3></div>
            <dl class="divide-y divide-slate-100 text-sm">
              <div class="px-5 py-4"><dt class="text-xs text-slate-500">模型</dt><dd class="mt-1 font-mono text-xs">{{ modelConfig.model }}</dd></div>
              <div class="px-5 py-4"><dt class="text-xs text-slate-500">模式</dt><dd class="mt-1 font-medium">{{ agentConfig.defaultExecutionMode }}</dd></div>
              <div class="px-5 py-4"><dt class="text-xs text-slate-500">工具</dt><dd class="mt-2 flex flex-wrap gap-1"><span v-for="tool in agentConfig.toolKeys" :key="tool" class="rounded bg-slate-100 px-2 py-1 font-mono text-xs">{{ tool }}</span></dd></div>
            </dl>
          </section>
        </div>
        <section class="border border-slate-200 bg-white" aria-labelledby="runs-title">
          <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4"><h3 id="runs-title" class="font-semibold">最近运行</h3><span class="text-xs text-slate-500">{{ runs.length }} 条</span></div>
          <div v-if="runs.length === 0" class="flex h-36 items-center justify-center text-sm text-slate-500">尚无运行记录</div>
          <div v-else class="overflow-x-auto"><table class="w-full min-w-[760px] text-left text-sm"><thead class="border-b border-slate-200 bg-slate-50 text-xs text-slate-500"><tr><th class="px-5 py-3">运行 ID</th><th class="px-5 py-3">模式</th><th class="px-5 py-3">状态</th><th class="px-5 py-3">模型调用</th><th class="px-5 py-3">开始时间</th></tr></thead><tbody class="divide-y divide-slate-100"><tr v-for="run in runs" :key="run.id"><td class="px-5 py-3 font-mono text-xs">{{ run.id }}</td><td class="px-5 py-3">{{ run.executionMode }}</td><td class="px-5 py-3"><span class="rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">{{ run.status }}</span></td><td class="px-5 py-3">{{ run.modelInvoked ? "是" : "否" }}</td><td class="px-5 py-3 text-slate-600">{{ formatDateTime(run.startedAt) }}</td></tr></tbody></table></div>
        </section>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Eye, EyeOff, LoaderCircle, Play, Wrench } from "lucide-vue-next"

import type { AgentConfiguration, AgentDefinition, AgentRun, ModelConfiguration, ModelConnectionTest } from "~/types/catalog"

const { request, errorMessage } = useApiClient()
const tabs = [{ key: "configuration", label: "配置" }, { key: "runtime", label: "运行与审计" }] as const
const activeTab = ref<(typeof tabs)[number]["key"]>("configuration")
const agent = ref<AgentDefinition | null>(null)
const modelConfig = ref<ModelConfiguration | null>(null)
const agentConfig = ref<AgentConfiguration | null>(null)
const runs = ref<AgentRun[]>([])
const loading = ref(true)
const running = ref(false)
const savingModel = ref(false)
const savingAgent = ref(false)
const testingConnection = ref(false)
const showApiKey = ref(false)
const pageError = ref("")
const modelMessage = ref("")
const modelMessageKind = ref<"success" | "error">("success")
const agentMessage = ref("")
const agentMessageKind = ref<"success" | "error">("success")
const modelForm = reactive({ provider: "DEEPSEEK", model: "deepseek-chat", baseUrl: "https://api.deepseek.com", apiKey: "" })
const agentForm = reactive({ systemPrompt: "", defaultExecutionMode: "TEST" as "TEST" | "LIVE", toolKeys: [] as string[] })
const workflowNodes = [
  { key: "load_scope", name: "加载监测范围", description: "解析物料范围并形成工作上下文。" },
  { key: "collect_evidence", name: "采集外部证据", description: "执行已授权的来源与证据工具。" },
  { key: "analyze_changes", name: "分析变化", description: "使用所选模型进行结构化分析。" },
  { key: "prepare_outputs", name: "准备下游输出", description: "校验建议与报告输入契约。" },
]
const latestRun = computed(() => runs.value[0] || null)
const latestStep = (key: string) => latestRun.value?.steps.find(step => step.key === key)

function applyForms() {
  if (modelConfig.value) Object.assign(modelForm, { provider: modelConfig.value.provider, model: modelConfig.value.model, baseUrl: modelConfig.value.baseUrl, apiKey: "" })
  if (agentConfig.value) Object.assign(agentForm, { systemPrompt: agentConfig.value.systemPrompt, defaultExecutionMode: agentConfig.value.defaultExecutionMode, toolKeys: [...agentConfig.value.toolKeys] })
}

async function refresh() {
  loading.value = true
  pageError.value = ""
  try {
    const [definitions, modelResult, agentResult, runList] = await Promise.all([
      request<{ data: AgentDefinition[] }>("/api/v1/agents"),
      request<ModelConfiguration>("/api/v1/model-configuration"),
      request<AgentConfiguration>("/api/v1/agents/material-monitor/configuration"),
      request<{ data: AgentRun[] }>("/api/v1/agent-runs"),
    ])
    agent.value = definitions.data[0] || null
    modelConfig.value = modelResult
    agentConfig.value = agentResult
    runs.value = runList.data
    applyForms()
  } catch (caught) {
    pageError.value = errorMessage(caught, "Agent 配置加载失败。")
  } finally {
    loading.value = false
  }
}

async function saveModelConfiguration() {
  savingModel.value = true
  modelMessage.value = ""
  try {
    modelConfig.value = await request<ModelConfiguration>("/api/v1/model-configuration", { method: "PUT", body: { ...modelForm, apiKey: modelForm.apiKey || undefined } })
    modelForm.apiKey = ""
    modelMessageKind.value = "success"
    modelMessage.value = "模型配置已保存。"
  } catch (caught) {
    modelMessageKind.value = "error"
    modelMessage.value = errorMessage(caught, "模型配置保存失败。")
  } finally {
    savingModel.value = false
  }
}

async function testConnection() {
  testingConnection.value = true
  modelMessage.value = ""
  try {
    const result = await request<ModelConnectionTest>("/api/v1/model-configuration/test", { method: "POST" })
    modelMessageKind.value = "success"
    modelMessage.value = `连接成功，${result.model} 响应耗时 ${result.latencyMs} ms。`
  } catch (caught) {
    modelMessageKind.value = "error"
    modelMessage.value = errorMessage(caught, "DeepSeek 连接测试失败。")
  } finally {
    testingConnection.value = false
  }
}

async function saveAgentConfiguration() {
  savingAgent.value = true
  agentMessage.value = ""
  try {
    agentConfig.value = await request<AgentConfiguration>("/api/v1/agents/material-monitor/configuration", { method: "PATCH", body: agentForm })
    applyForms()
    agentMessageKind.value = "success"
    agentMessage.value = "Agent 配置已保存。"
  } catch (caught) {
    agentMessageKind.value = "error"
    agentMessage.value = errorMessage(caught, "Agent 配置保存失败。")
  } finally {
    savingAgent.value = false
  }
}

async function runWorkflow() {
  if (!agentConfig.value) return
  running.value = true
  pageError.value = ""
  try {
    await request<AgentRun>("/api/v1/agents/material-monitor/runs", { method: "POST", body: { executionMode: agentConfig.value.defaultExecutionMode, materialIds: [] } })
    const result = await request<{ data: AgentRun[] }>("/api/v1/agent-runs")
    runs.value = result.data
  } catch (caught) {
    pageError.value = errorMessage(caught, "工作流运行失败。")
  } finally {
    running.value = false
  }
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value))
}

onMounted(refresh)
</script>

<style scoped>
.field {
  @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}
</style>
