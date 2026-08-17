<template>
  <div class="space-y-5">
    <header class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div><h2 class="text-xl font-semibold text-slate-900">外部监控</h2><p class="mt-1 text-sm text-slate-500">按物料组或单个物料配置网站，由页面导航智能体完成站内检索和证据采集</p></div>
      <button class="primary-button" type="button" @click="openCreate"><Plus :size="17" />新建监控</button>
    </header>

    <form v-if="showForm" class="border-y border-slate-200 bg-white py-5" @submit.prevent="saveSource">
      <div class="mb-4 flex items-center justify-between"><div><h3 class="font-semibold text-slate-900">{{ editingId ? '编辑监控来源' : '新建监控来源' }}</h3><p class="mt-1 text-xs text-slate-500">默认绑定覆盖物料最多的分组，也可改为单个物料</p></div><button class="icon-button" title="关闭" type="button" @click="closeForm"><X :size="17" /></button></div>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <label class="text-sm"><span class="field-label">来源名称</span><input v-model="form.name" class="field" maxlength="200" required></label>
        <label class="text-sm xl:col-span-2"><span class="field-label">目标网址</span><input v-model="form.targetUrl" class="field" placeholder="https://example.com/products" type="url" required></label>
        <label class="text-sm"><span class="field-label">允许域名</span><input v-model="form.allowedDomain" class="field" placeholder="example.com" required></label>
        <label class="text-sm"><span class="field-label">监控范围</span><select v-model="bindingType" class="field"><option value="group">物料组</option><option value="material">单个物料</option><option value="supplier">供应商（旧来源兼容）</option></select></label>
        <label class="text-sm"><span class="field-label">绑定对象</span><select v-model="bindingId" class="field" required><option value="" disabled>请选择</option><option v-for="item in bindingOptions" :key="item.id" :value="item.id">{{ item.label }}</option></select></label>
        <label class="text-sm"><span class="field-label">关注变化</span><select v-model="form.signalType" class="field"><option v-for="item in signalTypes" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        <label class="text-sm"><span class="field-label">采集间隔</span><select v-model.number="form.scheduleMinutes" class="field"><option :value="60">每小时</option><option :value="360">每 6 小时</option><option :value="720">每 12 小时</option><option :value="1440">每天</option></select></label>
        <label class="text-sm"><span class="field-label">采集方式</span><select v-model="form.collectionMode" class="field"><option value="AI_BROWSER">AI 智能浏览</option><option value="HTTP">固定页面采集</option></select></label>
        <label v-if="form.collectionMode === 'HTTP'" class="text-sm"><span class="field-label">内容选择器</span><input v-model="form.extractionSelector" class="field font-mono" placeholder="main 或 #price" maxlength="200"></label>
        <label class="text-sm md:col-span-2 xl:col-span-3"><span class="field-label">导航与检索目标</span><textarea v-model="form.navigationGoal" class="textarea" placeholder="例如：在产品中心搜索物料名称，进入价格或供货信息标签，提取规格、价格和交期" maxlength="2000" :required="form.collectionMode === 'AI_BROWSER'" /></label>
        <div class="flex items-end gap-2"><button class="secondary-button flex-1" type="button" @click="closeForm">取消</button><button class="primary-button flex-1" :disabled="saving || !bindingId" type="submit"><LoaderCircle v-if="saving" class="animate-spin" :size="17" /><Save v-else :size="17" />{{ saving ? '保存中...' : '保存' }}</button></div>
      </div>
      <p class="mt-4 text-xs text-slate-500">智能浏览仅执行站内只读搜索、标签、分页和详情导航。遇到登录、验证码、付费墙或权限限制会停止并转人工。</p>
      <p v-if="formError" class="mt-3 text-sm text-red-700" role="alert">{{ formError }}</p>
    </form>

    <p v-if="successMessage" class="border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">{{ successMessage }}</p>
    <div v-if="loadError" class="border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">{{ loadError }}</div>

    <section class="border border-slate-200 bg-white">
      <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4"><div><h3 class="font-semibold">监控来源</h3><p class="mt-1 text-xs text-slate-500">{{ sources.length }} 个来源，以物料范围组织采集任务</p></div><button class="icon-button" title="刷新" type="button" @click="loadAll"><RefreshCw :size="16" :class="loading ? 'animate-spin' : ''" /></button></div>
      <div v-if="loading" class="empty-state"><LoaderCircle class="mr-2 animate-spin" :size="18" />正在加载...</div>
      <div v-else-if="!sources.length" class="empty-state flex-col text-center"><Radar :size="30" class="text-slate-300" /><p class="mt-3 font-medium text-slate-800">还没有监控来源</p></div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[940px] table-fixed text-left text-sm">
          <thead class="bg-slate-50 text-xs text-slate-500"><tr><th class="w-[17%] px-3 py-3">来源</th><th class="w-[16%] px-3 py-3">物料范围</th><th class="w-[12%] px-3 py-3">采集方式</th><th class="w-[9%] px-3 py-3">关注变化</th><th class="w-[13%] px-3 py-3">最近采集</th><th class="w-[8%] px-3 py-3">状态</th><th class="w-[25%] px-3 py-3 text-right">操作</th></tr></thead>
          <tbody class="divide-y divide-slate-100"><tr v-for="source in sources" :key="source.id" class="hover:bg-slate-50">
            <td class="px-3 py-3"><p class="truncate font-medium" :title="source.name">{{ source.name }}</p><p class="mt-1 truncate text-xs text-slate-400" :title="source.navigationGoal || source.targetUrl">{{ source.navigationGoal || source.targetUrl }}</p></td>
            <td class="px-3 py-3"><span class="block truncate font-medium text-slate-700">{{ bindingLabel(source) }}</span><span class="mt-1 block text-xs text-slate-400">{{ bindingKind(source) }}</span></td>
            <td class="px-3 py-3"><span class="type-chip">{{ source.collectionMode === 'AI_BROWSER' ? 'AI 智能浏览' : '固定页面' }}</span></td>
            <td class="px-3 py-3 text-slate-600">{{ signalTypeLabel(source.signalType) }}</td><td class="px-3 py-3 text-slate-600">{{ formatDate(source.lastCollectedAt) }}</td><td class="px-3 py-3"><span :class="statusClass(source.lastCollectionStatus)">{{ statusLabel(source.lastCollectionStatus) }}</span></td>
            <td class="px-3 py-3"><div class="flex justify-end gap-1"><button class="icon-button" title="编辑来源" type="button" @click="openEdit(source)"><Pencil :size="15" /></button><button class="icon-button text-red-600" title="删除来源" type="button" @click="removeSource(source)"><Trash2 :size="15" /></button><button class="secondary-button ml-1" :disabled="collectingId === source.id" type="button" @click="collect(source)"><LoaderCircle v-if="collectingId === source.id" class="animate-spin" :size="15" /><Play v-else :size="15" />{{ collectingId === source.id ? '采集中...' : '立即采集' }}</button></div></td>
          </tr></tbody>
        </table>
      </div>
    </section>

    <section class="border border-slate-200 bg-white"><div class="border-b border-slate-200 px-5 py-4"><h3 class="font-semibold">最近采集任务</h3></div><div v-if="!jobs.length" class="px-5 py-8 text-center text-sm text-slate-500">暂无记录</div><div v-else class="divide-y divide-slate-100"><div v-for="job in jobs.slice(0, 8)" :key="job.id" class="grid gap-2 px-5 py-3 text-sm sm:grid-cols-[1fr_140px_160px_2fr]"><span>{{ sourceName(job.sourceId) }}</span><span :class="statusClass(job.status)">{{ statusLabel(job.status) }}</span><span class="text-slate-500">{{ formatDate(job.finishedAt) }}</span><span class="truncate text-slate-500">{{ job.errorMessage || (job.contentChanged ? '证据变化已交给情报分析智能体' : '采集成功，未发现相关变化') }}</span></div></div></section>
  </div>
