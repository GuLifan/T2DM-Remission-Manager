import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import CheckboxGroup from './CheckboxGroup'

function Harness() {
  const [values, setValues] = useState<string[]>(['无'])
  return (
    <CheckboxGroup
      legend="安全问题"
      values={values}
      onChange={setValues}
      options={['无', '低血糖', '急性疾病'].map((value) => ({ value, label: value }))}
    />
  )
}

describe('CheckboxGroup 排他项', () => {
  it('选择具体项时清除“无”，再次选择“无”时清除具体项', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    const none = screen.getByRole('checkbox', { name: '无' })
    const hypoglycemia = screen.getByRole('checkbox', { name: '低血糖' })
    const acute = screen.getByRole('checkbox', { name: '急性疾病' })

    expect(none).toBeChecked()
    await user.click(hypoglycemia)
    expect(none).not.toBeChecked()
    expect(hypoglycemia).toBeChecked()

    await user.click(acute)
    expect(hypoglycemia).toBeChecked()
    expect(acute).toBeChecked()

    await user.click(none)
    expect(none).toBeChecked()
    expect(hypoglycemia).not.toBeChecked()
    expect(acute).not.toBeChecked()
  })
})
