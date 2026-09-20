/**
 * 文件名称：useAsync.ts
 * 所属层级：自定义 Hook（hooks）
 * 功能说明：统一处理"加载中 / 失败 / 成功"三种状态的数据获取。
 *
 * 为什么要统一：V0.1 各页面各自写 loading/error 处理，导致有的页面请求悬挂时不提示、
 * 有的页面前端组件卸载后仍 setState。本 Hook 统一处理取消与错误文案。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'

interface AsyncState<T> {
  data: T | null
  loading: boolean
  /** 失败原因（医生可读自然语言）；无错误时为空字符串 */
  error: string
  /** 手动重新加载 */
  reload: () => void
}

/**
 * 加载异步数据。
 *
 * @param loader 接收 AbortSignal 的加载函数（组件卸载时会被中止）
 * @param deps 依赖数组（变化时重新加载）
 */
export function useAsync<T>(loader: (signal: AbortSignal) => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tick, setTick] = useState(0)

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(loader, deps)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    run(controller.signal)
      .then((result) => {
        // 组件已卸载或被取消：不再写入状态
        if (!controller.signal.aborted) setData(result)
      })
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return
        setError(caught instanceof ApiError ? caught.message : '加载失败，请重试。')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [run, tick])

  const reload = useCallback(() => setTick((value) => value + 1), [])
  return { data, loading, error, reload }
}
