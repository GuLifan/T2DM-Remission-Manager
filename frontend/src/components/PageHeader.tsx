/**
 * 组件名称：PageHeader.tsx
 * 所属层级：通用组件（components）
 * 功能说明：页头。左侧为页面标题与患者上下文，右侧为全局入口（医学依据、账号）。
 *   页头不承载流程进度——流程进度只在左侧导航表达（UI.md 4.1/4.2 硬约束：
 *   禁止同一语义出现两套导航）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface PageHeaderProps {
  /** 页面标题 */
  title: string
  /** 患者上下文（姓名 · 住院号等），可选 */
  context?: string
  /** 右侧全局入口 */
  actions?: React.ReactNode
}

/** 页头。 */
export default function PageHeader({ title, context, actions }: PageHeaderProps) {
  return (
    <header className="page-header">
      <div className="page-header__titles">
        <span className="page-header__title">{title}</span>
        {context ? <span className="page-header__context">{context}</span> : null}
      </div>
      {actions ? <div className="page-header__actions">{actions}</div> : null}
    </header>
  )
}
