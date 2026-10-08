interface ApiError {
  data?: {
    error?: {
      message?: string
    }
  }
  message?: string
}

export function useApi() {
  const get = <T>(url: string, query?: Record<string, string | number | undefined>) =>
    $fetch<T>(url, { query })

  const errorMessage = (error: unknown) => {
    const apiError = error as ApiError
    return apiError.data?.error?.message || apiError.message || '请求失败，请稍后重试'
  }

  return { get, errorMessage }
}
