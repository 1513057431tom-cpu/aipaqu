<template>
  <div class="space-y-5">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-xl font-semibold text-slate-900">物料主数据</h2>
        <p class="mt-1 text-sm text-slate-500">{{ pagination.totalItems }} 条物料记录，{{ groups.length }} 个分组</p>
      </div>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 text-sm font-medium text-white hover:bg-emerald-800"
        type="button"
        @click="toggleCreateForm"
      >
        <X v-if="showForm" :size="17" aria-hidden="true" />
        <Plus v-else :size="17" aria-hidden="true" />
        {{ showForm ? "关闭" : "新建物料" }}
      </button>
    </div>

    <form
      v-if="showForm"
      class="grid gap-4 border-y border-slate-200 bg-white py-5 md:grid-cols-2 xl:grid-cols-4"
      @submit.prevent="submitMaterial"
    >
      <div class="md:col-span-2 xl:col-span-4">
        <h3 class="font-semibold text-slate-900">{{ editingId ? "编辑物料" : "新建物料" }}</h3>
        <p v-if="editingId" class="mt-1 text-xs text-slate-500">修改会更新当前主数据，不改写已有库存和报告快照。</p>
      </div>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">物料编码</span>
        <input v-model="form.externalCode" class="field" maxlength="80" required>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">物料名称</span>
        <input v-model="form.name" class="field" maxlength="200" required>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">规格</span>
        <input v-model="form.specification" class="field" maxlength="500">
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">所属分组</span>
        <select v-model="form.groupId" class="field">
          <option value="">未分组</option>
          <option v-for="item in flatGroups" :key="item.group.id" :value="item.group.id">
            {{ "　".repeat(item.depth) }}{{ item.group.name }}
          </option>
        </select>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">辅助标签</span>
        <input v-model="form.category" class="field" maxlength="120">
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">基础单位</span>
        <input v-model="form.baseUnit" class="field" maxlength="32" required>
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">安全库存</span>
        <input v-model.number="form.safetyStockQty" class="field" min="0" step="any" type="number">
      </label>
      <label class="block text-sm">
        <span class="font-medium text-slate-700">参考交期（天）</span>
        <input v-model.number="form.leadTimeDays" class="field" max="3650" min="0" type="number">
      </label>
      <div class="flex items-end">
        <button
          class="h-10 w-full rounded-md bg-emerald-700 px-4 text-sm font-medium text-white disabled:opacity-60"
          :disabled="saving"
          type="submit"
        >
          {{ saving ? "保存中..." : editingId ? "保存修改" : "保存物料" }}
        </button>
      </div>
      <p v-if="formError" class="text-sm text-red-700 md:col-span-2 xl:col-span-4" role="alert">
        {{ formError }}
      </p>
    </form>

    <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
      <form class="flex min-w-0 flex-1 gap-2" role="search" @submit.prevent="refreshMaterials">
        <label class="relative min-w-0 flex-1">
          <span class="sr-only">搜索物料</span>
          <Search class="pointer-events-none absolute left-3 top-2.5 text-slate-400" :size="18" aria-hidden="true" />
          <input
            v-model="query"
            class="h-10 w-full rounded-md border border-slate-300 bg-white pl-10 pr-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
            placeholder="按编码、名称或规格搜索"
          >
        </label>
        <button class="h-10 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium hover:bg-slate-50" type="submit">
          搜索
        </button>
      </form>
      <button
        class="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium hover:bg-slate-50"
        title="刷新物料列表"
        type="button"
        @click="refreshMaterials"
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
      <button class="font-medium underline" type="button" @click="refreshMaterials">重试</button>
    </div>

    <div class="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside class="border border-slate-200 bg-white" aria-label="物料分组">
        <div class="flex h-12 items-center justify-between border-b border-slate-200 px-4">
          <h3 class="text-sm font-semibold">物料分组</h3>
          <button class="icon-button" title="新建分组" type="button" @click="showGroupForm = !showGroupForm">
            <FolderPlus :size="16" aria-hidden="true" />
            <span class="sr-only">新建分组</span>
          </button>
        </div>
        <form v-if="showGroupForm" class="space-y-3 border-b border-slate-200 bg-slate-50 p-3" @submit.prevent="createGroup">
          <input v-model="groupForm.code" class="compact-field" maxlength="80" placeholder="分组编码" required>
          <input v-model="groupForm.name" class="compact-field" maxlength="120" placeholder="分组名称" required>
          <select v-model="groupForm.parentId" class="compact-field">
            <option value="">顶级分组</option>
            <option v-for="item in flatGroups" :key="item.group.id" :value="item.group.id">
              {{ "　".repeat(item.depth) }}{{ item.group.name }}
            </option>
          </select>
          <button class="h-9 w-full rounded-md bg-emerald-700 text-sm font-medium text-white" :disabled="groupSaving" type="submit">
            {{ groupSaving ? "保存中..." : "保存分组" }}
          </button>
          <p v-if="groupError" class="text-xs text-red-700" role="alert">{{ groupError }}</p>
        </form>
        <div class="p-2">
          <button
            class="group-row"
            :class="selectedGroupId === '' ? 'bg-emerald-50 text-emerald-800' : 'text-slate-700 hover:bg-slate-50'"
            type="button"
            @click="selectedGroupId = ''"
          >
            <span class="flex min-w-0 items-center gap-2"><Boxes :size="16" /><span class="truncate">全部物料</span></span>
            <span class="text-xs tabular-nums text-slate-400">{{ pagination.totalItems }}</span>
          </button>
          <button
            v-for="item in flatGroups"
            :key="item.group.id"
            class="group-row"
            :class="selectedGroupId === item.group.id ? 'bg-emerald-50 text-emerald-800' : 'text-slate-700 hover:bg-slate-50'"
            :style="{ paddingLeft: `${12 + item.depth * 18}px` }"
            type="button"
            @click="selectedGroupId = item.group.id"
          >
            <span class="flex min-w-0 items-center gap-2"><Folder :size="16" /><span class="truncate">{{ item.group.name }}</span></span>
            <span class="text-xs tabular-nums text-slate-400">{{ groupMaterialCount(item.group.id) }}</span>
          </button>
          <p v-if="groups.length === 0" class="px-3 py-5 text-center text-xs text-slate-400">尚未创建分组</p>
        </div>
      </aside>

      <div class="overflow-hidden border border-slate-200 bg-white">
      <div v-if="loading" class="flex h-48 items-center justify-center text-sm text-slate-500">
        <LoaderCircle class="mr-2 animate-spin" :size="18" aria-hidden="true" />
        正在加载物料...
      </div>
      <div v-else-if="visibleMaterials.length === 0" class="flex h-48 flex-col items-center justify-center px-6 text-center">
        <PackageOpen :size="30" class="text-slate-300" aria-hidden="true" />
        <p class="mt-3 text-sm font-medium text-slate-700">没有匹配的物料</p>
        <p class="mt-1 text-sm text-slate-500">新建物料或从 CSV 导入。</p>
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[960px] table-fixed text-left text-sm">
          <thead class="border-b border-slate-200 bg-slate-50 text-xs font-medium text-slate-500">
            <tr>
              <th class="w-36 px-4 py-3">编码</th>
              <th class="w-48 px-4 py-3">名称</th>
              <th class="px-4 py-3">规格</th>
              <th class="w-28 px-4 py-3">分组</th>
              <th class="w-24 px-4 py-3 text-right">安全库存</th>
              <th class="w-24 px-4 py-3 text-right">交期</th>
              <th class="w-24 px-4 py-3">状态</th>
              <th class="w-16 px-4 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-for="material in visibleMaterials" :key="material.id" class="hover:bg-slate-50">
              <td class="truncate px-4 py-3 font-mono text-xs text-slate-700" :title="material.externalCode">{{ material.externalCode }}</td>
              <td class="truncate px-4 py-3 font-medium text-slate-900" :title="material.name">{{ material.name }}</td>
              <td class="truncate px-4 py-3 text-slate-600" :title="material.specification">{{ material.specification || "-" }}</td>
              <td class="truncate px-4 py-3 text-slate-600" :title="groupName(material.groupId)">{{ groupName(material.groupId) }}</td>
              <td class="px-4 py-3 text-right tabular-nums">{{ formatQuantity(material.safetyStockQty) }} {{ material.baseUnit }}</td>
              <td class="px-4 py-3 text-right tabular-nums">{{ material.leadTimeDays }} 天</td>
              <td class="px-4 py-3"><span class="status-active">启用</span></td>
              <td class="px-4 py-3 text-right">
                <button
                  class="icon-button"
                  :title="`编辑 ${material.externalCode}`"
                  type="button"
                  @click="startEditing(material)"
                >
                  <Pencil :size="16" aria-hidden="true" />
                  <span class="sr-only">编辑 {{ material.externalCode }}</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Boxes, Folder, FolderPlus, LoaderCircle, PackageOpen, Pencil, Plus, RefreshCw, Search, X } from "lucide-vue-next"

