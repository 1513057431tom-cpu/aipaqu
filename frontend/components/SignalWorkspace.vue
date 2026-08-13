<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-emerald-700">External signals</p>
        <h2 class="mt-1 text-xl font-semibold text-slate-900">情报信号</h2>
        <p class="mt-1 text-sm text-slate-500">对比网页变化并回到原始证据，当前信号默认等待人工确认</p>
      </div>
      <button class="icon-button" title="刷新信号" type="button" @click="loadSignals"><RefreshCw :size="17" :class="loading ? 'animate-spin' : ''" /></button>
    </div>

    <div v-if="loadError" class="flex items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert"><span>{{ loadError }}</span><button class="font-medium underline" type="button" @click="loadSignals">重试</button></div>

    <div class="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(420px,1.1fr)]">
      <section class="border border-slate-200 bg-white">
        <div class="border-b border-slate-200 px-5 py-4"><h3 class="font-semibold">变化列表</h3><p class="mt-1 text-xs text-slate-500">{{ signals.length }} 条待追溯信号</p></div>
        <div v-if="loading" class="empty-state"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载信号...</div>
        <div v-else-if="signals.length === 0" class="empty-state flex-col text-center"><Activity :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">暂无变化信号</p><p class="mt-1 text-sm text-slate-500">来源第二次及后续采集发生内容变化时会生成信号。</p></div>
        <div v-else class="divide-y divide-slate-100">
          <button v-for="signal in signals" :key="signal.id" class="w-full px-5 py-4 text-left hover:bg-slate-50" :class="selectedId === signal.id ? 'bg-emerald-50/60' : ''" type="button" @click="selectSignal(signal)">
            <div class="flex items-center justify-between gap-3"><span class="type-chip">{{ signalTypeLabel(signal.signalType) }}</span><span class="status" :class="statusClass(signal.reviewStatus)">{{ reviewStatusLabel(signal.reviewStatus) }}</span></div>
            <p class="mt-3 line-clamp-2 text-sm font-medium text-slate-900">{{ signal.currentValue }}</p>
            <div class="mt-2 flex items-center justify-between gap-3 text-xs text-slate-400"><span>{{ sourceName(signal.sourceId) }}</span><span>{{ formatDate(signal.observedAt) }}</span></div>
          </button>
        </div>
      </section>

      <section class="border border-slate-200 bg-white">
        <div v-if="!selectedSignal" class="empty-state flex-col text-center"><FileSearch :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">选择一条信号查看差异</p></div>
        <template v-else>
          <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
            <div><div class="flex items-center gap-2"><span class="type-chip">{{ signalTypeLabel(selectedSignal.signalType) }}</span><span class="status" :class="statusClass(selectedSignal.reviewStatus)">{{ reviewStatusLabel(selectedSignal.reviewStatus) }}</span></div><h3 class="mt-3 font-semibold text-slate-900">{{ sourceName(selectedSignal.sourceId) }}</h3><p class="mt-1 text-xs text-slate-500">观测于 {{ formatDate(selectedSignal.observedAt) }} · 置信度 {{ Math.round(selectedSignal.confidence * 100) }}%</p></div>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <button v-if="selectedSignal.reviewStatus !== 'CONFIRMED'" class="review-button confirm-button" :disabled="Boolean(reviewing)" type="button" @click="reviewSignal('CONFIRMED')"><LoaderCircle v-if="reviewing === 'CONFIRMED'" class="animate-spin" :size="15" /><Check v-else :size="15" />确认</button>
              <button v-if="selectedSignal.reviewStatus !== 'DISMISSED'" class="review-button dismiss-button" :disabled="Boolean(reviewing)" type="button" @click="reviewSignal('DISMISSED')"><LoaderCircle v-if="reviewing === 'DISMISSED'" class="animate-spin" :size="15" /><X v-else :size="15" />忽略</button>
              <button class="secondary-button" :disabled="evidenceLoading" type="button" @click="loadEvidence(selectedSignal.documentId)"><LoaderCircle v-if="evidenceLoading" class="animate-spin" :size="15" /><FileSearch v-else :size="15" />查看证据</button>
            </div>
          </div>
          <div class="grid gap-px bg-slate-200 md:grid-cols-2">
            <div class="bg-white p-5"><p class="text-xs font-semibold uppercase text-slate-400">Previous</p><p class="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{{ selectedSignal.previousValue }}</p></div>
            <div class="bg-white p-5"><p class="text-xs font-semibold uppercase text-emerald-700">Current</p><p class="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-slate-900">{{ selectedSignal.currentValue }}</p></div>
          </div>
          <div class="border-t border-slate-200 bg-slate-50 p-5">
            <div class="flex items-center justify-between gap-3"><h4 class="text-sm font-semibold text-slate-800">证据快照</h4><a v-if="evidence" class="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:underline" :href="evidence.finalUrl" rel="noreferrer" target="_blank">打开原页面<ExternalLink :size="13" /></a></div>
            <p v-if="evidenceError" class="mt-3 text-sm text-red-700" role="alert">{{ evidenceError }}</p>
            <div v-else-if="evidence" class="mt-3 space-y-3"><div class="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500"><span>HTTP {{ evidence.statusCode }}</span><span>{{ evidence.title || "无标题" }}</span><span>{{ formatDate(evidence.collectedAt) }}</span></div><pre class="max-h-72 overflow-auto whitespace-pre-wrap break-words border border-slate-200 bg-white p-4 font-sans text-sm leading-6 text-slate-700">{{ evidence.extractedText }}</pre></div>
            <p v-else class="mt-3 text-sm text-slate-500">点击“查看证据”加载保存的正文快照。</p>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Activity, Check, ExternalLink, FileSearch, LoaderCircle, RefreshCw, X } from "lucide-vue-next"
