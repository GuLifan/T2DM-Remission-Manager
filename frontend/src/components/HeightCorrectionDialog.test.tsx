import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import HeightCorrectionDialog from './HeightCorrectionDialog'
import type { Patient } from '../types'

it('Escape关闭身高更正并返回触发按钮，取消不提交',async()=>{
  const user=userEvent.setup(),fetcher=vi.spyOn(window,'fetch'),saved=vi.fn()
  render(<HeightCorrectionDialog patient={{id:1,height_cm:170} as Patient} onSaved={saved} />)
  const trigger=screen.getByRole('button',{name:'更正身高'})
  await user.click(trigger)
  await user.clear(screen.getByLabelText('新身高'));await user.type(screen.getByLabelText('新身高'),'171')
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveFocus();expect(fetcher).not.toHaveBeenCalled();expect(saved).not.toHaveBeenCalled()
  fetcher.mockRestore()
})
