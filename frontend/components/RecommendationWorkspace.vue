<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-emerald-700">Procurement recommendations</p>
        <h2 class="mt-1 text-xl font-semibold text-slate-900">采购建议</h2>
        <p class="mt-1 text-sm text-slate-500">基于已导入快照执行确定性计算，所有建议必须人工复核</p>
      </div>
      <div class="flex flex-wrap items-end gap-2">
        <label class="text-xs font-medium text-slate-600">分析日期<input v-model="generateForm.asOfDate" class="date-field" type="date"></label>
        <label class="text-xs font-medium text-slate-600">范围<select v-model.number="generateForm.horizonDays" class="date-field"><option :value="30">30 天</option><option :value="60">60 天</option><option :value="90">90 天</option></select></label>
        <button class="primary-button" :disabled="generating" type="button" @click="generate"><LoaderCircle v-if="generating" class="animate-spin" :size="16" /><Calculator v-else :size="16" />运行计算</button>
      </div>
    </div>

    <p v-if="successMessage" class="border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{{ successMessage }}</p>
    <div v-if="loadError" class="flex items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert"><span>{{ loadError }}</span><button class="font-medium underline" type="button" @click="loadAll">重试</button></div>

    <div class="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(440px,1.1fr)]">
      <section class="border border-slate-200 bg-white">
        <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h3 class="font-semibold">建议列表</h3><p class="mt-1 text-xs text-slate-500">{{ recommendations.length }} 条建议</p></div><button class="icon-button" title="刷新建议" type="button" @click="loadAll"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button></div>
        <div v-if="loading" class="empty-state"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载建议...</div>
        <div v-else-if="recommendations.length === 0" class="empty-state flex-col text-center"><ClipboardCheck :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">暂无采购建议</p><p class="mt-1 text-sm text-slate-500">导入库存、需求和在途后运行计算。</p></div>
        <div v-else class="divide-y divide-slate-100">
          <button v-for="item in recommendations" :key="item.id" class="w-full px-5 py-4 text-left hover:bg-slate-50" :class="selectedId === item.id ? 'bg-emerald-50/60' : ''" type="button" @click="select(item)">
            <div class="flex items-center justify-between gap-3"><span :class="riskClass(item.riskLevel)">{{ riskLabel(item.riskLevel) }}</span><span :class="statusClass(item.status)">{{ statusLabel(item.status) }}</span></div>
            <p class="mt-3 font-medium text-slate-900">{{ materialLabel(item.materialId) }}</p>
            <div class="mt-2 flex items-center justify-between gap-3 text-sm"><span class="text-slate-500">建议 {{ formatDate(item.recommendedOrderDate) }} 下单</span><span class="font-semibold tabular-nums text-slate-900">{{ formatQty(item.recommendedQty) }} {{ item.unit }}</span></div>
          </button>
        </div>
      </section>

      <section class="border border-slate-200 bg-white">
        <div v-if="!selected" class="empty-state flex-col text-center"><Calculator :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">选择一条建议查看计算依据</p></div>
        <template v-else>
          <div class="border-b border-slate-200 px-5 py-4">
            <div class="flex flex-wrap items-start justify-between gap-3"><div><div class="flex items-center gap-2"><span :class="riskClass(selected.riskLevel)">{{ riskLabel(selected.riskLevel) }}</span><span :class="statusClass(selected.status)">{{ statusLabel(selected.status) }}</span></div><h3 class="mt-3 font-semibold text-slate-900">{{ materialLabel(selected.materialId) }}</h3><p class="mt-1 text-xs text-slate-500">规则 {{ selected.algorithm.key }} v{{ selected.algorithm.version }} · 版本 {{ selected.version }}</p></div><p class="text-right"><span class="block text-xs text-slate-500">建议数量</span><span class="text-xl font-semibold tabular-nums">{{ formatQty(selected.recommendedQty) }} {{ selected.unit }}</span></p></div>
            <p class="mt-4 text-sm leading-6 text-slate-600">{{ selected.explanation }}</p>
          </div>
          <div class="grid grid-cols-2 gap-px bg-slate-200 sm:grid-cols-4">
            <div v-for="metric in calculationMetrics" :key="metric.label" class="bg-white p-4"><p class="text-xs text-slate-500">{{ metric.label }}</p><p class="mt-2 font-semibold tabular-nums">{{ metric.value }}</p></div>
          </div>
          <div class="grid gap-5 border-t border-slate-200 p-5 lg:grid-cols-2">
            <div><h4 class="text-sm font-semibold">时间与依据</h4><dl class="mt-3 space-y-2 text-sm"><div class="flex justify-between gap-4"><dt class="text-slate-500">建议下单日</dt><dd>{{ formatDate(selected.recommendedOrderDate) }}</dd></div><div class="flex justify-between gap-4"><dt class="text-slate-500">最晚下单日</dt><dd>{{ formatDate(selected.latestOrderDate) }}</dd></div><div class="flex justify-between gap-4"><dt class="text-slate-500">分析范围</dt><dd>{{ formatDate(selected.asOfDate) }} 至 {{ formatDate(selected.horizonEnd) }}</dd></div><div class="flex justify-between gap-4"><dt class="text-slate-500">证据引用</dt><dd>{{ selected.evidenceRefs.length }} 条</dd></div><div class="flex justify-between gap-4"><dt class="text-slate-500">已确认外部信号</dt><dd>{{ selected.externalSignalIds.length }} 条</dd></div></dl><div class="mt-4 flex flex-wrap gap-1"><code v-for="refId in selected.evidenceRefs" :key="refId" class="rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-500">{{ refId }}</code></div></div>
            <form class="space-y-3" @submit.prevent="submitDecision">
              <h4 class="text-sm font-semibold">人工复核</h4>
              <div class="grid grid-cols-3 gap-2"><button v-for="item in decisions" :key="item.value" class="choice-button" :class="decisionForm.decision === item.value ? 'choice-active' : ''" type="button" @click="decisionForm.decision = item.value">{{ item.label }}</button></div>
              <div v-if="decisionForm.decision === 'ADJUST'" class="grid grid-cols-2 gap-3"><label class="text-xs text-slate-600">调整日期<input v-model="decisionForm.adjustedOrderDate" class="field" type="date"></label><label class="text-xs text-slate-600">调整数量<input v-model.number="decisionForm.adjustedQty" class="field" min="0" step="any" type="number"></label></div>
              <label class="block text-xs text-slate-600">复核原因<textarea v-model="decisionForm.reason" class="textarea" maxlength="500" required /></label>
              <p v-if="decisionError" class="text-sm text-red-700" role="alert">{{ decisionError }}</p>
              <button class="primary-button w-full" :disabled="deciding || !decisionReady" type="submit"><LoaderCircle v-if="deciding" class="animate-spin" :size="16" /><Check v-else :size="16" />提交复核</button>
            </form>
          </div>
          <div class="border-t border-slate-200 px-5 py-4"><h4 class="text-sm font-semibold">复核流水</h4><p v-if="historyLoading" class="mt-3 text-sm text-slate-500">正在加载...</p><p v-else-if="decisionHistory.length === 0" class="mt-3 text-sm text-slate-500">暂无复核记录</p><div v-else class="mt-3 divide-y divide-slate-100 border-y border-slate-100"><div v-for="item in decisionHistory" :key="item.id" class="grid gap-1 py-3 text-sm sm:grid-cols-[90px_1fr_auto]"><span class="font-medium text-slate-800">{{ decisionLabel(item.decision) }}</span><span class="text-slate-600">{{ item.reason }}<span v-if="item.adjustedQty !== null"> · {{ formatQty(item.adjustedQty) }} {{ selected.unit }}</span><span v-if="item.adjustedOrderDate"> · {{ formatDate(item.adjustedOrderDate) }}</span></span><span class="text-xs text-slate-400">{{ formatDateTime(item.createdAt) }}</span></div></div></div>
        </template>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Calculator, Check, ClipboardCheck, LoaderCircle, RefreshCw } from "lucide-vue-next"
