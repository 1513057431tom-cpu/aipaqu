<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-xl font-semibold text-slate-900">Agent 中心</h2>
        <p class="mt-1 text-sm text-slate-500">管理模型能力、工作流节点和运行审计</p>
      </div>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
        :disabled="running || loading"
        type="button"
        @click="runTest"
      >
        <LoaderCircle v-if="running" class="animate-spin" :size="17" aria-hidden="true" />
        <Play v-else :size="17" aria-hidden="true" />
        {{ running ? "运行中..." : "测试工作流" }}
      </button>
    </div>

    <div v-if="error" class="border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      {{ error }}
    </div>

    <div v-if="loading" class="flex h-48 items-center justify-center border border-slate-200 bg-white text-sm text-slate-500">
      <LoaderCircle class="mr-2 animate-spin" :size="18" aria-hidden="true" />
      正在加载 Agent 配置...
    </div>

    <template v-else-if="agent">
      <section class="border border-slate-200 bg-white" aria-labelledby="agent-overview-title">
        <div class="flex flex-col gap-4 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div class="flex min-w-0 items-center gap-3">
            <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">
              <Bot :size="21" aria-hidden="true" />
            </span>
            <div class="min-w-0">
              <h3 id="agent-overview-title" class="truncate font-semibold text-slate-900">{{ agent.name }}</h3>
              <p class="mt-1 text-sm text-slate-500">{{ agent.description }}</p>
            </div>
          </div>
          <span
            class="inline-flex w-fit items-center gap-2 rounded px-2.5 py-1 text-xs font-medium"
            :class="agent.modelConfigured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="agent.modelConfigured ? 'bg-emerald-600' : 'bg-amber-600'" />
            {{ agent.modelConfigured ? "DeepSeek 已配置" : "DeepSeek 未配置" }}
          </span>
        </div>
        <dl class="grid divide-y divide-slate-100 text-sm sm:grid-cols-2 sm:divide-x sm:divide-y-0 xl:grid-cols-4">
          <div class="px-5 py-4"><dt class="text-xs text-slate-500">模型提供方</dt><dd class="mt-1 font-medium">{{ agent.provider }}</dd></div>
          <div class="px-5 py-4"><dt class="text-xs text-slate-500">模型</dt><dd class="mt-1 font-mono text-xs">{{ agent.model }}</dd></div>
          <div class="px-5 py-4"><dt class="text-xs text-slate-500">工作流版本</dt><dd class="mt-1 font-medium">v{{ agent.workflowVersion }}</dd></div>
          <div class="px-5 py-4"><dt class="text-xs text-slate-500">执行策略</dt><dd class="mt-1 font-medium">人工可审计</dd></div>
        </dl>
      </section>

      <div class="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
        <section class="border border-slate-200 bg-white" aria-labelledby="workflow-title">
          <div class="border-b border-slate-200 px-5 py-4">
            <h3 id="workflow-title" class="font-semibold">物料监测工作流</h3>
          </div>
          <ol class="divide-y divide-slate-100">
            <li v-for="(node, index) in workflowNodes" :key="node.key" class="flex items-start gap-4 px-5 py-4">
              <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600">{{ index + 1 }}</span>
              <div class="min-w-0 flex-1">
                <div class="flex items-center justify-between gap-3">
                  <p class="font-medium text-slate-900">{{ node.name }}</p>
                  <span v-if="latestStep(node.key)" class="text-xs font-medium text-emerald-700">已完成</span>
                </div>
                <p class="mt-1 text-sm text-slate-500">{{ latestStep(node.key)?.detail || node.description }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section class="border border-slate-200 bg-white" aria-labelledby="tools-title">
          <div class="border-b border-slate-200 px-5 py-4">
            <h3 id="tools-title" class="font-semibold">允许使用的工具</h3>
          </div>
          <ul class="divide-y divide-slate-100">
            <li v-for="tool in agent.toolKeys" :key="tool" class="flex items-center gap-3 px-5 py-4 text-sm">
              <Wrench :size="16" class="text-slate-400" aria-hidden="true" />
              <span class="font-mono text-xs text-slate-700">{{ tool }}</span>
            </li>
          </ul>
          <div v-if="!agent.modelConfigured" class="border-t border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-900">
            TEST 模式可验证编排；LIVE 模式需在后端配置 <code class="font-mono text-xs">DEEPSEEK_API_KEY</code>。
          </div>
        </section>
      </div>

      <section class="border border-slate-200 bg-white" aria-labelledby="runs-title">
        <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h3 id="runs-title" class="font-semibold">最近运行</h3>
          <span class="text-xs text-slate-500">{{ runs.length }} 条</span>
        </div>
        <div v-if="runs.length === 0" class="flex h-36 items-center justify-center text-sm text-slate-500">尚无运行记录</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full min-w-[760px] text-left text-sm">
            <thead class="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
              <tr><th class="px-5 py-3">运行 ID</th><th class="px-5 py-3">模式</th><th class="px-5 py-3">状态</th><th class="px-5 py-3">模型调用</th><th class="px-5 py-3">开始时间</th></tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="run in runs" :key="run.id">
                <td class="px-5 py-3 font-mono text-xs">{{ run.id }}</td>
                <td class="px-5 py-3">{{ run.executionMode }}</td>
                <td class="px-5 py-3"><span class="rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">{{ run.status }}</span></td>
                <td class="px-5 py-3">{{ run.modelInvoked ? "是" : "否" }}</td>
                <td class="px-5 py-3 text-slate-600">{{ formatDateTime(run.startedAt) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Bot, LoaderCircle, Play, Wrench } from "lucide-vue-next"

import type { AgentDefinition, AgentRun } from "~/types/catalog"

const { request, errorMessage } = useApiClient()
const agent = ref<AgentDefinition | null>(null)
const runs = ref<AgentRun[]>([])
const loading = ref(true)
const running = ref(false)
const error = ref("")
const workflowNodes = [
  { key: "load_scope", name: "加载监测范围", description: "解析物料分组或指定物料，形成工作上下文。" },
  { key: "collect_evidence", name: "采集外部证据", description: "保留采集器接入节点；当前版本尚未在工作流内触发网络采集。" },
  { key: "analyze_changes", name: "分析变化", description: "通过 DeepSeek 结构化识别价格、规格、交期等变化。" },
  { key: "prepare_outputs", name: "准备下游输出", description: "校验建议与报告输入契约，当前版本不自动写入业务结果。" },
]

const latestRun = computed(() => runs.value[0] || null)
const latestStep = (key: string) => latestRun.value?.steps.find(step => step.key === key)

async function refresh() {
  loading.value = true
  error.value = ""
  try {
    const [definitions, runList] = await Promise.all([
      request<{ data: AgentDefinition[] }>("/api/v1/agents"),
      request<{ data: AgentRun[] }>("/api/v1/agent-runs"),
    ])
    agent.value = definitions.data[0] || null
    runs.value = runList.data
  } catch (caught) {
    error.value = errorMessage(caught, "Agent 配置加载失败。")
  } finally {
    loading.value = false
  }
}

async function runTest() {
  running.value = true
  error.value = ""
  try {
    await request<AgentRun>("/api/v1/agents/material-monitor/runs", {
      method: "POST",
      body: { executionMode: "TEST", materialIds: [] },
    })
    await refresh()
  } catch (caught) {
    error.value = errorMessage(caught, "工作流测试运行失败。")
  } finally {
    running.value = false
  }
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "medium" }).format(new Date(value))
}

onMounted(refresh)
</script>
