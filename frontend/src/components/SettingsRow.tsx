/**
 * 组件名称：SettingsRow.tsx
 * 所属层级：通用组件（components）
 * 功能说明：行式设置项（Chrome 设置页的基本单元）：左侧标签、右侧控件、下方说明。
 *   一行只表达一个临床信息（UI.md 3.2）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

interface SettingsRowProps {
  /** 标签文本 */
  label: string
  /** 控件（输入框、下拉框、开关等） */
  control: React.ReactNode
  /** 说明文字（仅在需要解释判定口径时提供） */
  description?: string
  /** 纵向排列（控件较宽时使用） */
  stacked?: boolean
}

/** 行式设置项。 */
export default function SettingsRow({ label, control, description, stacked = false }: SettingsRowProps) {
  return (
    <div className={stacked ? 'settings-row settings-row--stacked' : 'settings-row'}>
      <div>
        <div className="settings-row__label">{label}</div>
        {description ? <div className="settings-row__description">{description}</div> : null}
      </div>
      <div className="settings-row__control">{control}</div>
    </div>
  )
}
