/**
 * 组件名称：ActionBar.tsx
 * 所属层级：通用组件（components）
 * 功能说明：底部动作条。承载当前步骤的主按钮与次按钮，
 *   是"下一步去哪一目了然"的落地位置（UI.md 4.1 硬约束）。
 *
 * 约束：一个界面最多一个主按钮，由调用方保证（这里不做数量校验）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface ActionBarProps {
  /** 左侧说明（可选，例如"缺省按 12 周计算"） */
  note?: string
  /** 动作按钮（右侧排列） */
  children: React.ReactNode
}

/** 底部动作条：主按钮放最右。 */
export default function ActionBar({ note, children }: ActionBarProps) {
  return (
    <div className="action-bar">
      {note ? <span className="action-bar__note">{note}</span> : null}
      <div className="action-bar__spacer" />
      {children}
    </div>
  )
}
