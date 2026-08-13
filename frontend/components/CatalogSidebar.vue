<template>
  <aside class="flex h-full w-56 flex-col border-r border-slate-200 bg-white">
    <div class="border-b border-slate-200 px-5 py-5">
      <p class="text-xs font-semibold uppercase text-emerald-700">Aipaqu</p>
      <p class="mt-1 text-base font-semibold text-slate-900">物料与供应情报</p>
    </div>

    <nav class="flex-1 space-y-1 px-3 py-4" aria-label="主导航">
      <button
        v-for="item in activeItems"
        :key="item.key"
        class="flex h-10 w-full items-center gap-3 rounded-md px-3 text-left text-sm font-medium"
        :class="currentView === item.key
          ? 'bg-emerald-50 text-emerald-800'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'"
        type="button"
        @click="$emit('select', item.key)"
      >
        <component :is="item.icon" :size="18" aria-hidden="true" />
        {{ item.label }}
      </button>

      <div class="px-3 pb-1 pt-5 text-xs font-medium text-slate-400">后续模块</div>
      <div
        v-for="item in futureItems"
        :key="item.label"
        class="flex h-9 items-center gap-3 px-3 text-sm text-slate-400"
      >
        <component :is="item.icon" :size="17" aria-hidden="true" />
        {{ item.label }}
      </div>
    </nav>

    <div class="border-t border-slate-200 p-3">
      <button
        class="flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm text-slate-600 hover:bg-slate-100 hover:text-slate-900"
        type="button"
        @click="$emit('logout')"
      >
        <LogOut :size="18" aria-hidden="true" />
        退出登录
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import {
  Activity,
  Building2,
  ClipboardCheck,
  FileText,
  Layers3,
  LayoutDashboard,
  LogOut,
  PackageSearch,
  Radar,
  Upload,
} from "lucide-vue-next"

import type { WorkspaceView } from "~/types/catalog"

defineProps<{ currentView: WorkspaceView }>()
defineEmits<{
  select: [view: WorkspaceView]
  logout: []
}>()

const activeItems = [
  { key: "dashboard" as const, label: "Dashboard", icon: LayoutDashboard },
  { key: "materials" as const, label: "物料", icon: PackageSearch },
  { key: "suppliers" as const, label: "供应商", icon: Building2 },
  { key: "operations" as const, label: "内部数据", icon: Layers3 },
  { key: "imports" as const, label: "数据导入", icon: Upload },
  { key: "monitoring" as const, label: "外部监控", icon: Radar },
  { key: "signals" as const, label: "情报信号", icon: Activity },
  { key: "recommendations" as const, label: "采购建议", icon: ClipboardCheck },
]

const futureItems = [
  { label: "周期报告", icon: FileText },
]
</script>
