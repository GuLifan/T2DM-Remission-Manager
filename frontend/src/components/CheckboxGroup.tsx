/**
 * 组件名称：CheckboxGroup.tsx
 * 所属层级：通用组件（components）
 * 功能说明：多选组，用于**本身可并存**的临床信息（如干预组合、管理约束、风险触发信息）。
 *   ⚠️ 互斥的临床分支一律使用 ChoiceGroup（单选），不要用本组件（UI.md 3.5）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useId } from 'react'

export interface CheckboxOption {
  /** 选项值 */
  value: string
  /** 选项标签 */
  label: string
}

interface CheckboxGroupProps {
  /** 组标题 */
  legend: string
  /** 可选项 */
  options: CheckboxOption[]
  /** 已选值集合 */
  values: string[]
  /** 勾选变化回调（返回新的完整集合） */
  onChange: (values: string[]) => void
  /** 组级说明 */
  description?: string
}

/** 多选组。 */
export default function CheckboxGroup({ legend, options, values, onChange, description }: CheckboxGroupProps) {
  const name = useId()
  return (
    <fieldset className="choice-group">
      <legend className="choice-group__legend">{legend}</legend>
      {description ? <span className="choice-group__item-hint">{description}</span> : null}
      {options.map((option) => {
        const checked = values.includes(option.value)
        const optionId = `${name}-${option.value}`
        return (
          <label
            className={checked ? 'choice-group__item choice-group__item--selected' : 'choice-group__item'}
            key={option.value}
            htmlFor={optionId}
          >
            <input
              id={optionId}
              type="checkbox"
              value={option.value}
              checked={checked}
              onChange={(event) => {
                // 勾选则加入集合，取消则从集合移除（保持原有顺序语义由调用方负责）
                const next = event.target.checked
                  ? [...values, option.value]
                  : values.filter((item) => item !== option.value)
                onChange(next)
              }}
            />
            <span className="choice-group__item-body">
              <span className="choice-group__item-label">{option.label}</span>
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}
