<template>
  <main class="min-h-screen bg-slate-50 text-slate-900">
    <div v-if="authChecking" class="flex min-h-screen items-center justify-center text-sm text-slate-500">
      <LoaderCircle class="mr-2 animate-spin" :size="19" aria-hidden="true" />
      正在检查会话...
    </div>

    <div v-else-if="!currentUser" class="grid min-h-screen lg:grid-cols-[minmax(320px,0.85fr)_minmax(480px,1.15fr)]">
      <section class="hidden bg-emerald-800 px-12 py-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div>
          <p class="text-xs font-semibold uppercase text-emerald-200">Aipaqu</p>
          <h1 class="mt-4 max-w-lg text-3xl font-semibold leading-tight">物料与供应情报平台</h1>
          <p class="mt-4 max-w-md text-sm leading-6 text-emerald-100">
            内部数据、外部变化信号与可解释采购建议的统一工作台。
          </p>
        </div>
        <div class="grid grid-cols-3 gap-6 border-t border-emerald-700 pt-6 text-sm">
          <div><p class="font-semibold">内部数据</p><p class="mt-1 text-emerald-200">物料与供应商</p></div>
          <div><p class="font-semibold">外部信号</p><p class="mt-1 text-emerald-200">证据与变化</p></div>
          <div><p class="font-semibold">人工决策</p><p class="mt-1 text-emerald-200">审核与追溯</p></div>
        </div>
      </section>

      <section class="flex min-h-screen items-center justify-center px-6 py-12 sm:px-10">
        <form class="w-full max-w-sm" @submit.prevent="login">
          <p class="text-xs font-semibold uppercase text-emerald-700 lg:hidden">Aipaqu</p>
          <h2 class="mt-2 text-2xl font-semibold">登录工作台</h2>
          <p class="mt-2 text-sm text-slate-500">使用工作空间账号继续</p>

          <label class="mt-7 block text-sm">
            <span class="font-medium text-slate-700">邮箱</span>
            <input
              v-model="loginForm.email"
              class="field"
              autocomplete="username"
              required
              type="email"
            >
          </label>
          <label class="mt-4 block text-sm">
            <span class="font-medium text-slate-700">密码</span>
            <input
              v-model="loginForm.password"
              class="field"
              autocomplete="current-password"
              required
              type="password"
            >
          </label>
          <p v-if="authError" class="mt-4 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
            {{ authError }}
          </p>
          <button
            class="mt-6 flex h-11 w-full items-center justify-center rounded-md bg-emerald-700 text-sm font-medium text-white hover:bg-emerald-800 disabled:opacity-60"
            :disabled="authLoading"
            type="submit"
          >
            <LoaderCircle v-if="authLoading" class="mr-2 animate-spin" :size="18" aria-hidden="true" />
            {{ authLoading ? "登录中..." : "登录" }}
          </button>
          <p class="mt-5 text-xs text-slate-400">开发账号：admin@example.com / change-me-now</p>
        </form>
      </section>
    </div>

    <div v-else class="flex min-h-screen">
      <div class="fixed inset-y-0 left-0 z-30 hidden lg:block">
        <CatalogSidebar :current-view="currentView" @logout="logout" @select="setView" />
      </div>

      <div v-if="mobileOpen" class="fixed inset-0 z-40 lg:hidden">
        <button class="absolute inset-0 bg-slate-900/40" aria-label="关闭导航" type="button" @click="mobileOpen = false" />
        <div class="relative h-full w-56 shadow-xl">
          <CatalogSidebar :current-view="currentView" @logout="logout" @select="setView" />
        </div>
      </div>

      <section class="min-w-0 flex-1 lg:pl-56">
        <header class="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div class="flex min-w-0 items-center gap-3">
            <button
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-slate-300 text-slate-600 lg:hidden"
              title="打开导航"
              type="button"
              @click="mobileOpen = true"
            >
              <Menu :size="19" aria-hidden="true" />
              <span class="sr-only">打开导航</span>
            </button>
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-slate-900">{{ currentViewLabel }}</p>
              <p class="truncate text-xs text-slate-500">workspace {{ currentUser.workspaceId }}</p>
            </div>
          </div>
          <div class="flex min-w-0 items-center gap-3">
            <div class="hidden text-right sm:block">
              <p class="max-w-48 truncate text-sm font-medium">{{ currentUser.email }}</p>
              <p class="text-xs text-slate-500">{{ currentUser.role }}</p>
            </div>
            <div class="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-800" aria-hidden="true">
              {{ userInitial }}
            </div>
          </div>
        </header>

        <div class="mx-auto w-full max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
          <section v-if="currentView === 'dashboard'" class="space-y-6">
            <div>
              <h2 class="text-xl font-semibold">供应数据概览</h2>
              <p class="mt-1 text-sm text-slate-500">{{ todayLabel }}</p>
            </div>

            <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <button
                v-for="metric in metrics"
                :key="metric.label"
                class="min-h-28 rounded-md border border-slate-200 bg-white p-4 text-left hover:border-slate-300"
                type="button"
                @click="setView(metric.view)"
              >
                <div class="flex items-center justify-between gap-3">
                  <p class="text-sm text-slate-500">{{ metric.label }}</p>
                  <component :is="metric.icon" :size="18" :class="metric.iconClass" aria-hidden="true" />
                </div>
                <p class="mt-3 text-2xl font-semibold tabular-nums">{{ summaryLoading ? "-" : metric.value }}</p>
                <p class="mt-1 text-xs text-slate-400">{{ metric.status }}</p>
              </button>
            </div>

            <div v-if="summaryError" class="flex items-center justify-between gap-4 border-l-4 border-red-600 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
              <span>{{ summaryError }}</span>
              <button class="font-medium underline" type="button" @click="refreshSummary">重试</button>
            </div>

            <div class="grid gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
              <section class="border border-slate-200 bg-white" aria-labelledby="foundation-title">
                <div class="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                  <h3 id="foundation-title" class="font-semibold">数据基础</h3>
                  <Database :size="18" class="text-slate-400" aria-hidden="true" />
                </div>
                <div class="divide-y divide-slate-100">
                  <button class="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50" type="button" @click="setView('materials')">
                    <div><p class="text-sm font-medium">物料主数据</p><p class="mt-1 text-xs text-slate-500">编码、规格、单位、安全库存与交期</p></div>
                    <div class="flex items-center gap-3"><span class="text-sm font-semibold tabular-nums">{{ materialCount }}</span><ChevronRight :size="17" class="text-slate-400" /></div>
                  </button>
                  <button class="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50" type="button" @click="setView('suppliers')">
                    <div><p class="text-sm font-medium">供应商主数据</p><p class="mt-1 text-xs text-slate-500">供应商编码、官网与所在地区</p></div>
                    <div class="flex items-center gap-3"><span class="text-sm font-semibold tabular-nums">{{ supplierCount }}</span><ChevronRight :size="17" class="text-slate-400" /></div>
                  </button>
                  <button class="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50" type="button" @click="setView('imports')">
                    <div><p class="text-sm font-medium">CSV 数据导入</p><p class="mt-1 text-xs text-slate-500">字段校验、重复编码保护与错误行反馈</p></div>
                    <div class="flex items-center gap-3"><span class="status-ready">可用</span><ChevronRight :size="17" class="text-slate-400" /></div>
                  </button>
                  <button class="flex w-full items-center justify-between gap-4 px-5 py-4 text-left hover:bg-slate-50" type="button" @click="setView('operations')">
                    <div><p class="text-sm font-medium">内部数据快照</p><p class="mt-1 text-xs text-slate-500">库存、消耗、需求与在途供应</p></div>
                    <div class="flex items-center gap-3"><span class="status-ready">可用</span><ChevronRight :size="17" class="text-slate-400" /></div>
                  </button>
                </div>
              </section>

              <section class="border border-slate-200 bg-white" aria-labelledby="pipeline-title">
                <div class="border-b border-slate-200 px-5 py-4">
                  <h3 id="pipeline-title" class="font-semibold">情报链路</h3>
                </div>
                <ol class="divide-y divide-slate-100 px-5">
                  <li v-for="stage in pipelineStages" :key="stage.label" class="flex items-center justify-between gap-3 py-4">
                    <div class="flex min-w-0 items-center gap-3">
                      <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold" :class="stage.className">{{ stage.step }}</span>
                      <span class="truncate text-sm font-medium">{{ stage.label }}</span>
                    </div>
                    <span class="text-xs text-slate-400">{{ stage.status }}</span>
                  </li>
                </ol>
              </section>
            </div>
          </section>

          <MaterialWorkspace v-else-if="currentView === 'materials'" @changed="refreshSummary" />
          <SupplierWorkspace v-else-if="currentView === 'suppliers'" @changed="refreshSummary" />
          <OperationsWorkspace v-else-if="currentView === 'operations'" @changed="refreshSummary" />
          <ImportWorkspace v-else-if="currentView === 'imports'" @changed="refreshSummary" />
          <MonitoringWorkspace v-else-if="currentView === 'monitoring'" @changed="refreshSummary" />
          <SignalWorkspace v-else />
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import {
  Activity,
  Building2,
  ChevronRight,
  ClipboardCheck,
  Database,
  LoaderCircle,
  Menu,
  PackageSearch,
} from "lucide-vue-next"

