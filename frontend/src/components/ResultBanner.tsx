/**
 * 组件名称：ResultBanner.tsx
 * 所属层级：通用组件（components）
 * 功能说明：系统结论提示区。展示医生实际看到的自然语言结论、原因与下一步
 *   （对应 FR-0-01：前台只出现自然语言，不出现状态代码、规则 ID、字段 ID）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import type { Tone } from './tone'

interface ResultBannerProps {
  /** 结论正文（锁定文案，逐字展示） */
  text: string
  /** 语义色调，决定提示区配色 */
  tone?: Tone
  /** 标题（默认"系统提示"） */
  title?: string
}

/** 结论提示区：不使用大色块铺底，只按语义轻微着色。 */
export default function ResultBanner({ text, tone = 'neutral', title = '系统提示' }: ResultBannerProps) {
  if (!text) return null
  return (
    <div className={`result-banner result-banner--${tone}`} role="status">
      <span className="result-banner__title">{title}</span>
      <p className="result-banner__text">{text}</p>
    </div>
  )
}