import type { ListEnvelope, Material, MaterialGroup } from "~/types/catalog"

const emit = defineEmits<{ changed: [] }>()
const { request, errorMessage } = useApiClient()

const materials = ref<Material[]>([])
const groups = ref<MaterialGroup[]>([])
const pagination = reactive({ page: 1, pageSize: 20, totalItems: 0, totalPages: 0 })
const query = ref("")
const loading = ref(true)
const saving = ref(false)
const showForm = ref(false)
const editingId = ref("")
const loadError = ref("")
const formError = ref("")
const successMessage = ref("")
const selectedGroupId = ref("")
const showGroupForm = ref(false)
const groupSaving = ref(false)
const groupError = ref("")
const groupForm = reactive({ code: "", name: "", parentId: "" })
const form = reactive({
  externalCode: "",
  name: "",
  specification: "",
  category: "",
  baseUnit: "kg",
  safetyStockQty: 0,
  leadTimeDays: 0,
  groupId: "",
})

const flatGroups = computed(() => {
  const result: { group: MaterialGroup; depth: number }[] = []
  const visit = (parentId: string | null, depth: number) => {
    groups.value
      .filter(group => group.parentId === parentId)
      .sort((left, right) => left.sortOrder - right.sortOrder || left.name.localeCompare(right.name, "zh-CN"))
      .forEach((group) => {
        result.push({ group, depth })
        visit(group.id, depth + 1)
      })
  }
  visit(null, 0)
  return result
})

