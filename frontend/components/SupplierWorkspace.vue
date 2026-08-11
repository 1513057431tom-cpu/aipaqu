<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-xl font-semibold text-slate-900">供应商主数据</h2>
        <p class="mt-1 text-sm text-slate-500">{{ pagination.totalItems }} 条供应商记录</p>
      </div>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800"
        type="button"
        @click="showForm = !showForm"
      >
        <X v-if="showForm" :size="17" aria-hidden="true" />
        <Plus v-else :size="17" aria-hidden="true" />
        {{ showForm ? "关闭" : "新建供应商" }}
      </button>
    </div>

    <form
      v-if="showForm"
      class="grid gap-4 border-y border-slate-200 bg-white py-5 md:grid-cols-2 xl:grid-cols-4"
      @submit.prevent="submitSupplier"
    >
      <label class="block text-sm">
        <span class="font-medium text-slate-700">供应商编码</span>
        <input v-model="form.externalCode" class="field" maxlength="80" required>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">供应商名称</span>
        <input v-model="form.name" class="field" maxlength="200" required>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">官网</span>
        <input v-model="form.website" class="field" placeholder="https://" type="url">
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">国家或地区</span>
        <input v-model="form.country" class="field" maxlength="64">
      </label>
      <div class="md:col-span-2 xl:col-span-4 xl:flex xl:justify-end">
        <button
          class="h-10 w-full rounded-md bg-emerald-700 px-5 text-sm font-medium text-white disabled:opacity-60 xl:w-auto"
          :disabled="saving"
          type="submit"
        >
          {{ saving ? "保存中..." : "保存供应商" }}
        </button>
      </div>
      <p v-if="formError" class="text-sm text-red-700 md:col-span-2 xl:col-span-4" role="alert">
        {{ formError }}
      </p>
    </form>

    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <form class="flex min-w-0 flex-1 gap-2" role="search" @submit.prevent="refreshSuppliers">
        <label class="relative min-w-0 flex-1">
          <span class="sr-only">搜索供应商</span>
          <Search class="pointer-events-none absolute left-3 top-2.5 text-slate-400" :size="18" aria-hidden="true" />
          <input
            v-model="query"
            class="h-10 w-full rounded-md border border-slate-300 bg-white pl-10 pr-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            placeholder="按编码或名称搜索"
          >
        </label>
        <button class="h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50" type="submit">
          搜索
        </button>
      </form>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium hover:bg-slate-50"
        title="刷新供应商列表"
        type="button"
        @click="refreshSuppliers"
      >
        <RefreshCw :size="17" aria-hidden="true" />
        刷新
      </button>
    </div>

    <p v-if="successMessage" class="border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-800" role="status">
      {{ successMessage }}
    </p>
    <div v-if="loadError" class="flex items-center justify-between gap-3 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
      <span>{{ loadError }}</span>
      <button class="font-medium underline" type="button" @click="refreshSuppliers">重试</button>
    </div>

    <div class="overflow-hidden border border-slate-200 bg-white">
      <div v-if="loading" class="flex h-48 items-center justify-center text-sm text-slate-500">
        <LoaderCircle class="mr-2 animate-spin" :size="18" aria-hidden="true" />
        正在加载供应商...
      </div>
      <div v-else-if="suppliers.length === 0" class="flex h-48 flex-col items-center justify-center px-6 text-center">
        <Building2 :size="30" class="text-slate-300" aria-hidden="true" />
        <p class="mt-3 text-sm font-medium text-slate-700">没有匹配的供应商</p>
        <p class="mt-1 text-sm text-slate-500">新建供应商或从 CSV 导入。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[720px] table-fixed text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
            <tr>
              <th class="w-40 px-4 py-3">编码</th>
              <th class="w-56 px-4 py-3">名称</th>
              <th class="px-4 py-3">官网</th>
              <th class="w-32 px-4 py-3">国家或地区</th>
              <th class="w-24 px-4 py-3">状态</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="supplier in suppliers" :key="supplier.id" class="hover:bg-slate-50">
              <td class="truncate px-4 py-3 font-mono text-xs text-slate-700" :title="supplier.externalCode">{{ supplier.externalCode }}</td>
              <td class="truncate px-4 py-3 font-medium text-slate-900" :title="supplier.name">{{ supplier.name }}</td>
              <td class="truncate px-4 py-3 text-slate-600">
                <a v-if="supplier.website" class="hover:text-emerald-700 hover:underline" :href="supplier.website" rel="noreferrer" target="_blank">
                  {{ supplier.website }}
                </a>
                <span v-else>-</span>
              </td>
              <td class="truncate px-4 py-3 text-slate-600">{{ supplier.country || "-" }}</td>
              <td class="px-4 py-3"><span class="status-active">启用</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Building2, LoaderCircle, Plus, RefreshCw, Search, X } from "lucide-vue-next"

import type { ListEnvelope, Supplier } from "~/types/catalog"

const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()

const suppliers = ref<Supplier[]>([])
const pagination = reactive({ page: 1, pageSize: 20, totalItems: 0, totalPages: 0 })
const query = ref("")
const loading = ref(true)
const saving = ref(false)
const showForm = ref(false)
const loadError = ref("")
const formError = ref("")
const successMessage = ref("")
const form = reactive({ externalCode: "", name: "", website: "", country: "CN" })

async function refreshSuppliers() {
  loading.value = true
  loadError.value = ""
  try {
    const result = await request<ListEnvelope<Supplier>>("/api/v1/suppliers", {
      query: { q: query.value, pageSize: 100 },
    })
    suppliers.value = result.data
    Object.assign(pagination, result.pagination)
  } catch (error) {
    loadError.value = errorMessage(error, "供应商加载失败，请稍后重试。")
  } finally {
    loading.value = false
  }
}

async function submitSupplier() {
  saving.value = true
  formError.value = ""
  successMessage.value = ""
  try {
    await request<Supplier>("/api/v1/suppliers", {
      method: "POST",
      body: { ...form, website: form.website || null },
    })
    successMessage.value = `供应商 ${form.externalCode.trim()} 已创建。`
    Object.assign(form, { externalCode: "", name: "", website: "", country: "CN" })
    showForm.value = false
    await refreshSuppliers()
    emit("changed")
  } catch (error) {
    formError.value = errorMessage(error, "供应商保存失败，请检查字段。")
  } finally {
    saving.value = false
  }
}

onMounted(refreshSuppliers)
</script>

<style scoped>
.field {
  @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}

.status-active {
  @apply inline-flex rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}
</style>
