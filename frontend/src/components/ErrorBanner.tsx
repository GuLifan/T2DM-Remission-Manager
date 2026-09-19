/**
 * 组件名称：ErrorBanner.tsx
 * 所属层级：通用组件（components）
 * 功能说明：错误提示条。必须给出自然语言原因与可执行动作（UI.md 3.9 / 8.1 禁止静默失败）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface ErrorBannerProps {
  /** 错误原因（后端返回的自然语言说明） */
  message: string
  /** 可执行动作，如"重试" */
  action?: React.ReactNode
}

/** 错误提示条。 */
export default function ErrorBanner({ message, action }: ErrorBannerProps) {
  if (!message) return null
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      {action}
    </div>
  )
}
