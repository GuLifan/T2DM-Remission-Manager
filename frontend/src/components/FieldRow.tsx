/**
 * 组件名称：FieldRow.tsx
 * 所属层级：通用组件（components）
 * 功能说明：表单字段行。标签必须与控件通过 htmlFor/id 关联，
 *   使点击标签即可聚焦控件，并让读屏能读出字段名（UI.md 3.3 / 8.2 强制项）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useId } from 'react'

interface FieldRowProps {
  /** 字段标签（同时作为读屏名称） */
  label: string
  /**
   * 渲染控件的函数。必须把 id 与 aria-describedby 透传到具体控件上，
   * 这样读屏能读出"字段名 + 说明 + 错误"，也保证点击标签即可聚焦控件。
   */
  children: (props: { id: string; 'aria-describedby': string | undefined }) => React.ReactNode
  /** 字段说明（口径解释） */
  hint?: string
  /** 校验错误（就地提示，不依赖后端报错） */
  error?: string
}

/** 表单字段行：标签 + 控件 + 说明/错误。 */
export default function FieldRow({ label, children, hint, error }: FieldRowProps) {
  // useId 保证同一页面内多实例的 id 不冲突
  const id = useId()
  const hintId = hint ? `${id}-hint` : undefined
  const errorId = error ? `${id}-error` : undefined
  // 把说明与错误串成 aria-describedby，读屏会一并读出
  const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined

  return (
    <div className="field-row">
      <label className="field-row__label" htmlFor={id}>
        {label}
      </label>
      {children({ id, 'aria-describedby': describedBy })}
      {hint ? (
        <span className="field-row__hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <span className="field-row__error" id={errorId} role="alert">
          {error}
        </span>
      ) : null}
    </div>
  )
}
