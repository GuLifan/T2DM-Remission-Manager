/**
 * 组件名称：TaskPanel.tsx
 * 所属层级：通用组件（components）
 * 功能说明：承载每页唯一的一级焦点，明确“现在要做什么”与当前结论。
 *
 * 设计依据：`UI.md` 1.3–1.5。任务面板常驻内容区顶部，并使用
 * `--etmms-text-task-title`，不得与二级决策卡片同权。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  第一批测试可用性补齐既有 UI 门禁
 */

interface TaskPanelProps {
  /** 当前任务标题；每页只允许一处 */
  title: string
  /** 对医生说明本页应该完成的事情 */
  description: string
  /** 可选的当前结论或状态补充 */
  children?: React.ReactNode
}

/** 页面一级任务面板。 */
export default function TaskPanel({ title, description, children }: TaskPanelProps) {
  return (
    <section className="task-panel" aria-labelledby="current-task-title">
      <h2 className="task-panel__title" id="current-task-title">
        {title}
      </h2>
      <p className="task-panel__description">{description}</p>
      {children ? <div className="task-panel__result">{children}</div> : null}
    </section>
  )
}
