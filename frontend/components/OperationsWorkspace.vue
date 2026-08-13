<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-emerald-700">Internal operations</p>
        <h2 class="mt-1 text-xl font-semibold text-slate-900">经营数据</h2>
        <p class="mt-1 text-sm text-slate-500">库存、消耗、需求与在途供应的只读快照</p>
      </div>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
        type="button"
        @click="showImporter = !showImporter"
      >
        <Upload :size="17" aria-hidden="true" />
        {{ showImporter ? "收起导入" : "导入经营数据" }}
      </button>
    </div>

    <section v-if="showImporter" class="border border-slate-200 bg-white" aria-labelledby="operations-import-title">
      <div class="border-b border-slate-200 px-5 py-4">
        <h3 id="operations-import-title" class="font-semibold text-slate-900">创建只读数据快照</h3>
        <p class="mt-1 text-xs text-slate-500">同一同步批次使用唯一幂等键，重复提交不会生成重复记录</p>
      </div>
      <form class="grid gap-5 p-5 lg:grid-cols-[180px_180px_minmax(260px,1fr)_auto] lg:items-end" @submit.prevent="submitImport">
        <label class="text-sm">
          <span class="font-medium text-slate-700">数据类型</span>
          <select v-model="importForm.dataType" class="field" @change="resetImportFile">
            <option v-for="item in tabs" :key="item.key" :value="item.key">{{ item.label }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="font-medium text-slate-700">来源系统</span>
          <select v-model="importForm.sourceSystem" class="field">
            <option v-for="source in sourceSystems" :key="source" :value="source">{{ source }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="font-medium text-slate-700">CSV 文件</span>
          <input ref="fileInput" class="field file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium" accept=".csv,text/csv" type="file" @change="selectFile">
        </label>
        <button
          class="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-emerald-700 px-5 text-sm font-medium text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="!selectedFile || uploading"
          type="submit"
        >
          <LoaderCircle v-if="uploading" class="animate-spin" :size="17" aria-hidden="true" />
          <Upload v-else :size="17" aria-hidden="true" />
          {{ uploading ? "导入中..." : "开始导入" }}
        </button>
      </form>
      <div class="grid gap-4 border-t border-slate-100 bg-slate-50 px-5 py-4 lg:grid-cols-[1fr_auto]">
        <div class="min-w-0">
          <p class="text-xs font-medium text-slate-600">必需字段</p>
          <p class="mt-1 break-all font-mono text-xs leading-5 text-slate-500">{{ currentTab.headers.join(", ") }}</p>
        </div>
        <p class="text-xs text-slate-500 lg:text-right">UTF-8 · 最大 5 MB · 物料编码必须已存在</p>
      </div>
      <div v-if="importError" class="border-t border-red-100 bg-red-50 px-5 py-3 text-sm text-red-800" role="alert">{{ importError }}</div>
      <div v-if="importResult" class="flex flex-col gap-3 border-t border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between" role="status">
        <div>
          <p class="text-sm font-medium text-slate-900">{{ resultLabel }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ importResult.fileName }} · 成功 {{ importResult.createdRows }} 行 · 失败 {{ importResult.failedRows }} 行</p>
        </div>
        <span class="w-fit rounded px-2.5 py-1 text-xs font-medium" :class="resultClass">{{ importResult.status }}</span>
      </div>
    </section>

    <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <button
        v-for="item in tabs"
        :key="item.key"
        class="min-h-24 rounded-md border bg-white p-4 text-left transition-colors"
        :class="activeTab === item.key ? 'border-emerald-600 ring-1 ring-emerald-100' : 'border-slate-200 hover:border-slate-300'"
        type="button"
        @click="activeTab = item.key"
      >
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm font-medium" :class="activeTab === item.key ? 'text-emerald-800' : 'text-slate-700'">{{ item.label }}</span>
          <component :is="item.icon" :size="18" :class="item.iconClass" aria-hidden="true" />
        </div>
        <p class="mt-3 text-2xl font-semibold tabular-nums">{{ loading ? "-" : counts[item.key] }}</p>
      </button>
    </div>

    <section class="border border-slate-200 bg-white" aria-live="polite">
      <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 class="font-semibold text-slate-900">{{ currentTab.label }}快照</h3>
          <p class="mt-1 text-xs text-slate-500">按业务时间展示最近 100 条记录</p>
        </div>
        <button class="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 px-3 text-sm text-slate-600 hover:bg-slate-50" type="button" @click="loadData">
          <RefreshCw :size="15" :class="loading ? 'animate-spin' : ''" aria-hidden="true" />
          刷新
        </button>
      </div>

      <div v-if="loading" class="flex min-h-56 items-center justify-center text-sm text-slate-500">
        <LoaderCircle class="mr-2 animate-spin" :size="18" aria-hidden="true" />正在加载经营数据...
      </div>
      <div v-else-if="loadError" class="flex min-h-56 flex-col items-center justify-center px-6 text-center" role="alert">
        <CircleAlert :size="28" class="text-red-600" aria-hidden="true" />
        <p class="mt-3 text-sm font-medium text-slate-900">数据加载失败</p>
        <p class="mt-1 text-sm text-slate-500">{{ loadError }}</p>
      </div>
      <div v-else-if="currentRows.length === 0" class="flex min-h-56 flex-col items-center justify-center px-6 text-center">
        <DatabaseZap :size="30" class="text-slate-300" aria-hidden="true" />
        <p class="mt-3 text-sm font-medium text-slate-900">暂无{{ currentTab.label }}数据</p>
        <p class="mt-1 text-sm text-slate-500">通过 CSV 验证数据契约，后续连接器复用同一套快照结构。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[980px] text-left text-sm">
          <thead class="bg-slate-50 text-xs text-slate-500">
            <tr>
              <th v-for="column in currentTab.columns" :key="column.key" class="px-5 py-3 font-medium">{{ column.label }}</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="row in currentRows" :key="row.id" class="hover:bg-slate-50">
              <td v-for="column in currentTab.columns" :key="column.key" class="whitespace-nowrap px-5 py-3 text-slate-600">
                <template v-if="column.key === 'material'">
                  <p class="font-medium text-slate-900">{{ row.material.name }}</p>
                  <p class="mt-0.5 font-mono text-xs text-slate-400">{{ row.material.externalCode }}</p>
                </template>
                <span v-else-if="column.key === 'sourceSystem'" class="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">{{ row.sourceSystem }}</span>
                <span v-else>{{ displayValue(row, column.key) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  Boxes,
  CircleAlert,
  ClipboardList,
  DatabaseZap,
  Factory,
  LoaderCircle,
  RefreshCw,
  ShoppingCart,
  Upload,
} from "lucide-vue-next"

import type {
  ConsumptionSnapshot,
  InternalDataType,
  InternalImportResult,
  InventorySnapshot,
  ListEnvelope,
  MaterialDemand,
  OpenSupplySnapshot,
  SourceSystem,
} from "~/types/catalog"

type OperationsRow = InventorySnapshot | ConsumptionSnapshot | MaterialDemand | OpenSupplySnapshot
type Column = { key: string; label: string }
type TabDefinition = {
  key: InternalDataType
  label: string
  endpoint: string
  icon: typeof Boxes
  iconClass: string
  headers: string[]
  columns: Column[]
}

const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()

const tabs: TabDefinition[] = [
  {
    key: "INVENTORY", label: "库存", endpoint: "/api/v1/inventory-snapshots", icon: Boxes, iconClass: "text-emerald-700",
    headers: ["materialExternalCode", "locationCode", "snapshotAt", "onHandQty", "availableQty", "unit", "sourceRecordRef"],
    columns: [
      { key: "material", label: "物料" }, { key: "locationCode", label: "仓库" }, { key: "availableQty", label: "可用库存" },
      { key: "onHandQty", label: "账面库存" }, { key: "reservedQty", label: "预留" }, { key: "qualityHoldQty", label: "质检冻结" },
      { key: "snapshotAt", label: "业务时间" }, { key: "sourceSystem", label: "来源" },
    ],
  },
  {
    key: "CONSUMPTION", label: "消耗", endpoint: "/api/v1/consumption-snapshots", icon: Factory, iconClass: "text-sky-700",
    headers: ["materialExternalCode", "bucketDate", "actualQty", "plannedQty", "unit", "sourceRecordRef"],
    columns: [
      { key: "material", label: "物料" }, { key: "actualQty", label: "实际消耗" }, { key: "plannedQty", label: "计划消耗" },
      { key: "bucketDate", label: "业务日期" }, { key: "sourceSystem", label: "来源" }, { key: "sourceRecordRef", label: "来源记录" },
    ],
  },
  {
    key: "DEMAND", label: "需求", endpoint: "/api/v1/material-demands", icon: ClipboardList, iconClass: "text-amber-700",
    headers: ["materialExternalCode", "requiredAt", "requiredQty", "unit", "sourceType", "sourceRecordRef"],
    columns: [
      { key: "material", label: "物料" }, { key: "requiredQty", label: "需求数量" }, { key: "sourceType", label: "需求类型" },
      { key: "requiredAt", label: "需求时间" }, { key: "sourceSystem", label: "来源" }, { key: "sourceRecordRef", label: "来源记录" },
    ],
  },
  {
    key: "OPEN_SUPPLY", label: "在途供应", endpoint: "/api/v1/open-supply-snapshots", icon: ShoppingCart, iconClass: "text-violet-700",
    headers: ["materialExternalCode", "orderNo", "orderLineNo", "orderedQty", "receivedQty", "openQty", "unit", "expectedAt", "status", "sourceRecordRef"],
    columns: [
      { key: "material", label: "物料" }, { key: "orderNo", label: "采购单" }, { key: "openQty", label: "在途数量" },
      { key: "receivedQty", label: "已收数量" }, { key: "expectedAt", label: "预计到货" }, { key: "status", label: "状态" }, { key: "sourceSystem", label: "来源" },
    ],
  },
]

const sourceSystems: SourceSystem[] = ["ERP", "MES", "WMS", "DATABASE", "FILE", "OTHER"]
const activeTab = ref<InternalDataType>("INVENTORY")
const rows = reactive<Record<InternalDataType, OperationsRow[]>>({ INVENTORY: [], CONSUMPTION: [], DEMAND: [], OPEN_SUPPLY: [] })
const counts = reactive<Record<InternalDataType, number>>({ INVENTORY: 0, CONSUMPTION: 0, DEMAND: 0, OPEN_SUPPLY: 0 })
const loading = ref(true)
const loadError = ref("")
const showImporter = ref(false)
const selectedFile = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const importError = ref("")
const importResult = ref<InternalImportResult | null>(null)
const importIdempotencyKey = ref(crypto.randomUUID())
const importForm = reactive<{ dataType: InternalDataType; sourceSystem: SourceSystem }>({ dataType: "INVENTORY", sourceSystem: "ERP" })

const currentTab = computed(() => tabs.find(item => item.key === activeTab.value) || tabs[0])
const currentRows = computed(() => rows[activeTab.value])
const resultLabel = computed(() => importResult.value?.replayed ? "已返回原同步结果" : "同步批次处理完成")
const resultClass = computed(() => {
  if (importResult.value?.status === "SUCCEEDED") return "bg-emerald-50 text-emerald-700"
  if (importResult.value?.status === "SUCCEEDED_WITH_ERRORS") return "bg-amber-50 text-amber-700"
  return "bg-red-50 text-red-700"
})

function selectFile(event: Event) {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] || null
  importIdempotencyKey.value = crypto.randomUUID()
  importResult.value = null
  importError.value = ""
}

function resetImportFile() {
  selectedFile.value = null
  importResult.value = null
  importError.value = ""
  importIdempotencyKey.value = crypto.randomUUID()
  if (fileInput.value) fileInput.value.value = ""
}

async function submitImport() {
  if (!selectedFile.value) return
  uploading.value = true
  importError.value = ""
  importResult.value = null
  try {
    const body = new FormData()
    body.append("dataType", importForm.dataType)
    body.append("sourceSystem", importForm.sourceSystem)
    body.append("file", selectedFile.value)
    importResult.value = await request<InternalImportResult>("/api/v1/internal-data/imports", {
      method: "POST",
      body,
      headers: { "Idempotency-Key": importIdempotencyKey.value },
    })
    activeTab.value = importForm.dataType
    await loadData()
    emit("changed")
  } catch (error) {
    importError.value = errorMessage(error, "经营数据导入失败，请检查字段、物料编码和数量口径。")
  } finally {
    uploading.value = false
  }
}

async function loadData() {
  loading.value = true
  loadError.value = ""
  try {
    const results = await Promise.all(tabs.map(tab => request<ListEnvelope<OperationsRow>>(tab.endpoint, { query: { pageSize: 100 } })))
    tabs.forEach((tab, index) => {
      rows[tab.key] = results[index].data
      counts[tab.key] = results[index].pagination.totalItems
    })
  } catch (error) {
    loadError.value = errorMessage(error, "经营数据加载失败。")
  } finally {
    loading.value = false
  }
}

function displayValue(row: OperationsRow, key: string): string {
  const value = (row as unknown as Record<string, unknown>)[key]
  if (typeof value === "number") {
    const unit = "unit" in row ? row.unit : ""
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value)} ${unit}`.trim()
  }
  if (typeof value === "string" && (key.endsWith("At") || key === "bucketDate")) {
    const parsed = new Date(value)
    return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: key === "bucketDate" ? undefined : "short" }).format(parsed)
  }
  return String(value ?? "-")
}

onMounted(loadData)
</script>

<style scoped>
.field {
  @apply mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}
</style>
