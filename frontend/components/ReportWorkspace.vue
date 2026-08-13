<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-emerald-700">Intelligence reports</p>
        <h2 class="mt-1 text-xl font-semibold text-slate-900">报告中心</h2>
        <p class="mt-1 text-sm text-slate-500">日报形成可审核快照，周报和月报仅汇总已审核日报。</p>
      </div>
      <form class="flex flex-wrap items-end gap-2" @submit.prevent="createReport">
        <div class="segmented" aria-label="报告周期">
          <button
            v-for="period in periods"
            :key="period.value"
            class="segment"
            :class="form.reportPeriod === period.value ? 'segment-active' : ''"
            type="button"
            @click="selectPeriod(period.value)"
          >
            {{ period.label }}
          </button>
        </div>
        <label class="field-label">开始日期<input v-model="form.periodStart" class="field" required type="date"></label>
        <label class="field-label">结束日期<input v-model="form.periodEnd" class="field" required type="date" :disabled="form.reportPeriod === 'DAILY'"></label>
        <label class="field-label min-w-52 flex-1">标题<input v-model="form.title" class="field" maxlength="200" required></label>
        <button class="primary-button" :disabled="creating" type="submit">
          <LoaderCircle v-if="creating" class="animate-spin" :size="16" />
          <FilePlus2 v-else :size="16" />
          生成草稿
        </button>
      </form>
    </div>

    <div v-if="missingDates.length" class="border-l-4 border-amber-500 bg-amber-50 px-4 py-3 text-sm text-amber-900" role="alert">
      缺少已审核日报：{{ missingDates.join("、") }}
    </div>
    <p v-if="successMessage" class="border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{{ successMessage }}</p>
    <div v-if="loadError" class="flex items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      <span>{{ loadError }}</span>
      <button class="font-medium underline" type="button" @click="loadReports()">重试</button>
    </div>

    <div class="grid gap-5 xl:grid-cols-[minmax(280px,0.7fr)_minmax(560px,1.3fr)]">
      <section class="border border-slate-200 bg-white">
        <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div><h3 class="font-semibold">报告记录</h3><p class="mt-1 text-xs text-slate-500">{{ reports.length }} 份</p></div>
          <button class="icon-button" title="刷新报告" type="button" @click="loadReports()"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button>
        </div>
        <div v-if="loading" class="empty-state"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载报告...</div>
        <div v-else-if="reports.length === 0" class="empty-state flex-col text-center">
          <FileText :size="30" class="text-slate-300" />
          <p class="mt-3 font-medium text-slate-800">暂无报告</p>
          <p class="mt-1 text-sm text-slate-500">先生成并审核一份日报。</p>
        </div>
        <div v-else class="divide-y divide-slate-100">
          <button
            v-for="item in reports"
            :key="item.id"
            class="w-full px-5 py-4 text-left hover:bg-slate-50"
            :class="selectedId === item.id ? 'bg-emerald-50/60' : ''"
            type="button"
            @click="selectReport(item)"
          >
            <div class="flex items-center justify-between gap-3"><span class="period-badge">{{ periodLabel(item.reportPeriod) }}</span><span :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span></div>
            <p class="mt-3 truncate font-medium text-slate-900">{{ item.title }}</p>
            <p class="mt-1 text-xs text-slate-500">{{ formatDate(item.periodStart) }}<span v-if="item.periodStart !== item.periodEnd"> 至 {{ formatDate(item.periodEnd) }}</span> · v{{ item.currentVersion.version }}</p>
          </button>
        </div>
      </section>

      <section class="border border-slate-200 bg-white">
        <div v-if="!selected" class="empty-state flex-col text-center"><FilePenLine :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">选择报告查看正文</p></div>
        <template v-else>
          <div class="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
            <div>
              <div class="flex items-center gap-2"><span class="period-badge">{{ periodLabel(selected.reportPeriod) }}</span><span :class="statusClass(selected.status)">{{ statusLabel(selected.status) }}</span></div>
              <h3 class="mt-3 font-semibold text-slate-900">{{ selected.title }}</h3>
              <p class="mt-1 text-xs text-slate-500">{{ inputModeLabel(selected.inputMode) }} · {{ selected.inputSnapshotDates.length }} 个日报快照</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button v-if="selected.status === 'DRAFT'" class="secondary-button" :disabled="saving" type="button" @click="saveVersion"><Save :size="16" />保存版本</button>
              <button v-if="selected.status === 'DRAFT'" class="primary-button" :disabled="approving || isDirty" :title="isDirty ? '请先保存当前修改' : '审核通过'" type="button" @click="approveReport"><ShieldCheck :size="16" />审核通过</button>
              <button v-if="selected.status === 'APPROVED'" class="secondary-button" type="button" @click="download('markdown')"><Download :size="16" />Markdown</button>
              <button v-if="selected.status === 'APPROVED'" class="secondary-button" type="button" @click="download('docx')"><Download :size="16" />DOCX</button>
            </div>
          </div>
          <div class="p-5">
            <label class="block text-sm font-medium text-slate-700" for="report-markdown">报告正文</label>
            <textarea id="report-markdown" v-model="editorMarkdown" class="editor" :readonly="selected.status === 'APPROVED'" spellcheck="false" />
            <div class="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
              <span>版本 {{ selected.currentVersion.version }} · {{ selected.currentVersion.changeSource === "MANUAL_EDIT" ? "人工编辑" : "系统草稿" }}</span>
              <span v-if="selected.approvedAt">{{ formatDateTime(selected.approvedAt) }} 审核</span>
            </div>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Download, FilePenLine, FilePlus2, FileText, LoaderCircle, RefreshCw, Save, ShieldCheck } from "lucide-vue-next"
