/**
 * 组件名称：LoadingBlock.tsx
 * 所属层级：通用组件（components）
 * 功能说明：加载态。用文字明确说明"正在做什么"，不使用装饰性动画（UI.md 2.7/3.9）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface LoadingBlockProps {
  /** 加载说明（如"正在读取患者信息…"） */
  message: string
}

/** 加载态。 */
export default function LoadingBlock({ message }: LoadingBlockProps) {
  return (
    <div className="loading-block" role="status" aria-live="polite">
      <span>{message}</span>
    </div>
  )
}