</template>

<script setup lang="ts">
import { LoaderCircle, Pencil, Play, Plus, Radar, RefreshCw, Save, Trash2, X } from "lucide-vue-next"
import type { CollectionJob, CollectionResult, ListEnvelope, Material, MaterialGroup, MonitoringSource, SignalType, Supplier } from "~/types/catalog"
const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()
const signalTypes: { value: SignalType; label: string }[] = [{ value: "PRICE", label: "价格" }, { value: "SPECIFICATION", label: "规格" }, { value: "AVAILABILITY", label: "可用性" }, { value: "LEAD_TIME", label: "交期" }, { value: "SUPPLIER_EVENT", label: "供应事件" }]
const sources = ref<MonitoringSource[]>([]); const jobs = ref<CollectionJob[]>([]); const materials = ref<Material[]>([]); const groups = ref<MaterialGroup[]>([]); const suppliers = ref<Supplier[]>([])
const loading = ref(true); const saving = ref(false); const collectingId = ref(""); const showForm = ref(false); const editingId = ref(""); const loadError = ref(""); const formError = ref(""); const successMessage = ref("")
const bindingType = ref<"group" | "material" | "supplier">("group"); const bindingId = ref("")
const emptyForm = () => ({ name: "", targetUrl: "", allowedDomain: "", scheduleMinutes: 1440, signalType: "PRICE" as SignalType, extractionSelector: "main", collectionMode: "AI_BROWSER" as "AI_BROWSER" | "HTTP", navigationGoal: "搜索绑定物料，进入产品详情或供货信息页面，提取最新变化", status: "ACTIVE" as "ACTIVE" | "PAUSED" })
const form = reactive(emptyForm())
const bindingOptions = computed(() => bindingType.value === "group" ? [...groups.value].sort((a, b) => b.materialCount - a.materialCount).map(item => ({ id: item.id, label: `${item.name}（${item.materialCount} 项）` })) : bindingType.value === "material" ? materials.value.map(item => ({ id: item.id, label: `${item.externalCode} · ${item.name}` })) : suppliers.value.map(item => ({ id: item.id, label: `${item.externalCode} · ${item.name}` })))
watch(bindingType, () => { bindingId.value = bindingOptions.value[0]?.id || "" })
watch(() => form.targetUrl, value => { if (form.allowedDomain || !value) return; try { form.allowedDomain = new URL(value).hostname } catch {} })
function defaultBinding() { bindingType.value = groups.value.length ? "group" : "material"; bindingId.value = bindingOptions.value[0]?.id || "" }
function openCreate() { editingId.value = ""; Object.assign(form, emptyForm()); defaultBinding(); formError.value = ""; showForm.value = true }
function openEdit(source: MonitoringSource) { editingId.value = source.id; Object.assign(form, { name: source.name, targetUrl: source.targetUrl, allowedDomain: source.allowedDomain, scheduleMinutes: source.scheduleMinutes, signalType: source.signalType, extractionSelector: source.extractionSelector, collectionMode: source.collectionMode, navigationGoal: source.navigationGoal, status: source.status === "PAUSED" ? "PAUSED" : "ACTIVE" }); bindingType.value = source.materialGroupId ? "group" : source.materialId ? "material" : "supplier"; nextTick(() => { bindingId.value = source.materialGroupId || source.materialId || source.supplierId || "" }); formError.value = ""; showForm.value = true }
function closeForm() { showForm.value = false; editingId.value = ""; formError.value = "" }
async function loadAll() { loading.value = true; loadError.value = ""; try { const [sourceResult, jobResult, materialResult, groupResult, supplierResult] = await Promise.all([request<ListEnvelope<MonitoringSource>>("/api/v1/sources", { query: { pageSize: 100 } }), request<ListEnvelope<CollectionJob>>("/api/v1/collection-jobs", { query: { pageSize: 20 } }), request<ListEnvelope<Material>>("/api/v1/materials", { query: { pageSize: 100 } }), request<ListEnvelope<MaterialGroup>>("/api/v1/material-groups", { query: { pageSize: 100 } }), request<ListEnvelope<Supplier>>("/api/v1/suppliers", { query: { pageSize: 100 } })]); sources.value = sourceResult.data; jobs.value = jobResult.data; materials.value = materialResult.data; groups.value = groupResult.data; suppliers.value = supplierResult.data } catch (error) { loadError.value = errorMessage(error, "外部监控加载失败。") } finally { loading.value = false } }
async function saveSource() { saving.value = true; formError.value = ""; try { const body = { ...form, materialGroupId: bindingType.value === "group" ? bindingId.value : null, materialId: bindingType.value === "material" ? bindingId.value : null, supplierId: bindingType.value === "supplier" ? bindingId.value : null }; await request<MonitoringSource>(editingId.value ? `/api/v1/sources/${editingId.value}` : "/api/v1/sources", { method: editingId.value ? "PATCH" : "POST", body }); successMessage.value = editingId.value ? "监控来源已更新。" : "监控来源已创建，可立即启动 AI 采集。"; closeForm(); await loadAll(); emit("changed") } catch (error) { formError.value = errorMessage(error, "来源保存失败，请检查网址、物料范围和导航目标。") } finally { saving.value = false } }
async function removeSource(source: MonitoringSource) { if (!window.confirm(`确认删除“${source.name}”吗？历史证据和情报仍会保留。`)) return; try { await request(`/api/v1/sources/${source.id}`, { method: "DELETE" }); successMessage.value = "监控来源已删除，历史记录已保留。"; await loadAll(); emit("changed") } catch (error) { loadError.value = errorMessage(error, "来源删除失败。") } }
async function collect(source: MonitoringSource) { collectingId.value = source.id; successMessage.value = ""; loadError.value = ""; try { const result = await request<CollectionResult>(`/api/v1/sources/${source.id}/collect`, { method: "POST", timeout: 120000 }); if (result.job.status === "WAITING_HUMAN") { loadError.value = `${source.name} 已停止自动采集：${result.job.errorMessage || '需要人工授权或配置浏览器运行时'}。` } else if (result.job.status === "FAILED") { loadError.value = `${source.name} 采集失败：${result.job.errorMessage || '请检查网站连接和采集配置'}。` } else { const analysisMessage = result.signal ? `${source.name} 已生成一条待复核物料情报。` : !result.document?.previousContentDigest ? `${source.name} 已建立首份证据基线，本次没有历史内容可供比较。` : result.document.changed ? `${source.name} 页面有变化，但 AI 判定与绑定物料或关注指标无关，因此未生成情报信号。` : `${source.name} 页面内容没有变化，因此未重复生成情报信号。`; successMessage.value = `${analysisMessage}${result.downstreamStatus === 'QUEUED' ? ` ${result.downstreamMessage}` : ''}` } await loadAll(); emit("changed") } catch (error) { loadError.value = errorMessage(error, "采集超过两分钟未完成，已停止等待。请检查浏览器内核、网络和模型连接。") } finally { collectingId.value = "" } }
function signalTypeLabel(value: SignalType) { return signalTypes.find(item => item.value === value)?.label || value }
function sourceName(id: string) { return sources.value.find(item => item.id === id)?.name || id }
function bindingLabel(source: MonitoringSource) { if (source.materialGroupId) return groups.value.find(item => item.id === source.materialGroupId)?.name || source.materialGroupId; if (source.materialId) { const item = materials.value.find(value => value.id === source.materialId); return item ? `${item.externalCode} · ${item.name}` : source.materialId } const item = suppliers.value.find(value => value.id === source.supplierId); return item?.name || source.supplierId || "未绑定" }
function bindingKind(source: MonitoringSource) { return source.materialGroupId ? "物料组" : source.materialId ? "单个物料" : "旧供应商来源" }
function statusLabel(value: string | null) { return ({ SUCCEEDED: "成功", FAILED: "失败", WAITING_HUMAN: "等待人工" } as Record<string, string>)[value || ""] || "未采集" }
function statusClass(value: string | null) { if (value === "SUCCEEDED") return "status success"; if (value === "WAITING_HUMAN") return "status warning"; if (value === "FAILED") return "status danger"; return "status neutral" }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(value)) : "-" }
onMounted(loadAll)
</script>

<style scoped>
.field { @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100; }.field-label { @apply font-medium text-slate-700; }.textarea { @apply mt-1 min-h-20 w-full resize-y rounded-md border border-slate-300 bg-white p-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100; }.primary-button { @apply inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-50; }.secondary-button { @apply inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50; }.icon-button { @apply inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-300 bg-white text-slate-600 hover:bg-slate-50; }.empty-state { @apply flex min-h-48 items-center justify-center px-6 text-sm text-slate-500; }.type-chip { @apply rounded bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700; }.status { @apply inline-flex rounded px-2 py-1 text-xs font-medium; }.success { @apply bg-emerald-50 text-emerald-700; }.warning { @apply bg-amber-50 text-amber-700; }.danger { @apply bg-red-50 text-red-700; }.neutral { @apply bg-slate-100 text-slate-500; }
</style>
