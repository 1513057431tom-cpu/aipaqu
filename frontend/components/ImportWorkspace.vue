<template>
  <div class="space-y-5">
    <div>
      <h2 class="text-xl font-semibold text-slate-900">CSV 数据导入</h2>
      <p class="mt-1 text-sm text-slate-500">物料与供应商主数据</p>
    </div>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <form class="border border-slate-200 bg-white p-5" @submit.prevent="submitImport">
        <fieldset>
          <legend class="text-sm font-medium text-slate-700">数据类型</legend>
          <div class="mt-2 inline-flex rounded-md border border-slate-300 bg-slate-50 p-1">
            <label
              v-for="option in entityOptions"
              :key="option.value"
              class="cursor-pointer rounded px-4 py-2 text-sm font-medium"
              :class="entityType === option.value ? 'bg-white text-emerald-800 shadow-sm' : 'text-slate-500'"
            >
              <input v-model="entityType" class="sr-only" name="entityType" type="radio" :value="option.value">
              {{ option.label }}
            </label>
          </div>
        </fieldset>

        <label class="mt-6 block text-sm font-medium text-slate-700" for="catalog-file">CSV 文件</label>
        <label
          class="mt-2 flex min-h-40 cursor-pointer flex-col items-center justify-center border border-dashed border-slate-300 bg-slate-50 px-6 text-center hover:border-emerald-500 hover:bg-emerald-50"
          for="catalog-file"
        >
          <FileUp :size="30" class="text-slate-400" aria-hidden="true" />
          <span class="mt-3 text-sm font-medium text-slate-700">{{ selectedFile?.name || "选择 CSV 文件" }}</span>
          <span class="mt-1 text-xs text-slate-500">UTF-8，最大 5 MB</span>
          <input id="catalog-file" class="sr-only" accept=".csv,text/csv" type="file" @change="selectFile">
        </label>

        <p v-if="formError" class="mt-4 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
          {{ formError }}
        </p>

        <button
          class="mt-5 inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          :disabled="!selectedFile || uploading"
          type="submit"
        >
          <LoaderCircle v-if="uploading" class="animate-spin" :size="17" aria-hidden="true" />
          <Upload v-else :size="17" aria-hidden="true" />
          {{ uploading ? "导入中..." : "开始导入" }}
        </button>
      </form>

      <section class="border border-slate-200 bg-white p-5" aria-labelledby="schema-title">
        <h3 id="schema-title" class="font-semibold text-slate-900">字段模板</h3>
        <dl class="mt-4 space-y-4 text-sm">
          <div v-for="field in currentFields" :key="field.name" class="border-b border-slate-100 pb-3 last:border-0">
            <dt class="flex items-center justify-between gap-3">
              <code class="text-xs font-semibold text-slate-800">{{ field.name }}</code>
              <span v-if="field.required" class="text-xs text-red-600">必填</span>
              <span v-else class="text-xs text-slate-400">可选</span>
            </dt>
            <dd class="mt-1 text-xs text-slate-500">{{ field.label }}</dd>
          </div>
        </dl>
      </section>
    </div>

    <section v-if="result" class="border border-slate-200 bg-white" aria-labelledby="result-title">
      <div class="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="result-title" class="font-semibold text-slate-900">导入结果</h3>
          <p class="mt-1 text-sm text-slate-500">{{ result.fileName }}</p>
        </div>
        <span class="w-fit rounded px-2.5 py-1 text-xs font-medium" :class="resultBadgeClass">
          {{ resultStatusLabel }}
        </span>
      </div>
      <div class="grid grid-cols-3 divide-x divide-slate-200 border-b border-slate-200">
        <div class="px-5 py-4">
          <p class="text-xs text-slate-500">总行数</p>
          <p class="mt-1 text-xl font-semibold tabular-nums">{{ result.totalRows }}</p>
        </div>
        <div class="px-5 py-4">
          <p class="text-xs text-slate-500">成功</p>
          <p class="mt-1 text-xl font-semibold text-emerald-700 tabular-nums">{{ result.createdRows }}</p>
        </div>
        <div class="px-5 py-4">
          <p class="text-xs text-slate-500">失败</p>
          <p class="mt-1 text-xl font-semibold text-red-700 tabular-nums">{{ result.failedRows }}</p>
        </div>
      </div>
      <div v-if="result.errors.length" class="overflow-x-auto">
        <table class="w-full min-w-[600px] text-left text-sm">
          <thead class="bg-slate-50 text-xs text-slate-500">
            <tr><th class="w-20 px-5 py-3">行号</th><th class="w-56 px-5 py-3">错误代码</th><th class="px-5 py-3">说明</th></tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="error in result.errors" :key="`${error.row}-${error.code}`">
              <td class="px-5 py-3 tabular-nums">{{ error.row }}</td>
              <td class="px-5 py-3 font-mono text-xs text-slate-600">{{ error.code }}</td>
              <td class="px-5 py-3 text-slate-600">{{ error.message }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { FileUp, LoaderCircle, Upload } from "lucide-vue-next"

import type { ImportResult } from "~/types/catalog"

const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()

const entityType = ref<"MATERIAL" | "SUPPLIER">("MATERIAL")
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const formError = ref("")
const result = ref<ImportResult | null>(null)

const entityOptions = [
  { value: "MATERIAL" as const, label: "物料" },
  { value: "SUPPLIER" as const, label: "供应商" },
]
const materialFields = [
  { name: "externalCode", label: "物料编码", required: true },
  { name: "name", label: "物料名称", required: true },
  { name: "baseUnit", label: "基础单位", required: true },
  { name: "specification", label: "规格", required: false },
  { name: "category", label: "分类", required: false },
  { name: "safetyStockQty", label: "安全库存", required: false },
  { name: "leadTimeDays", label: "参考交期天数", required: false },
]
const supplierFields = [
  { name: "externalCode", label: "供应商编码", required: true },
  { name: "name", label: "供应商名称", required: true },
  { name: "website", label: "官网地址", required: false },
  { name: "country", label: "国家或地区", required: false },
]

const currentFields = computed(() => entityType.value === "MATERIAL" ? materialFields : supplierFields)
const resultStatusLabel = computed(() => ({
  SUCCEEDED: "导入成功",
  SUCCEEDED_WITH_ERRORS: "部分成功",
  FAILED: "导入失败",
}[result.value?.status || "FAILED"]))
const resultBadgeClass = computed(() => {
  if (result.value?.status === "SUCCEEDED") return "bg-emerald-50 text-emerald-700"
  if (result.value?.status === "SUCCEEDED_WITH_ERRORS") return "bg-amber-50 text-amber-700"
  return "bg-red-50 text-red-700"
})

function selectFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
  result.value = null
  formError.value = ""
}

async function submitImport() {
  if (!selectedFile.value) return
  uploading.value = true
  formError.value = ""
  result.value = null
  try {
    const body = new FormData()
    body.append("entityType", entityType.value)
    body.append("file", selectedFile.value)
    result.value = await request<ImportResult>("/api/v1/imports", { method: "POST", body })
    emit("changed")
  } catch (error) {
    formError.value = errorMessage(error, "导入失败，请检查文件格式。")
  } finally {
    uploading.value = false
  }
}
</script>
