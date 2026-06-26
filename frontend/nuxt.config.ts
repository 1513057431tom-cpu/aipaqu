export default defineNuxtConfig({
  compatibilityDate: "2026-06-26",
  css: ["~/assets/css/main.css"],
  modules: ["@nuxtjs/tailwindcss"],
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000",
    },
  },
  typescript: {
    strict: true,
    typeCheck: true,
  },
})
