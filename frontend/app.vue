<template>
  <main class="min-h-screen bg-panel text-ink">
    <div class="mx-auto flex min-h-screen w-full max-w-7xl">
      <aside class="hidden w-64 shrink-0 border-r border-slate-200 bg-white px-5 py-6 lg:block">
        <p class="text-sm font-semibold uppercase tracking-wide text-accent">Aipaqu</p>
        <h1 class="mt-2 text-xl font-semibold">情报报告平台</h1>
        <nav class="mt-8 space-y-1 text-sm">
          <a class="block rounded-md bg-slate-100 px-3 py-2 font-medium" href="#">Dashboard</a>
          <a class="block rounded-md px-3 py-2 text-slate-600" href="#">采集工作台</a>
          <a class="block rounded-md px-3 py-2 text-slate-600" href="#">报告中心</a>
          <a class="block rounded-md px-3 py-2 text-slate-600" href="#">系统配置</a>
        </nav>
      </aside>

      <section class="flex-1 px-5 py-6 md:px-8">
        <header class="flex flex-col gap-4 border-b border-slate-200 pb-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p class="text-sm text-slate-500">MVP 工作台</p>
            <h2 class="mt-1 text-2xl font-semibold">可追溯报告生产闭环</h2>
          </div>
          <button
            class="h-10 rounded-md bg-accent px-4 text-sm font-medium text-white disabled:opacity-60"
            :disabled="!currentUser"
            @click="focusBriefForm"
          >
            新建 ResearchBrief
          </button>
        </header>

        <div class="grid gap-4 py-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section class="space-y-4">
            <div class="grid gap-4 md:grid-cols-3">
              <section
                v-for="metric in metrics"
                :key="metric.label"
                class="rounded-md border border-slate-200 bg-white p-4"
              >
                <p class="text-sm text-slate-500">{{ metric.label }}</p>
                <p class="mt-2 text-2xl font-semibold">{{ metric.value }}</p>
                <p class="mt-1 text-sm text-slate-500">{{ metric.hint }}</p>
              </section>
            </div>

            <section class="rounded-md border border-slate-200 bg-white">
              <div class="border-b border-slate-200 px-4 py-3">
                <h3 class="font-semibold">实施阶段</h3>
              </div>
              <ol class="divide-y divide-slate-200">
                <li
                  v-for="item in roadmap"
                  :key="item.title"
                  class="flex flex-col gap-2 px-4 py-4 md:flex-row md:items-center md:justify-between"
                >
                  <div>
                    <p class="font-medium">{{ item.title }}</p>
                    <p class="mt-1 text-sm text-slate-500">{{ item.description }}</p>
                  </div>
                  <span class="w-fit rounded-md px-2.5 py-1 text-sm" :class="item.className">
                    {{ item.status }}
                  </span>
                </li>
              </ol>
            </section>

            <section class="rounded-md border border-slate-200 bg-white p-4">
              <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <h3 class="font-semibold">采集需求工作台</h3>
                  <p class="mt-1 text-sm text-slate-500">
                    先建立 ResearchBrief，后续上传资料和运行报告任务都会挂在这里。
                  </p>
                </div>
                <span class="rounded-md bg-slate-100 px-2.5 py-1 text-sm text-slate-600">
                  {{ briefs.length }} 个 Brief
                </span>
              </div>

              <form
                ref="briefFormElement"
                class="mt-4 grid gap-3 md:grid-cols-2"
                @submit.prevent="createBrief"
              >
                <label class="block text-sm md:col-span-2">
                  <span class="font-medium">标题</span>
                  <input
                    v-model="briefForm.title"
                    class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                    :disabled="!currentUser"
                    maxlength="120"
                  >
                </label>
                <label class="block text-sm md:col-span-2">
                  <span class="font-medium">目标说明</span>
                  <textarea
                    v-model="briefForm.objective"
                    class="mt-1 min-h-24 w-full rounded-md border border-slate-300 px-3 py-2"
                    :disabled="!currentUser"
                    maxlength="2000"
                  />
                </label>
                <label class="block text-sm">
                  <span class="font-medium">日期模式</span>
                  <select
                    v-model="briefForm.dateKind"
                    class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                    :disabled="!currentUser"
                  >
                    <option value="DAY">单日</option>
                    <option value="WEEK">自然周</option>
                    <option value="MONTH">自然月</option>
                  </select>
                </label>
                <label class="block text-sm">
                  <span class="font-medium">参考日期</span>
                  <input
                    v-model="briefForm.referenceDate"
                    class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                    :disabled="!currentUser"
                    type="date"
                  >
                </label>
                <label class="block text-sm md:col-span-2">
                  <span class="font-medium">必答问题</span>
                  <input
                    v-model="briefForm.requiredQuestion"
                    class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                    :disabled="!currentUser"
                    placeholder="例如：本周市场最重要的变化是什么？"
                  >
                </label>
                <p v-if="briefError" class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700 md:col-span-2">
                  {{ briefError }}
                </p>
                <button
                  class="h-10 rounded-md bg-accent px-4 text-sm font-medium text-white disabled:opacity-60 md:col-span-2"
                  :disabled="!currentUser || briefLoading"
                  type="submit"
                >
                  {{ briefLoading ? "创建中..." : "创建 Brief" }}
                </button>
              </form>

              <div class="mt-5 divide-y divide-slate-200 rounded-md border border-slate-200">
                <div v-if="briefs.length === 0" class="px-4 py-5 text-sm text-slate-500">
                  {{ currentUser ? "还没有 Brief，创建一个开始。" : "登录后可以创建 Brief。" }}
                </div>
                <article
                  v-for="brief in briefs"
                  :key="brief.id"
                  class="px-4 py-3"
                >
                  <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p class="font-medium">{{ brief.title }}</p>
                      <p class="mt-1 text-sm text-slate-500">{{ brief.objective }}</p>
                    </div>
                    <span class="w-fit rounded-md bg-slate-100 px-2.5 py-1 text-sm text-slate-600">
                      {{ brief.status }}
                    </span>
                  </div>
                </article>
              </div>
            </section>
          </section>

          <section class="rounded-md border border-slate-200 bg-white p-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <h3 class="font-semibold">账号会话</h3>
                <p class="mt-1 text-sm text-slate-500">后端地址：{{ apiBase }}</p>
              </div>
              <span class="rounded-md px-2.5 py-1 text-sm" :class="sessionBadgeClass">
                {{ sessionLabel }}
              </span>
            </div>

            <div v-if="currentUser" class="mt-5 space-y-3">
              <div class="rounded-md bg-slate-50 p-3 text-sm">
                <p class="font-medium">{{ currentUser.email }}</p>
                <p class="mt-1 text-slate-500">
                  {{ currentUser.role }} / workspace {{ currentUser.workspaceId }}
                </p>
              </div>
              <button
                class="h-10 w-full rounded-md border border-slate-300 text-sm font-medium"
                type="button"
                @click="logout"
              >
                退出登录
              </button>
            </div>

            <form v-else class="mt-5 space-y-3" @submit.prevent="login">
              <label class="block text-sm">
                <span class="font-medium">邮箱</span>
                <input
                  v-model="loginForm.email"
                  class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                  autocomplete="username"
                  type="email"
                >
              </label>
              <label class="block text-sm">
                <span class="font-medium">密码</span>
                <input
                  v-model="loginForm.password"
                  class="mt-1 h-10 w-full rounded-md border border-slate-300 px-3"
                  autocomplete="current-password"
                  type="password"
                >
              </label>
              <p v-if="authError" class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {{ authError }}
              </p>
              <button
                class="h-10 w-full rounded-md bg-accent text-sm font-medium text-white disabled:opacity-60"
                :disabled="authLoading"
                type="submit"
              >
                {{ authLoading ? "登录中..." : "登录开发账号" }}
              </button>
              <p class="text-xs text-slate-500">
                默认开发账号：admin@example.com / change-me-now
              </p>
            </form>
          </section>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