import type { EvidenceDocument, ExternalSignal, ListEnvelope, MonitoringSource, SignalType } from "~/types/catalog"
const { request, errorMessage } = useApiClient()
const signals = ref<ExternalSignal[]>([])
const sources = ref<MonitoringSource[]>([])
const selectedId = ref("")
const evidence = ref<EvidenceDocument | null>(null)
const loading = ref(true)
const evidenceLoading = ref(false)
const reviewing = ref<"CONFIRMED" | "DISMISSED" | "">("")
const loadError = ref("")
const evidenceError = ref("")
const selectedSignal = computed(() => signals.value.find(item => item.id === selectedId.value) || null)
async function loadSignals() { loading.value = true; loadError.value = ""; try { const [signalResult, sourceResult] = await Promise.all([request<ListEnvelope<ExternalSignal>>("/api/v1/external-signals", { query: { pageSize: 100 } }), request<ListEnvelope<MonitoringSource>>("/api/v1/sources", { query: { pageSize: 100 } })]); signals.value = signalResult.data; sources.value = sourceResult.data; if (!selectedId.value && signals.value.length) selectSignal(signals.value[0]) } catch (error) { loadError.value = errorMessage(error, "情报信号加载失败。") } finally { loading.value = false } }
function selectSignal(signal: ExternalSignal) { selectedId.value = signal.id; evidence.value = null; evidenceError.value = "" }
async function loadEvidence(id: string) { evidenceLoading.value = true; evidenceError.value = ""; try { evidence.value = await request<EvidenceDocument>(`/api/v1/documents/${id}`) } catch (error) { evidenceError.value = errorMessage(error, "证据加载失败。") } finally { evidenceLoading.value = false } }
async function reviewSignal(reviewStatus: "CONFIRMED" | "DISMISSED") { if (!selectedSignal.value) return; reviewing.value = reviewStatus; loadError.value = ""; try { const updated = await request<ExternalSignal>(`/api/v1/external-signals/${selectedSignal.value.id}`, { method: "PATCH", body: { reviewStatus } }); const index = signals.value.findIndex(item => item.id === updated.id); if (index >= 0) signals.value[index] = updated } catch (error) { loadError.value = errorMessage(error, "信号审核失败。") } finally { reviewing.value = "" } }
function sourceName(id: string) { return sources.value.find(item => item.id === id)?.name || id }
function signalTypeLabel(value: SignalType) { return ({ PRICE: "价格", SPECIFICATION: "规格", AVAILABILITY: "可用性", LEAD_TIME: "交期", SUPPLIER_EVENT: "供应商事件" } as Record<SignalType, string>)[value] }
function reviewStatusLabel(value: ExternalSignal["reviewStatus"]) { return ({ PENDING: "待审核", CONFIRMED: "已确认", DISMISSED: "已忽略" } as const)[value] }
function statusClass(value: ExternalSignal["reviewStatus"]) { return { "status-confirmed": value === "CONFIRMED", "status-dismissed": value === "DISMISSED" } }
function formatDate(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) }
onMounted(loadSignals)
</script>

<style scoped>
.icon-button { @apply flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50; }
.secondary-button { @apply inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50; }
.review-button { @apply inline-flex h-9 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium disabled:opacity-50; }
.confirm-button { @apply bg-emerald-700 text-white hover:bg-emerald-800; }
.dismiss-button { @apply border border-slate-300 bg-white text-slate-600 hover:bg-slate-50; }
.empty-state { @apply flex min-h-56 items-center justify-center px-6 text-sm text-slate-500; }
.type-chip { @apply rounded bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700; }
.status { @apply rounded bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700; }
.status-confirmed { @apply bg-emerald-50 text-emerald-700; }
.status-dismissed { @apply bg-slate-100 text-slate-500; }
</style>
