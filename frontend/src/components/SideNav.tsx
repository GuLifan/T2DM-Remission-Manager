/**
 * 组件名称：SideNav.tsx
 * 所属层级：通用组件（components）
 * 功能说明：左侧流程导航。全应用**唯一**的流程进度表达位置（UI.md 4.1 硬约束）。
 *
 * 与 V0.1 的差异（针对实测缺陷的修正）：
 *   1. 已完成单元**可点击回看**（V0.1 把它们禁用，医生无法回看历史步骤）；
 *   2. 只在未到达的单元上禁用并说明原因；
 *   3. 不显示状态代码（STxx），只用自然语言标签与序号。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

export interface NavItem {
  /** 单元标识（用于回调，不展示给医生） */
  key: string
  /** 单元名称（自然语言） */
  label: string
  /** 单元序号（1 起） */
  index: number
  /** 是否为当前单元 */
  active: boolean
  /** 是否已完成（可点击回看） */
  done: boolean
  /** 是否尚未到达（禁用） */
  locked: boolean
}

interface SideNavProps {
  /** 导航项 */
  items: NavItem[]
  /** 选中回调 */
  onSelect: (key: string) => void
  /** 分组标题（默认"本次管理路径"） */
  title?: string
  /** 附加区块（如"医学依据"入口），渲染在导航下方 */
  footer?: React.ReactNode
}

/** 左侧流程导航。 */
export default function SideNav({ items, onSelect, title = '本次管理路径', footer }: SideNavProps) {
  return (
    <div className="side-nav">
      <span className="side-nav__title">{title}</span>
      {items.map((item) => {
        const className = [
          'side-nav__item',
          item.active ? 'side-nav__item--active' : '',
        ]
          .filter(Boolean)
          .join(' ')
        return (
          <button
            key={item.key}
            type="button"
            className={className}
            disabled={item.locked}
            title={item.locked ? '尚未到达该流程单元' : item.label}
            onClick={() => onSelect(item.key)}
          >
            {/* 序号位：已完成显示对勾，当前与未到显示序号 */}
            <span className="side-nav__index" aria-hidden="true">
              {item.done && !item.active ? '✓' : item.index}
            </span>
            <span>{item.label}</span>
          </button>
        )
      })}
      {footer}
    </div>
  )
}
