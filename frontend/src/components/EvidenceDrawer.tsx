/**
 * 组件名称：EvidenceDrawer.tsx
 * 所属层级：通用组件（components）
 * 功能说明：医学依据检索抽屉（UI.md 3.8）。医生按需检索共识/指南原文，结果显示出处。
 *
 * 措辞纪律（_SPEC/07 AD-07）：检索只提供依据出处，**不得**自动生成临床建议。
 * 材料未录入时给出明确占位文案，不做静默降级。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useEffect } from 'react'

import LoadingBlock from './LoadingBlock'

export interface EvidenceHit {
  /** 命中片段 */
  text: string
  /** 出处：材料名 + 页码 */
  source: string
}

interface EvidenceDrawerProps {
  /** 是否打开 */
  open: boolean
  /** 关闭回调 */
  onClose: () => void
  /** 当前检索词 */
  query: string
  /** 检索词变化 */
  onQueryChange: (value: string) => void
  /** 检索结果 */
  hits: EvidenceHit[]
  /** 是否正在检索 */
  loading?: boolean
  /** 材料尚未录入时的提示 */
  emptyHint?: string
}

/** 医学依据检索抽屉。 */
export default function EvidenceDrawer({
  open,
  onClose,
  query,
  onQueryChange,
  hits,
  loading = false,
  emptyHint = '依据材料尚未录入。请联系开发者导入共识与指南原文。',
}: EvidenceDrawerProps) {
  // Esc 关闭抽屉
  useEffect(() => {
    if (!open) return undefined
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null
  return (
    <>
      <div className="drawer__scrim" role="presentation" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="医学依据">
        <div className="drawer__header">
          <span className="drawer__title">医学依据</span>
          <button type="button" className="btn btn--text" onClick={onClose}>
            关闭依据面板
          </button>
        </div>
        <div className="drawer__body">
          <input
            className="input"
            type="search"
            value={query}
            placeholder="输入关键词，例如：缓解定义、停药时间"
            aria-label="检索医学依据"
            onChange={(event) => onQueryChange(event.target.value)}
          />
          {loading ? <LoadingBlock message="正在检索依据材料…" /> : null}
          {!loading && hits.length === 0 ? <p className="drawer__source">{emptyHint}</p> : null}
          {!loading &&
            hits.map((hit, index) => (
              <div className="drawer__result" key={`${hit.source}-${index}`}>
                <p>{hit.text}</p>
                {/* 依据必须显示出处，供医生核对（_SPEC/06 V1.0-Q-05） */}
                <span className="drawer__source">出处：{hit.source}</span>
              </div>
            ))}
        </div>
      </aside>
    </>
  )
}
