/**
 * 组件名称：StatusBadge.tsx
 * 所属层级：通用组件（components）
 * 功能说明：临床状态徽章。语义色只表达临床状态，不得用作装饰（UI.md 3.4）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import type { Tone } from './tone'

interface StatusBadgeProps {
  /** 展示文本（必须是自然语言，禁止出现状态代码） */
  children: React.ReactNode
  /** 语义（默认中性） */
  tone?: Tone
}

/** 状态徽章：胶囊形，浅底深字。 */
export default function StatusBadge({ children, tone = 'neutral' }: StatusBadgeProps) {
  return <span className={`status-badge status-badge--${tone}`}>{children}</span>
}
