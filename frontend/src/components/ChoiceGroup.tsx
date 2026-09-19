/**
 * 组件名称：ChoiceGroup.tsx
 * 所属层级：通用组件（components）
 * 功能说明：互斥分支选择组（单选语义），用于临床分支选择。
 *
 * 为什么必须是单选：临床分支存在优先级（如阶段复评：明显失控 > 治疗下达标用获益药
 * > 停用最后一种药 > 常规复评动作）。V0.1 用多个独立复选框表达互斥分支，
 * 导致医生同时勾选时高优先级分支静默覆盖低优先级分支。V1.0 用单选 + 显式禁用原因
 * 从结构上杜绝该问题（UI.md 3.5）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useId } from 'react'

export interface ChoiceOption {
  /** 选项值（提交给后端的枚举值） */
  value: string
  /** 选项标签（医生看到的自然语言） */
  label: string
  /** 选项说明："选了会发生什么" */
  hint?: string
  /** 是否禁用（被更高优先级分支覆盖时置为 true） */
  disabled?: boolean
  /** 禁用原因（必须给出，禁止静默忽略医生已填内容） */
  disabledReason?: string
}

interface ChoiceGroupProps {
  /** 组标题 */
  legend: string
  /** 选项（按优先级自上而下排列，高优先级在上） */
  options: ChoiceOption[]
  /** 当前选中值 */
  value: string | null
  /** 选中回调 */
  onChange: (value: string) => void
  /** 组级说明 */
  description?: string
}

/** 互斥分支选择组。 */
export default function ChoiceGroup({ legend, options, value, onChange, description }: ChoiceGroupProps) {
  const name = useId()
  return (
    <fieldset className="choice-group">
      <legend className="choice-group__legend">{legend}</legend>
      {description ? <span className="choice-group__item-hint">{description}</span> : null}
      {options.map((option) => {
        const selected = option.value === value
        // 选项样式：选中 / 禁用 / 默认三种
        const className = [
          'choice-group__item',
          selected ? 'choice-group__item--selected' : '',
          option.disabled ? 'choice-group__item--disabled' : '',
        ]
          .filter(Boolean)
          .join(' ')
        const optionId = `${name}-${option.value}`
        return (
          <label className={className} key={option.value} htmlFor={optionId}>
            <input
              id={optionId}
              type="radio"
              name={name}
              value={option.value}
              checked={selected}
              disabled={option.disabled}
              onChange={() => onChange(option.value)}
            />
            <span className="choice-group__item-body">
              <span className="choice-group__item-label">{option.label}</span>
              {option.hint ? <span className="choice-group__item-hint">{option.hint}</span> : null}
              {/* 禁用原因必须展示，让医生知道"为什么不能选" */}
              {option.disabled && option.disabledReason ? (
                <span className="choice-group__item-hint">本次不可选：{option.disabledReason}</span>
              ) : null}
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}