const selectedGroupIds = computed(() => {
  if (!selectedGroupId.value) return new Set<string>()
  const ids = new Set([selectedGroupId.value])
  let changed = true
  while (changed) {
    changed = false
    for (const group of groups.value) {
      if (group.parentId && ids.has(group.parentId) && !ids.has(group.id)) {
        ids.add(group.id)
        changed = true
      }
    }
  }
  return ids
})

const visibleMaterials = computed(() => selectedGroupId.value
  ? materials.value.filter(material => material.groupId && selectedGroupIds.value.has(material.groupId))
  : materials.value)

async function refreshMaterials() {
  loading.value = true
  loadError.value = ""
  try {
    const [result, groupResult] = await Promise.all([
      request<ListEnvelope<Material>>("/api/v1/materials", { query: { q: query.value, pageSize: 100 } }),
      request<{ data: MaterialGroup[] }>("/api/v1/material-groups"),
    ])
    materials.value = result.data
    groups.value = groupResult.data
    Object.assign(pagination, result.pagination)
  } catch (error) {
    loadError.value = errorMessage(error, "物料加载失败，请稍后重试。")
  } finally {
    loading.value = false
  }
}

async function createGroup() {
  groupSaving.value = true
  groupError.value = ""
  try {
    await request<MaterialGroup>("/api/v1/material-groups", {
      method: "POST",
      body: {
        code: groupForm.code,
        name: groupForm.name,
        parentId: groupForm.parentId || null,
      },
    })
    Object.assign(groupForm, { code: "", name: "", parentId: "" })
    showGroupForm.value = false
    await refreshMaterials()
  } catch (error) {
    groupError.value = errorMessage(error, "分组保存失败。")
  } finally {
    groupSaving.value = false
  }
}

async function submitMaterial() {
  saving.value = true
  formError.value = ""
  successMessage.value = ""
  try {
    const isEditing = Boolean(editingId.value)
    await request<Material>(isEditing ? `/api/v1/materials/${editingId.value}` : "/api/v1/materials", {
      method: isEditing ? "PATCH" : "POST",
      body: { ...form, groupId: form.groupId || null },
    })
    successMessage.value = `物料 ${form.externalCode.trim()} 已${isEditing ? "更新" : "创建"}。`
    resetForm()
    showForm.value = false
    await refreshMaterials()
    emit("changed")
  } catch (error) {
    formError.value = errorMessage(error, "物料保存失败，请检查字段。")
  } finally {
    saving.value = false
  }
}

function toggleCreateForm() {
  if (showForm.value) {
    showForm.value = false
    resetForm()
    return
  }
  resetForm()
  showForm.value = true
}

function startEditing(material: Material) {
  editingId.value = material.id
  Object.assign(form, {
    externalCode: material.externalCode,
    name: material.name,
    specification: material.specification,
    category: material.category,
    baseUnit: material.baseUnit,
    safetyStockQty: material.safetyStockQty,
    leadTimeDays: material.leadTimeDays,
    groupId: material.groupId || "",
  })
  formError.value = ""
  successMessage.value = ""
  showForm.value = true
  window.scrollTo({ top: 0, behavior: "smooth" })
}

function resetForm() {
  editingId.value = ""
  formError.value = ""
  Object.assign(form, {
    externalCode: "",
    name: "",
    specification: "",
    category: "",
    baseUnit: "kg",
    safetyStockQty: 0,
    leadTimeDays: 0,
    groupId: "",
  })
}

function formatQuantity(value: number) {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value)
}

function groupName(groupId: string | null) {
  return groups.value.find(group => group.id === groupId)?.name || "未分组"
}

function groupMaterialCount(groupId: string) {
  const ids = new Set([groupId])
  let changed = true
  while (changed) {
    changed = false
    for (const group of groups.value) {
      if (group.parentId && ids.has(group.parentId) && !ids.has(group.id)) {
        ids.add(group.id)
        changed = true
      }
    }
  }
  return groups.value
    .filter(group => ids.has(group.id))
    .reduce((total, group) => total + group.materialCount, 0)
}

onMounted(refreshMaterials)
</script>

<style scoped>
.field {
  @apply mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}

.status-active {
  @apply inline-flex rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}

.icon-button {
  @apply inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 text-slate-600 hover:bg-slate-100 hover:text-slate-900;
}

.compact-field {
  @apply h-9 w-full rounded-md border border-slate-300 bg-white px-2.5 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}

.group-row {
  @apply flex h-9 w-full items-center justify-between gap-2 rounded-md px-3 text-left text-sm;
}
</style>
