/**
 * 文件名称：ChoiceGroup.test.tsx
 * 所属层级：组件测试（components）
 * 功能说明：验证互斥分支选择组的关键行为——单选语义、禁用原因展示、
 *   以及"被覆盖的分支不可选"这一 V1.0 关键约束（UI.md 3.5）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ChoiceGroup from './ChoiceGroup'

describe('ChoiceGroup', () => {
  it('按传入顺序（优先级）渲染全部选项', () => {
    render(
      <ChoiceGroup
        legend="本次复评分支"
        value="stop_last_med"
        onChange={() => undefined}
        options={[
          { value: 'uncontrolled', label: '存在明显血糖失控' },
          { value: 'stop_last_med', label: '停用最后一种药物' },
        ]}
      />,
    )

    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(2)
    // 顺序即优先级：高优先级必须排在前面
    expect(radios[0]).toHaveAccessibleName(/存在明显血糖失控/)
    expect(radios[1]).toHaveAccessibleName(/停用最后一种药物/)
    // 当前值对应的选项应当被选中
    expect(radios[1]).toBeChecked()
  })

  it('被高优先级分支覆盖的选项必须禁用并说明原因', () => {
    render(
      <ChoiceGroup
        legend="本次复评分支"
        value="uncontrolled"
        onChange={() => undefined}
        options={[
          { value: 'uncontrolled', label: '存在明显血糖失控' },
          {
            value: 'stop_last_med',
            label: '停用最后一种药物',
            disabled: true,
            disabledReason: '已选择明显血糖失控，本次不记录停药',
          },
        ]}
      />,
    )

    expect(screen.getByRole('radio', { name: /停用最后一种药物/ })).toBeDisabled()
    // 禁用原因必须展示给医生，禁止静默忽略
    expect(screen.getByText(/已选择明显血糖失控/)).toBeInTheDocument()
  })

  it('点击选项触发 onChange 并回传选项值', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(
      <ChoiceGroup
        legend="本次复评分支"
        value="routine_action"
        onChange={onChange}
        options={[
          { value: 'stop_last_med', label: '停用最后一种药物' },
          { value: 'routine_action', label: '常规复评动作' },
        ]}
      />,
    )

    await user.click(screen.getByRole('radio', { name: /停用最后一种药物/ }))
    expect(onChange).toHaveBeenCalledWith('stop_last_med')
  })
})