import type { ListEnvelope, Material, ProcurementRecommendation, RecommendationDecision } from "~/types/catalog"
const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()
const recommendations = ref<ProcurementRecommendation[]>([])
const materials = ref<Material[]>([])
const selectedId = ref("")
const loading = ref(true)
const generating = ref(false)
const deciding = ref(false)
const historyLoading = ref(false)
const loadError = ref("")
const decisionError = ref("")
const successMessage = ref("")
const decisionHistory = ref<RecommendationDecision[]>([])
const generateForm = reactive({ asOfDate: new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai" }).format(new Date()), horizonDays: 30 })
const decisionForm = reactive({ decision: "APPROVE" as "APPROVE" | "ADJUST" | "REJECT", adjustedOrderDate: "", adjustedQty: null as number | null, reason: "" })
const decisions = [{ value: "APPROVE" as const, label: "批准" }, { value: "ADJUST" as const, label: "调整" }, { value: "REJECT" as const, label: "拒绝" }]
const selected = computed(() => recommendations.value.find(item => item.id === selectedId.value) || null)
const decisionReady = computed(() => Boolean(decisionForm.reason.trim()) && (decisionForm.decision !== "ADJUST" || Boolean(selected.value && ((decisionForm.adjustedOrderDate && decisionForm.adjustedOrderDate !== selected.value.recommendedOrderDate) || (decisionForm.adjustedQty !== null && decisionForm.adjustedQty !== selected.value.recommendedQty)))))
const calculationMetrics = computed(() => selected.value ? [
  { label: "可用库存", value: `${formatQty(selected.value.calculation.availableQty)} ${selected.value.unit}` },
  { label: "期间需求", value: `${formatQty(selected.value.calculation.demandQty)} ${selected.value.unit}` },
  { label: "按期在途", value: `${formatQty(selected.value.calculation.openSupplyQty)} ${selected.value.unit}` },
  { label: "安全库存", value: `${formatQty(selected.value.calculation.safetyStockQty)} ${selected.value.unit}` },
  { label: "预计结余", value: `${formatQty(selected.value.calculation.projectedBalanceQty)} ${selected.value.unit}` },
  { label: "日均消耗", value: `${formatQty(selected.value.calculation.consumptionDailyQty)} ${selected.value.unit}` },
  { label: "交期", value: `${selected.value.calculation.leadTimeDays} 天` },
  { label: "原因", value: selected.value.reasonCodes.map(reasonLabel).join("、") },
] : [])
async function loadAll() { loading.value = true; loadError.value = ""; try { const [recResult, materialResult] = await Promise.all([request<ListEnvelope<ProcurementRecommendation>>("/api/v1/procurement-recommendations", { query: { pageSize: 100 } }), request<ListEnvelope<Material>>("/api/v1/materials", { query: { pageSize: 100 } })]); recommendations.value = recResult.data; materials.value = materialResult.data; if ((!selectedId.value || !recommendations.value.some(item => item.id === selectedId.value)) && recommendations.value.length) select(recommendations.value[0]) } catch (error) { loadError.value = errorMessage(error, "采购建议加载失败。") } finally { loading.value = false } }
async function generate() { generating.value = true; loadError.value = ""; successMessage.value = ""; try { const result = await request<{ recommendations: ProcurementRecommendation[]; skipped: { materialId: string; reason: string }[]; replayed: boolean }>("/api/v1/procurement-recommendations/generate", { method: "POST", body: generateForm }); successMessage.value = result.replayed ? "输入未变化，已返回现有建议。" : `已生成 ${result.recommendations.length} 条建议${result.skipped.length ? `，${result.skipped.length} 个物料因数据问题跳过` : ""}。`; await loadAll(); emit("changed") } catch (error) { loadError.value = errorMessage(error, "建议计算失败。") } finally { generating.value = false } }
async function submitDecision() { if (!selected.value) return; deciding.value = true; decisionError.value = ""; successMessage.value = ""; try { const result = await request<{ recommendation: ProcurementRecommendation; decision: RecommendationDecision }>(`/api/v1/procurement-recommendations/${selected.value.id}/decisions`, { method: "POST", headers: { "If-Match": `\"${selected.value.version}\"` }, body: { decision: decisionForm.decision, adjustedOrderDate: decisionForm.decision === "ADJUST" && decisionForm.adjustedOrderDate ? decisionForm.adjustedOrderDate : null, adjustedQty: decisionForm.decision === "ADJUST" ? decisionForm.adjustedQty : null, reason: decisionForm.reason.trim() } }); const index = recommendations.value.findIndex(item => item.id === result.recommendation.id); if (index >= 0) recommendations.value[index] = result.recommendation; decisionHistory.value.push(result.decision); successMessage.value = "复核决策已记录。"; Object.assign(decisionForm, { decision: "APPROVE", adjustedOrderDate: "", adjustedQty: null, reason: "" }); emit("changed") } catch (error) { decisionError.value = errorMessage(error, "复核提交失败，请刷新后重试。") } finally { deciding.value = false } }
async function select(item: ProcurementRecommendation) { selectedId.value = item.id; decisionError.value = ""; historyLoading.value = true; try { decisionHistory.value = (await request<{ data: RecommendationDecision[] }>(`/api/v1/procurement-recommendations/${item.id}/decisions`)).data } catch (error) { decisionError.value = errorMessage(error, "复核记录加载失败。") } finally { historyLoading.value = false } }
function materialLabel(id: string) { const item = materials.value.find(value => value.id === id); return item ? `${item.externalCode} · ${item.name}` : id }
function formatQty(value: number) { return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value) }
function formatDate(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeZone: "Asia/Shanghai" }).format(new Date(`${value}T00:00:00+08:00`)) }
function formatDateTime(value: string) { return new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short", timeZone: "Asia/Shanghai" }).format(new Date(value)) }
function riskLabel(value: ProcurementRecommendation["riskLevel"]) { return ({ HIGH: "高风险", MEDIUM: "中风险", LOW: "低风险" } as const)[value] }
function riskClass(value: ProcurementRecommendation["riskLevel"]) { return `badge ${value === "HIGH" ? "risk-high" : value === "MEDIUM" ? "risk-medium" : "risk-low"}` }
function statusLabel(value: ProcurementRecommendation["status"]) { return ({ PROPOSED: "待复核", APPROVED: "已批准", ADJUSTED: "已调整", REJECTED: "已拒绝" } as const)[value] }
function statusClass(value: ProcurementRecommendation["status"]) { return `badge ${value === "APPROVED" ? "status-approved" : value === "REJECTED" ? "status-rejected" : value === "ADJUSTED" ? "status-adjusted" : "status-proposed"}` }
function reasonLabel(value: string) { return ({ PROJECTED_SHORTAGE: "预计短缺", ORDER_DUE: "需立即下单", CONFIRMED_EXTERNAL_SIGNAL: "外部信号" } as Record<string, string>)[value] || value }
function decisionLabel(value: RecommendationDecision["decision"]) { return ({ APPROVE: "批准", ADJUST: "调整", REJECT: "拒绝" } as const)[value] }
onMounted(loadAll)
</script>

<style scoped>
.primary-button { @apply inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50; }
.icon-button { @apply flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50; }
.date-field { @apply mt-1 block h-10 rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600; }
.field { @apply mt-1 h-10 w-full rounded-md border border-slate-300 px-3 text-sm outline-none focus:border-emerald-600; }
.textarea { @apply mt-1 min-h-20 w-full resize-y rounded-md border border-slate-300 p-3 text-sm outline-none focus:border-emerald-600; }
.empty-state { @apply flex min-h-56 items-center justify-center px-6 text-sm text-slate-500; }
.badge { @apply inline-flex rounded px-2 py-1 text-xs font-medium; }
.risk-high { @apply bg-red-50 text-red-700; } .risk-medium { @apply bg-amber-50 text-amber-700; } .risk-low { @apply bg-sky-50 text-sky-700; }
.status-proposed { @apply bg-slate-100 text-slate-600; } .status-approved { @apply bg-emerald-50 text-emerald-700; } .status-adjusted { @apply bg-blue-50 text-blue-700; } .status-rejected { @apply bg-slate-200 text-slate-500; }
.choice-button { @apply h-9 rounded-md border border-slate-300 bg-white text-sm font-medium text-slate-600 hover:bg-slate-50; } .choice-active { @apply border-emerald-700 bg-emerald-50 text-emerald-800; }
</style>
