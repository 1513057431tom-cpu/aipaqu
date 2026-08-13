<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-emerald-700">External monitoring</p>
        <h2 class="mt-1 text-xl font-semibold text-slate-900">外部监控</h2>
        <p class="mt-1 text-sm text-slate-500">定向采集公开或已授权网页，保存证据并检测内容变化</p>
      </div>
      <button class="primary-button" type="button" @click="showForm = !showForm">
        <X v-if="showForm" :size="17" aria-hidden="true" />
        <Plus v-else :size="17" aria-hidden="true" />
        {{ showForm ? "关闭" : "新建来源" }}
      </button>
    </div>

    <form v-if="showForm" class="border-y border-slate-200 bg-white py-5" @submit.prevent="createSource">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label class="text-sm">
          <span class="field-label">来源名称</span>
          <input v-model="form.name" class="field" maxlength="200" required>
        </label>
        <label class="text-sm xl:col-span-2">
          <span class="field-label">目标 URL</span>
          <input v-model="form.targetUrl" class="field" placeholder="https://supplier.example.com/product" type="url" required>
        </label>
        <label class="text-sm">
          <span class="field-label">允许域名</span>
          <input v-model="form.allowedDomain" class="field" placeholder="supplier.example.com" required>
        </label>
        <label class="text-sm">
          <span class="field-label">信号类型</span>
          <select v-model="form.signalType" class="field">
            <option v-for="item in signalTypes" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="field-label">绑定类型</span>
          <select v-model="bindingType" class="field">
            <option value="material">物料</option>
            <option value="supplier">供应商</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="field-label">绑定对象</span>
          <select v-model="bindingId" class="field" required>
            <option value="" disabled>请选择</option>
            <option v-for="item in bindingOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="field-label">采集间隔</span>
          <select v-model.number="form.scheduleMinutes" class="field">
            <option :value="60">每小时</option>
            <option :value="360">每 6 小时</option>
            <option :value="720">每 12 小时</option>
            <option :value="1440">每天</option>
          </select>
        </label>
        <label class="text-sm md:col-span-2 xl:col-span-3">
          <span class="field-label">内容选择器</span>
          <input v-model="form.extractionSelector" class="field font-mono" placeholder="main、#price 或 .availability" maxlength="200">
        </label>
        <div class="flex items-end">
          <button class="primary-button h-10 w-full" :disabled="saving || !bindingId" type="submit">
            <LoaderCircle v-if="saving" class="animate-spin" :size="17" aria-hidden="true" />
            <Save v-else :size="17" aria-hidden="true" />
            {{ saving ? "保存中..." : "保存来源" }}
          </button>
        </div>
      </div>
      <p class="mt-4 text-xs text-slate-500">仅支持 HTTP/HTTPS 公开地址；内网、环回地址、跨域重定向和访问挑战会被阻止。</p>
      <p v-if="formError" class="mt-3 text-sm text-red-700" role="alert">{{ formError }}</p>
    </form>

    <p v-if="successMessage" class="border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{{ successMessage }}</p>
    <div v-if="loadError" class="flex items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      <span>{{ loadError }}</span>
      <button class="font-medium underline" type="button" @click="loadAll">重试</button>
    </div>

    <section class="border border-slate-200 bg-white" aria-live="polite">
      <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4">
        <div>
          <h3 class="font-semibold text-slate-900">监控来源</h3>
          <p class="mt-1 text-xs text-slate-500">{{ sources.length }} 个来源 · 手动采集可立即建立基线或检测变化</p>
        </div>
        <button class="icon-button" title="刷新来源" type="button" @click="loadAll"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button>
      </div>
      <div v-if="loading" class="empty-state"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载来源...</div>
      <div v-else-if="sources.length === 0" class="empty-state flex-col text-center">
        <Radar :size="30" class="text-slate-300" />
        <p class="mt-3 font-medium text-slate-800">还没有监控来源</p>
        <p class="mt-1 text-sm text-slate-500">新建来源后首次采集会建立证据基线。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[900px] table-fixed text-left text-sm">
          <thead class="bg-slate-50 text-xs text-slate-500">
            <tr><th class="w-[22%] px-4 py-3 font-medium">来源</th><th class="w-[22%] px-4 py-3 font-medium">绑定</th><th class="w-[10%] px-4 py-3 font-medium">类型</th><th class="w-[9%] px-4 py-3 font-medium">频率</th><th class="w-[14%] px-4 py-3 font-medium">最近采集</th><th class="w-[10%] px-4 py-3 font-medium">状态</th><th class="w-[13%] px-4 py-3 text-right font-medium">操作</th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="source in sources" :key="source.id" class="hover:bg-slate-50">
              <td class="px-4 py-3"><p class="truncate font-medium text-slate-900" :title="source.name">{{ source.name }}</p><p class="mt-1 truncate text-xs text-slate-400" :title="source.targetUrl">{{ source.targetUrl }}</p></td>
              <td class="truncate px-4 py-3 text-slate-600" :title="bindingLabel(source)">{{ bindingLabel(source) }}</td>
              <td class="px-4 py-3"><span class="type-chip">{{ signalTypeLabel(source.signalType) }}</span></td>
              <td class="px-4 py-3 text-slate-600">{{ scheduleLabel(source.scheduleMinutes) }}</td>
              <td class="px-4 py-3 text-slate-600">{{ formatDate(source.lastCollectedAt) }}</td>
              <td class="px-4 py-3"><span :class="statusClass(source.lastCollectionStatus)">{{ statusLabel(source.lastCollectionStatus) }}</span></td>
              <td class="px-4 py-3 text-right">
                <button class="secondary-button" :disabled="collectingId === source.id" type="button" @click="collect(source)">
                  <LoaderCircle v-if="collectingId === source.id" class="animate-spin" :size="15" />
                  <Play v-else :size="15" />
                  {{ collectingId === source.id ? "采集中..." : "立即采集" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="border border-slate-200 bg-white">
      <div class="border-b border-slate-200 px-5 py-4"><h3 class="font-semibold">最近采集任务</h3></div>
      <div v-if="jobs.length === 0" class="px-5 py-8 text-center text-sm text-slate-500">暂无采集记录</div>
      <div v-else class="divide-y divide-slate-100">
        <div v-for="job in jobs.slice(0, 8)" :key="job.id" class="grid gap-2 px-5 py-3 text-sm sm:grid-cols-[1fr_150px_150px_2fr] sm:items-center">
          <span class="font-mono text-xs text-slate-500">{{ sourceName(job.sourceId) }}</span>
          <span :class="statusClass(job.status)">{{ statusLabel(job.status) }}</span>
          <span class="text-slate-500">{{ formatDate(job.finishedAt) }}</span>
          <span class="truncate text-slate-500">{{ job.contentChanged ? "检测到内容变化" : job.errorMessage || "内容未变化或已建立基线" }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { LoaderCircle, Play, Plus, Radar, RefreshCw, Save, X } from "lucide-vue-next"
import type { CollectionJob, CollectionResult, ListEnvelope, Material, MonitoringSource, SignalType, Supplier } from "~/types/catalog"

const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()
const signalTypes: { value: SignalType; label: string }[] = [
  { value: "PRICE", label: "价格" }, { value: "SPECIFICATION", label: "规格" }, { value: "AVAILABILITY", label: "可用性" }, { value: "LEAD_TIME", label: "交期" }, { value: "SUPPLIER_EVENT", label: "供应商事件" },
]
const sources = ref<MonitoringSource[]>([])
const jobs = ref<CollectionJob[]>([])
const materials = ref<Material[]>([])
const suppliers = ref<Supplier[]>([])
const loading = ref(true)
const saving = ref(false)
const collectingId = ref("")
const showForm = ref(false)
const loadError = ref("")
const formError = ref("")
const successMessage = ref("")
const bindingType = ref<"material" | "supplier">("material")
const bindingId = ref("")
const form = reactive({ name: "", targetUrl: "", allowedDomain: "", scheduleMinutes: 1440, signalType: "PRICE" as SignalType, extractionSelector: "main" })

const bindingOptions = computed(() => bindingType.value === "material"
  ? materials.value.map(item => ({ id: item.id, label: `${item.externalCode} · ${item.name}` }))
  : suppliers.value.map(item => ({ id: item.id, label: `${item.externalCode} · ${item.name}` })))

watch(bindingType, () => { bindingId.value = "" })
watch(() => form.targetUrl, (value) => {
  if (form.allowedDomain || !value) return
  try { form.allowedDomain = new URL(value).hostname } catch { /* wait for a complete URL */ }
})

async function loadAll() {
  loading.value = true
  loadError.value = ""
  try {
    const [sourceResult, jobResult, materialResult, supplierResult] = await Promise.all([
      request<ListEnvelope<MonitoringSource>>("/api/v1/sources", { query: { pageSize: 100 } }),
      request<ListEnvelope<CollectionJob>>("/api/v1/collection-jobs", { query: { pageSize: 20 } }),
      request<ListEnvelope<Material>>("/api/v1/materials", { query: { pageSize: 100 } }),
      request<ListEnvelope<Supplier>>("/api/v1/suppliers", { query: { pageSize: 100 } }),
    ])
    sources.value = sourceResult.data
    jobs.value = jobResult.data
    materials.value = materialResult.data
    suppliers.value = supplierResult.data
  } catch (error) { loadError.value = errorMessage(error, "外部监控加载失败。") } finally { loading.value = false }
}

async function createSource() {
  saving.value = true
  formError.value = ""
  successMessage.value = ""
  try {
    await request<MonitoringSource>("/api/v1/sources", { method: "POST", body: { ...form, materialId: bindingType.value === "material" ? bindingId.value : null, supplierId: bindingType.value === "supplier" ? bindingId.value : null } })
    successMessage.value = `来源 ${form.name.trim()} 已创建，可立即采集建立基线。`
    Object.assign(form, { name: "", targetUrl: "", allowedDomain: "", scheduleMinutes: 1440, signalType: "PRICE", extractionSelector: "main" })
    bindingId.value = ""
    showForm.value = false
    await loadAll()
    emit("changed")
  } catch (error) { formError.value = errorMessage(error, "来源保存失败，请检查 URL、允许域名和绑定对象。") } finally { saving.value = false }
}

async function collect(source: MonitoringSource) {
  collectingId.value = source.id
  successMessage.value = ""
  loadError.value = ""
  try {
    const result = await request<CollectionResult>(`/api/v1/sources/${source.id}/collect`, { method: "POST" })
    if (result.job.status === "WAITING_HUMAN") successMessage.value = `${source.name} 需要人工授权或处理访问挑战，自动采集已停止。`
    else if (result.signal) successMessage.value = `${source.name} 检测到变化，已生成一条待审核信号。`
    else if (result.document?.previousContentDigest) successMessage.value = `${source.name} 采集成功，内容未变化。`
    else successMessage.value = `${source.name} 已建立首个证据基线。`
    await loadAll()
    emit("changed")
  } catch (error) { loadError.value = errorMessage(error, "采集启动失败。") } finally { collectingId.value = "" }
}

function signalTypeLabel(value: SignalType) { return signalTypes.find(item => item.value === value)?.label || value }
function scheduleLabel(value: number) { return value < 1440 ? `每 ${value / 60} 小时` : value === 1440 ? "每天" : `每 ${value / 1440} 天` }
function sourceName(id: string) { return sources.value.find(item => item.id === id)?.name || id }
function bindingLabel(source: MonitoringSource) { const item = source.materialId ? materials.value.find(v => v.id === source.materialId) : suppliers.value.find(v => v.id === source.supplierId); return item ? `${item.externalCode} · ${item.name}` : "未找到绑定对象" }
function statusLabel(value: string | null) { return ({ SUCCEEDED: "成功", FAILED: "失败", WAITING_HUMAN: "等待人工" } as Record<string, string>)[value || ""] || "未采集" }
function statusClass(value: string | null) { if (value === "SUCCEEDED") return "status success"; if (value === "WAITING_HUMAN") return "status warning"; if (value === "FAILED") return "status danger"; return "status neutral" }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "-" }
onMounted(loadAll)
</script>

<style scoped>
.field { @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100; }
.field-label { @apply font-medium text-slate-700; }
.primary-button { @apply inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50; }
.secondary-button { @apply inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50; }
.icon-button { @apply flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50; }
.empty-state { @apply flex min-h-48 items-center justify-center px-6 text-sm text-slate-500; }
.type-chip { @apply rounded bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700; }
.status { @apply inline-flex w-fit rounded px-2 py-1 text-xs font-medium; }
.success { @apply bg-emerald-50 text-emerald-700; } .warning { @apply bg-amber-50 text-amber-700; } .danger { @apply bg-red-50 text-red-700; } .neutral { @apply bg-slate-100 text-slate-500; }
</style>