type PublicUser = {
  id: string
  email: string
  role: "ADMIN" | "EDITOR"
  workspaceId: string
}

type UserEnvelope = {
  user: PublicUser
}

type DateRangeKind = "DAY" | "WEEK" | "MONTH"

type ResearchBrief = {
  id: string
  workspaceId: string
  title: string
  objective: string
  requiredQuestions: string[]
  dateRange: {
    kind: DateRangeKind
    referenceDate: string | null
    startDate: string | null
    endDate: string | null
    timezone: string
  }
  status: "DRAFT" | "READY" | "ARCHIVED"
  createdAt: string
  updatedAt: string
}

type BriefListEnvelope = {
  data: ResearchBrief[]
}

const config = useRuntimeConfig()
const apiBase = config.public.apiBase
const authLoading = ref(false)
const authError = ref("")
const currentUser = ref<PublicUser | null>(null)
const briefs = ref<ResearchBrief[]>([])
const briefLoading = ref(false)
const briefError = ref("")
const briefFormElement = ref<HTMLFormElement | null>(null)
const loginForm = reactive({
  email: "admin@example.com",
  password: "change-me-now",
})
const briefForm = reactive({
  title: "新能源汽车行业周报",
  objective: "分析价格、销量、政策和重点企业动态",
  dateKind: "WEEK" as DateRangeKind,
  referenceDate: new Date().toISOString().slice(0, 10),
  requiredQuestion: "本周市场最重要的变化是什么？",
})