import type { IntelligenceReport } from "~/types/catalog"

type ReportPeriod = IntelligenceReport["reportPeriod"]
type ApiFailure = { data?: { error?: { message?: string; details?: { missingDates?: string[] } } } }

const emit = defineEmits<{ changed: [] }>()
const { apiBase, request, errorMessage } = useApiClient()
const reports = ref<IntelligenceReport[]>([])
const selectedId = ref("")
const editorMarkdown = ref("")
const loading = ref(true)
const creating = ref(false)
const saving = ref(false)
const approving = ref(false)
const loadError = ref("")
const successMessage = ref("")
const missingDates = ref<string[]>([])
const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date())
const form = reactive({ reportPeriod: "DAILY" as ReportPeriod, periodStart: today, periodEnd: today, title: `${today} 每日供应情报` })
const periods = [{ value: "DAILY" as const, label: "日报" }, { value: "WEEKLY" as const, label: "周报" }, { value: "MONTHLY" as const, label: "月报" }]
const selected = computed(() => reports.value.find(item => item.id === selectedId.value) || null)
const isDirty = computed(() => Boolean(selected.value && editorMarkdown.value !== selected.value.currentVersion.markdown))

function selectPeriod(period: ReportPeriod) {
  form.reportPeriod = period
  if (period === "DAILY") form.periodEnd = form.periodStart
  form.title = `${form.periodStart} ${periodLabel(period)}供应情报`
}

async function loadReports(preferredId = selectedId.value) {
  loading.value = true
  loadError.value = ""
  try {
    reports.value = (await request<{ data: IntelligenceReport[] }>("/api/v1/reports", { query: { pageSize: 100 } })).data
    const next = reports.value.find(item => item.id === preferredId) || reports.value[0]
    if (next) selectReport(next)
    else { selectedId.value = ""; editorMarkdown.value = "" }
  } catch (error) {
    loadError.value = errorMessage(error, "报告加载失败。")
  } finally {
    loading.value = false
  }
}

async function createReport() {
  creating.value = true
  loadError.value = ""
  successMessage.value = ""
  missingDates.value = []
  try {
    const result = await request<IntelligenceReport>("/api/v1/reports", { method: "POST", body: form })
    successMessage.value = "报告草稿已生成。"
    await loadReports(result.id)
    emit("changed")
  } catch (error) {
    const failure = error as ApiFailure
    missingDates.value = failure.data?.error?.details?.missingDates || []
    loadError.value = missingDates.value.length ? "" : errorMessage(error, "报告生成失败。")
  } finally {
    creating.value = false
  }
}