import type { ExternalSignal, ListEnvelope, Material, MonitoringSource, PublicUser, Supplier, WorkspaceView } from "~/types/catalog"

type UserEnvelope = { user: PublicUser }

const { request, errorMessage } = useApiClient()

useHead({ title: "Aipaqu | 物料与供应情报" })

const currentUser = ref<PublicUser | null>(null)
const currentView = ref<WorkspaceView>("dashboard")
const authChecking = ref(true)
const authLoading = ref(false)
const authError = ref("")
const mobileOpen = ref(false)
const summaryLoading = ref(false)
const summaryError = ref("")
const materialCount = ref(0)
const supplierCount = ref(0)
const sourceCount = ref(0)
const signalCount = ref(0)
const loginForm = reactive({ email: "admin@example.com", password: "change-me-now" })

const currentViewLabel = computed(() => ({
  dashboard: "Dashboard",
  materials: "物料",
  suppliers: "供应商",
  operations: "内部数据",
  imports: "数据导入",
  monitoring: "外部监控",
  signals: "情报信号",
}[currentView.value]))
const userInitial = computed(() => currentUser.value?.email.slice(0, 1).toUpperCase() || "A")
const todayLabel = computed(() => new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "full",
  timeZone: "Asia/Shanghai",
}).format(new Date()))
const metrics = computed(() => [
  { label: "物料", value: materialCount.value, status: "主数据", view: "materials" as const, icon: PackageSearch, iconClass: "text-emerald-700" },
  { label: "供应商", value: supplierCount.value, status: "主数据", view: "suppliers" as const, icon: Building2, iconClass: "text-sky-700" },
  { label: "外部信号", value: signalCount.value, status: sourceCount.value ? `${sourceCount.value} 个来源` : "未配置来源", view: "signals" as const, icon: Activity, iconClass: "text-amber-700" },
  { label: "采购建议", value: 0, status: "待接入", view: "dashboard" as const, icon: ClipboardCheck, iconClass: "text-slate-500" },
])
const pipelineStages = computed(() => [
  { step: 1, label: "内部数据", status: "进行中", className: "bg-emerald-100 text-emerald-800" },
  { step: 2, label: "外部定向监控", status: sourceCount.value ? "已启用" : "待配置", className: sourceCount.value ? "bg-sky-100 text-sky-800" : "bg-slate-100 text-slate-500" },
  { step: 3, label: "每日情报快照", status: "待开始", className: "bg-slate-100 text-slate-500" },
  { step: 4, label: "采购建议", status: "待开始", className: "bg-slate-100 text-slate-500" },
])