const sessionLabel = computed(() => currentUser.value ? "已登录" : "未登录")
const sessionBadgeClass = computed(() => currentUser.value
  ? "bg-emerald-50 text-accent"
  : "bg-amber-50 text-warning")

async function request<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}) {
  return await $fetch<T>(`${apiBase}${path}`, {
    credentials: "include",
    ...options,
  })
}

async function refreshCurrentUser() {
  try {
    const result = await request<UserEnvelope>("/api/v1/auth/me")
    currentUser.value = result.user
    await refreshBriefs()
  } catch {
    currentUser.value = null
    briefs.value = []
  }
}

async function refreshBriefs() {
  if (!currentUser.value) {
    briefs.value = []
    return
  }
  const result = await request<BriefListEnvelope>("/api/v1/briefs")
  briefs.value = result.data
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
    await refreshBriefs()
  } catch {
    authError.value = "登录失败，请检查账号和密码。"
  } finally {
    authLoading.value = false
  }
}

async function logout() {
  await request<void>("/api/v1/auth/logout", { method: "POST" })
  currentUser.value = null
  briefs.value = []
}

onMounted(refreshCurrentUser)

function focusBriefForm() {
  briefFormElement.value?.scrollIntoView({ behavior: "smooth", block: "start" })
}

async function createBrief() {
  if (!currentUser.value) {
    briefError.value = "请先登录。"
    return
  }
  briefLoading.value = true
  briefError.value = ""
  try {
    await request<ResearchBrief>("/api/v1/briefs", {
      method: "POST",
      body: {
        title: briefForm.title,
        objective: briefForm.objective,
        requiredQuestions: [briefForm.requiredQuestion],
        dateRange: {
          kind: briefForm.dateKind,
          referenceDate: briefForm.referenceDate,
          timezone: "Asia/Shanghai",
        },
      },
    })
    await refreshBriefs()
  } catch {
    briefError.value = "创建 Brief 失败，请检查字段是否完整。"
  } finally {
    briefLoading.value = false
  }
}

const metrics = computed(() => [
  { label: "采集需求", value: String(briefs.value.length), hint: currentUser.value ? "已创建 Brief 数量" : "登录后创建 Brief" },
  { label: "报告任务", value: "0", hint: "MVP 工作流待接入" },
  { label: "待处理挑战", value: "0", hint: "验证码/登录/授权人工接管" },
])

const roadmap = [
  {
    title: "可运行基础",
    description: "FastAPI、Nuxt、Docker Compose、健康检查、开发登录",
    status: "进行中",
    className: "bg-emerald-50 text-accent",
  },
  {
    title: "采集需求工作台",
    description: "ResearchBrief、上传资料、运行前校验",
    status: "下一步",
    className: "bg-slate-100 text-slate-600",
  },
  {
    title: "报告工作流",
    description: "带引用草稿、人工审核、Markdown/DOCX 导出",
    status: "待开始",
    className: "bg-slate-100 text-slate-600",
  },
]
</script>
