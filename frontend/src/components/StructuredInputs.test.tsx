import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import DateInput from './DateInput'
import NumericInput from './NumericInput'
import YearMonthInput from './YearMonthInput'

describe('结构化录入控件', () => {
  it('日期按 yyyy/mm/dd 录入并向接口层输出 ISO 日期', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<DateInput value="" onChange={onChange} />)
    const input = screen.getByPlaceholderText('yyyy/mm/dd')
    await user.type(input, '2026/09/24')
    await user.tab()
    expect(onChange).toHaveBeenCalledWith('2026-09-24')
  })

  it('数值输入始终显示单位，出生年月分别录入', () => {
    const { rerender } = render(<NumericInput value="70" onChange={vi.fn()} unit="kg" />)
    expect(screen.getByText('kg')).toBeInTheDocument()
    rerender(
      <YearMonthInput year="1988" month="7" onYearChange={vi.fn()} onMonthChange={vi.fn()} />,
    )
    expect(screen.getByLabelText('出生年')).toHaveValue(1988)
    expect(screen.getByLabelText('出生月')).toHaveValue('7')
  })
})