async function saveVersion() {
  if (!selected.value || !editorMarkdown.value.trim()) return
  saving.value = true
  loadError.value = ""
  try {
    const updated = await request<IntelligenceReport>(`/api/v1/reports/${selected.value.id}/versions`, { method: "POST", body: { markdown: editorMarkdown.value } })
    replaceReport(updated)
    successMessage.value = `已保存版本 ${updated.currentVersion.version}。`
  } catch (error) {
    loadError.value = errorMessage(error, "报告保存失败。")
  } finally {
    saving.value = false
  }
}

async function approveReport() {
  if (!selected.value) return
  approving.value = true
  loadError.value = ""
  try {
    const updated = await request<IntelligenceReport>(`/api/v1/reports/${selected.value.id}/approve`, { method: "POST" })
    replaceReport(updated)
    successMessage.value = "报告已审核，可下载交付文件。"
    emit("changed")
  } catch (error) {
    loadError.value = errorMessage(error, "报告审核失败。")
  } finally {
    approving.value = false
  }
}

async function download(format: "markdown" | "docx") {
  if (!selected.value) return
  loadError.value = ""
  try {
    const response = await fetch(`${apiBase}/api/v1/reports/${selected.value.id}/exports/${format}`, { credentials: "include" })
    if (!response.ok) throw new Error("Download failed")
    const blobUrl = URL.createObjectURL(await response.blob())
    const link = document.createElement("a")
    link.href = blobUrl
    link.download = `${selected.value.id}.${format === "markdown" ? "md" : "docx"}`
    link.click()
    URL.revokeObjectURL(blobUrl)
  } catch {
    loadError.value = "报告下载失败。"
  }
}

function selectReport(item: IntelligenceReport) { selectedId.value = item.id; editorMarkdown.value = item.currentVersion.markdown; successMessage.value = "" }
function replaceReport(item: IntelligenceReport) { const index = reports.value.findIndex(value => value.id === item.id); if (index >= 0) reports.value[index] = item; selectReport(item) }
function periodLabel(value: ReportPeriod) { return ({ DAILY: "日报", WEEKLY: "周报", MONTHLY: "月报" } as const)[value] }
function statusLabel(value: IntelligenceReport["status"]) { return value === "APPROVED" ? "已审核" : "草稿" }
function statusClass(value: IntelligenceReport["status"]) { return `status-badge ${value === "APPROVED" ? "status-approved" : "status-draft"}` }
function inputModeLabel(value: IntelligenceReport["inputMode"]) { return value === "COLLECT_AND_ANALYZE" ? "当日数据分析" : "已审核日报汇总" }
function formatDate(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeZone: "Asia/Shanghai" }).format(new Date(`${value}T00:00:00+08:00`)) }
function formatDateTime(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value)) }
watch(() => form.periodStart, value => {
  if (form.reportPeriod === "DAILY") form.periodEnd = value
  form.title = `${value} ${periodLabel(form.reportPeriod)}供应情报`
})
onMounted(loadReports)
</script>

<style scoped>
.segmented { @apply flex h-10 overflow-hidden rounded-md border border-slate-300 bg-white; }
.segment { @apply border-r border-slate-300 px-3 text-sm font-medium text-slate-600 last:border-r-0 hover:bg-slate-50; }
.segment-active { @apply bg-emerald-50 text-emerald-800; }
.field-label { @apply text-xs font-medium text-slate-600; }
.field { @apply mt-1 block h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 disabled:bg-slate-100; }
.primary-button { @apply inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50; }
.secondary-button { @apply inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50; }
.icon-button { @apply flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50; }
.empty-state { @apply flex min-h-56 items-center justify-center px-6 text-sm text-slate-500; }
.period-badge { @apply inline-flex rounded bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700; }
.status-badge { @apply inline-flex rounded px-2 py-1 text-xs font-medium; }
.status-approved { @apply bg-emerald-50 text-emerald-700; }
.status-draft { @apply bg-amber-50 text-amber-700; }
.editor { @apply mt-2 min-h-[460px] w-full resize-y rounded-md border border-slate-300 bg-white p-4 font-mono text-sm leading-6 text-slate-800 outline-none focus:border-emerald-600 read-only:bg-slate-50; }
</style>
