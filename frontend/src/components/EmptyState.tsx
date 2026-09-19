/**
 * 组件名称：EmptyState.tsx
 * 所属层级：通用组件（components）
 * 功能说明：空态。一句说明 + 一个明确动作（UI.md 3.9）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface EmptyStateProps {
  /** 空态说明 */
  message: string
  /** 可选动作（如"建立患者档案"） */
  action?: React.ReactNode
}

/** 空态。 */
export default function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state__title">{message}</span>
      {action}
    </div>
  )
}