function setView(view: WorkspaceView) {
  currentView.value = view
  mobileOpen.value = false
}

async function refreshCurrentUser() {
  authChecking.value = true
  try {
    const result = await request<UserEnvelope>("/api/v1/auth/me")
    currentUser.value = result.user
    await refreshSummary()
  } catch {
    currentUser.value = null
  } finally {
    authChecking.value = false
  }
}

async function login() {
  authLoading.value = true
  authError.value = ""
  try {
    const result = await request<UserEnvelope>("/api/v1/auth/login", {
      method: "POST",
      body: loginForm,
    })
    currentUser.value = result.user
    await refreshSummary()
  } catch (error) {
    authError.value = errorMessage(error, "登录失败，请检查账号和密码。")
  } finally {
    authLoading.value = false
  }
}

async function logout() {
  await request<void>("/api/v1/auth/logout", { method: "POST" })
  currentUser.value = null
  currentView.value = "dashboard"
  mobileOpen.value = false
}

async function refreshSummary() {
  if (!currentUser.value) return
  summaryLoading.value = true
  summaryError.value = ""
  try {
    const [materials, suppliers, sources, signals] = await Promise.all([
      request<ListEnvelope<Material>>("/api/v1/materials", { query: { pageSize: 1 } }),
      request<ListEnvelope<Supplier>>("/api/v1/suppliers", { query: { pageSize: 1 } }),
      request<ListEnvelope<MonitoringSource>>("/api/v1/sources", { query: { pageSize: 1 } }),
      request<ListEnvelope<ExternalSignal>>("/api/v1/external-signals", { query: { pageSize: 1 } }),
    ])
    materialCount.value = materials.pagination.totalItems
    supplierCount.value = suppliers.pagination.totalItems
    sourceCount.value = sources.pagination.totalItems
    signalCount.value = signals.pagination.totalItems
  } catch (error) {
    summaryError.value = errorMessage(error, "数据概览加载失败。")
  } finally {
    summaryLoading.value = false
  }
}

onMounted(refreshCurrentUser)
</script>

<style scoped>
.field {
  @apply mt-1 h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100;
}

.status-ready {
  @apply rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700;
}
</style>
