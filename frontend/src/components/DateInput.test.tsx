import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import DateInput from './DateInput'

it('有事实日期上限时标记未来输入，纠正为当日后清除错误',async()=>{
  const changed=vi.fn(),user=userEvent.setup()
  render(<DateInput value="" onChange={changed} max="2026-10-21" />)
  const input=screen.getByPlaceholderText('yyyy/mm/dd')
  await user.type(input,'2026/10/22')
  expect(input).toHaveAttribute('aria-invalid','true')
  expect(screen.getByText('检测日期不得晚于本次业务日期 2026/10/21。')).toBeInTheDocument()
  expect(screen.getByLabelText('打开日历选择日期')).toHaveAttribute('max','2026-10-21')
  await user.clear(input);await user.type(input,'2026/10/21')
  expect(input).toHaveAttribute('aria-invalid','false')
  expect(changed).toHaveBeenLastCalledWith('2026-10-21')
})

it('无上限的未来复评计划仍然合法',async()=>{
  const user=userEvent.setup(),changed=vi.fn()
  render(<DateInput value="" onChange={changed} />)
  const input=screen.getByPlaceholderText('yyyy/mm/dd')
  await user.type(input,'2027/01/01')
  expect(input).toHaveAttribute('aria-invalid','false')
  expect(changed).toHaveBeenLastCalledWith('2027-01-01')
})
