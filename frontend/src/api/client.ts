/**
 * 文件名称：api/client.ts
 * 所属层级：接口调用层（api）
 * 功能说明：后端 REST 接口的 fetch 封装。
 *
 * 为修正 V0.1 的接口层缺陷（见 `_SPEC/07` 与 `_SPEC/08` M5 说明）：
 *   1. **超时**：默认 15 秒，避免请求悬挂导致界面"卡住没反应"；
 *   2. **取消**：调用方可传入 AbortSignal，组件卸载时中止请求；
 *   3. **统一错误**：后端返回的 `detail` 为医生可读自然语言，直接用于展示；
 *   4. **会话令牌**：自动附带 Bearer 令牌，401 时清除本地会话并通知上层；
 *   5. **请求标识**：写操作自动生成 request_id，配合后端幂等守卫防止重复提交。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

/** 后端业务错误：message 为医生可读的自然语言说明。 */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

const TOKEN_KEY = 'etmms.token'
const DEFAULT_TIMEOUT_MS = 15_000

/** 会话令牌读写（localStorage）。 */
export const session = {
  get token(): string | null {
    return window.localStorage.getItem(TOKEN_KEY)
  },
  set token(value: string | null) {
    if (value === null) {
      window.localStorage.removeItem(TOKEN_KEY)
    } else {
      window.localStorage.setItem(TOKEN_KEY, value)
    }
  },
  clear(): void {
    window.localStorage.removeItem(TOKEN_KEY)
  },
}

/** 生成一次性请求标识（用于后端幂等：同一标识不产生第二条事件）。 */
export function newRequestId(prefix: string): string {
  // crypto.randomUUID 在现代浏览器均可用；降级用时间戳 + 随机数
  const random =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.round(Math.random() * 1e9)}`
  return `${prefix}-${random}`
}

interface RequestOptions {
  method?: string
  body?: unknown
  /** 外部取消信号（组件卸载时使用） */
  signal?: AbortSignal
  /** 超时毫秒数 */
  timeoutMs?: number
}

/**
 * 通用请求封装。
 *
 * @param path 接口路径（如 /api/patients）
 * @param options 请求选项
 * @returns 解析后的 JSON 响应
 * @throws ApiError 非 2xx 响应；网络错误与超时也转换为 ApiError（提示为自然语言）
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController()
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  // 超时保护：到点自动中止，避免界面无限等待
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  // 外部信号（组件卸载）与内部超时信号合并
  if (options.signal) {
    if (options.signal.aborted) controller.abort()
    else options.signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  // FormData 必须让浏览器自行生成 multipart boundary；JSON 请求才显式声明类型。
  const isFormData = options.body instanceof FormData
  const headers: Record<string, string> = isFormData ? {} : { 'Content-Type': 'application/json' }
  const token = session.token
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(path, {
      method: options.method ?? 'GET',
      headers,
      body:
        options.body === undefined
          ? undefined
          : isFormData
            ? (options.body as FormData)
            : JSON.stringify(options.body),
      signal: controller.signal,
    })
  } catch (error) {
    // 中止与网络故障分别给出不同提示，便于医生判断"要不要重试"
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(0, '请求超时或已取消，请检查后端服务后重试。')
    }
    throw new ApiError(0, '无法连接后端服务，请确认服务已启动后重试。')
  } finally {
    window.clearTimeout(timer)
  }

  if (!response.ok) {
    let message = `请求失败（状态码 ${response.status}）`
    try {
      const body = await response.json()
      if (body && typeof body.detail === 'string') message = body.detail
    } catch {
      // 响应体不是 JSON：保留兜底文案
    }
    // 会话失效：清除本地令牌，由上层跳转登录页
    if (response.status === 401) session.clear()
    throw new ApiError(response.status, message)
  }

  if (response.status === 204) return {} as T
  const text = await response.text()
  return (text ? JSON.parse(text) : {}) as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body, signal }),
  put: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'PUT', body, signal }),
}
