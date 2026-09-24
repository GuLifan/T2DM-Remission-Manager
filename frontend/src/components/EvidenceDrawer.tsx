/**
 * 组件名称：EvidenceDrawer.tsx
 * 所属层级：通用组件（components）
 * 功能说明：医学依据检索抽屉（UI.md 3.8）。打开后读取依据库状态，并按需检索原文。
 *
 * 临床与无障碍边界：
 *   - 只展示后端返回的纯文本原文与可复核出处，不生成面向患者的临床建议；
 *   - 输入达到 2 个字符后延迟检索，新输入会取消旧请求；
 *   - 打开后聚焦检索框，焦点约束在抽屉内，Esc 关闭后回到原触发按钮。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 *   - 2026-09-24  v1.1  M6-C 接入真实状态/检索接口并补齐六类状态与焦点管理
 */

import { useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import { evidenceApi } from '../api/endpoints'
import type { EvidenceSearchResult, EvidenceStatus } from '../types'
import ErrorBanner from './ErrorBanner'
import LoadingBlock from './LoadingBlock'

interface EvidenceDrawerProps {
  /** 是否打开 */
  open: boolean
  /** 关闭回调 */
  onClose: () => void
}

const SEARCH_DELAY_MS = 300
const SEARCH_LIMIT = 20
const NOT_READY_MESSAGE = '医学依据尚未完整导入，请联系系统维护人员完成本地导入。'
const FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'a[href]',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

/** 把后端页码/章节转换为医生可直接核对的出处。 */
function formatSource(item: EvidenceSearchResult['items'][number]): string {
  if (item.source_type === 'pdf' && item.page_no !== null) {
    return `${item.title} · PDF 第 ${item.page_no} 页`
  }
  if (item.section) return `${item.title} · ${item.section}`
  return item.title
}

/** 把网络或代理错误转换为医生可执行的提示；后端业务文案保持原样。 */
function readableEvidenceError(caught: unknown, action: '读取' | '检索'): string {
  if (caught instanceof ApiError) {
    if (caught.status === 0 || caught.message.startsWith('请求失败（状态码')) {
      return `暂时无法${action}医学依据，请确认后端服务已启动后重试。`
    }
    return caught.message
  }
  return `${action}医学依据失败，请重试。`
}

/** 医学依据检索抽屉。 */
export default function EvidenceDrawer({ open, onClose }: EvidenceDrawerProps) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<EvidenceStatus | null>(null)
  const [statusLoading, setStatusLoading] = useState(true)
  const [statusError, setStatusError] = useState('')
  const [statusAttempt, setStatusAttempt] = useState(0)
  const [searchResult, setSearchResult] = useState<EvidenceSearchResult | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState('')
  const [searchAttempt, setSearchAttempt] = useState(0)
  const drawerRef = useRef<HTMLElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const onCloseRef = useRef(onClose)
  const normalizedQuery = query.trim().replace(/\s+/g, ' ')

  // 避免父组件重新渲染时重装键盘监听，同时始终调用最新关闭回调。
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // 每次关闭都清空临时检索状态；再次打开时重新核对本地材料是否完整。
  useEffect(() => {
    if (open) return
    setQuery('')
    setStatus(null)
    setStatusLoading(true)
    setStatusError('')
    setSearchResult(null)
    setSearchLoading(false)
    setSearchError('')
  }, [open])

  // 对话框焦点管理：打开后聚焦检索框，Tab 不离开抽屉，关闭后回到触发按钮。
  useEffect(() => {
    if (!open) return undefined
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusTimer = window.setTimeout(() => searchInputRef.current?.focus(), 0)

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !drawerRef.current) return
      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      ).filter((element) => element.getAttribute('aria-hidden') !== 'true')
      if (focusable.length === 0) {
        event.preventDefault()
        drawerRef.current.focus()
        return
      }
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.clearTimeout(focusTimer)
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = previousOverflow
      previousFocus?.focus()
    }
  }, [open])

  // 打开抽屉先读取状态；失败时由“重新读取”显式触发下一次请求。
  useEffect(() => {
    if (!open) return undefined
    const controller = new AbortController()
    setStatusLoading(true)
    setStatusError('')
    evidenceApi
      .status(controller.signal)
      .then((result) => setStatus(result))
      .catch((caught: unknown) => {
        if (controller.signal.aborted) return
        setStatusError(readableEvidenceError(caught, '读取'))
      })
      .finally(() => {
        if (!controller.signal.aborted) setStatusLoading(false)
      })
    return () => controller.abort()
  }, [open, statusAttempt])

  // 达到输入边界后延迟检索；依赖变化时中止计时器和旧请求，防止旧结果覆盖新结果。
  useEffect(() => {
    if (!open || !status?.searchable || normalizedQuery.length < 2) {
      setSearchResult(null)
      setSearchLoading(false)
      setSearchError('')
      return undefined
    }

    const controller = new AbortController()
    setSearchResult(null)
    setSearchLoading(true)
    setSearchError('')
    const timer = window.setTimeout(() => {
      evidenceApi
        .search(normalizedQuery, SEARCH_LIMIT, controller.signal)
        .then((result) => setSearchResult(result))
        .catch((caught: unknown) => {
          if (controller.signal.aborted) return
          setSearchError(readableEvidenceError(caught, '检索'))
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearchLoading(false)
        })
    }, SEARCH_DELAY_MS)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [open, normalizedQuery, searchAttempt, status?.searchable])

  if (!open) return null

  let content: React.ReactNode
  if (statusLoading) {
    content = <LoadingBlock message="正在读取医学依据状态…" />
  } else if (statusError) {
    content = (
      <ErrorBanner
        message={statusError}
        action={
          <button type="button" className="btn btn--text" onClick={() => setStatusAttempt((value) => value + 1)}>
            重新读取
          </button>
        }
      />
    )
  } else if (!status?.searchable) {
    content = (
      <div className="drawer__state" role="status">
        <strong>{NOT_READY_MESSAGE}</strong>
        <span>
          当前已就绪 {status?.indexed_count ?? 0} / {status?.expected_count ?? 4} 份材料。
        </span>
      </div>
    )
  } else if (normalizedQuery.length === 0) {
    content = (
      <div className="drawer__state" id="evidence-search-help" role="status">
        <strong>已载入 {status.indexed_count} 份医学依据。</strong>
        <span>请输入至少 2 个字符，查阅共识、指南或临床流程锁定稿原文。</span>
      </div>
    )
  } else if (normalizedQuery.length < 2) {
    content = (
      <div className="drawer__state" id="evidence-search-help" role="status">
        <strong>请输入至少 2 个字符。</strong>
        <span>当前输入不会发送检索请求。</span>
      </div>
    )
  } else if (searchLoading) {
    content = <LoadingBlock message="正在检索医学依据…" />
  } else if (searchError) {
    content = (
      <ErrorBanner
        message={searchError}
        action={
          <button type="button" className="btn btn--text" onClick={() => setSearchAttempt((value) => value + 1)}>
            重新检索
          </button>
        }
      />
    )
  } else if (searchResult && searchResult.items.length === 0) {
    content = (
      <div className="drawer__state" role="status">
        <strong>未找到与“{searchResult.query}”匹配的原文。</strong>
        <span>可以更换关键词后再次检索；这不表示医学依据尚未导入。</span>
      </div>
    )
  } else if (searchResult) {
    content = (
      <section className="drawer__results" aria-label="医学依据检索结果">
        <p className="drawer__summary" aria-live="polite">
          找到 {searchResult.total} 条，当前显示 {searchResult.returned} 条。
        </p>
        {searchResult.items.map((item, index) => (
          <article
            className="drawer__result"
            key={`${item.evidence_id}-${item.source_key}-${item.page_no ?? item.section}-${index}`}
          >
            <p>{item.snippet}</p>
            <span className="drawer__source">出处：{formatSource(item)}</span>
          </article>
        ))}
      </section>
    )
  } else {
    content = null
  }

  return (
    <>
      <div className="drawer__scrim" aria-hidden="true" onClick={() => onCloseRef.current()} />
      <aside
        ref={drawerRef}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidence-drawer-title"
        tabIndex={-1}
      >
        <div className="drawer__header">
          <span className="drawer__title" id="evidence-drawer-title">医学依据</span>
          <button type="button" className="btn btn--text" onClick={() => onCloseRef.current()}>
            关闭依据面板
          </button>
        </div>
        <div className="drawer__body">
          <label className="drawer__search-label">
            <span>检索原始依据</span>
            <input
              ref={searchInputRef}
              className="input"
              type="search"
              value={query}
              maxLength={100}
              placeholder="例如：缓解定义、停药时间"
              aria-describedby="evidence-disclaimer"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <p className="drawer__disclaimer" id="evidence-disclaimer">
            以下内容仅供查阅原始依据，不替代医生判断。
          </p>
          {content}
        </div>
      </aside>
    </>
  )
}
