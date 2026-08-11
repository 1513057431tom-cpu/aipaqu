export function useApiClient() {
  const config = useRuntimeConfig()
  const apiBase = config.public.apiBase

  async function request<T>(path: string, options: Parameters<typeof $fetch<T>>[1] = {}) {
    return await $fetch<T>(`${apiBase}${path}`, {
      credentials: "include",
      ...options,
    })
  }

  function errorMessage(error: unknown, fallback: string): string {
    if (
      typeof error === "object"
      && error !== null
      && "data" in error
      && typeof error.data === "object"
      && error.data !== null
      && "error" in error.data
      && typeof error.data.error === "object"
      && error.data.error !== null
      && "message" in error.data.error
      && typeof error.data.error.message === "string"
    ) {
      return error.data.error.message
    }
    return fallback
  }

  return { apiBase, request, errorMessage }
}
