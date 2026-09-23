/**
 * 文件名称：DateControl.test.tsx
 * 所属层级：组件测试
 * 功能说明：验证当前日期只读展示、模拟日期保存与恢复入口。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  第一批测试日期模拟
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import DateControl from './DateControl'

function jsonOk(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('DateControl 当前日期', () => {
  afterEach(() => vi.restoreAllMocks())

  it('普通账号只读显示 yyyy/mm/dd', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonOk({
            test_mode_enabled: false,
            can_use_test_tools: false,
            real_date: '2026-09-24',
            effective_date: '2026-09-24',
            simulated_date: null,
          }),
        ),
      ),
    )
    render(<DateControl />)
    expect(await screen.findByText('当前日期：2026/09/24')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '应用日期' })).not.toBeInTheDocument()
  })

  it('测试账号可保存模拟日期，并通知工作台返回患者列表', async () => {
    const onDateChanged = vi.fn()
    const fetchMock = vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve(
          jsonOk({
            test_mode_enabled: true,
            can_use_test_tools: true,
            real_date: '2026-09-24',
            effective_date: '2030-01-02',
            simulated_date: '2030-01-02',
          }),
        )
      }
      return Promise.resolve(
        jsonOk({
          test_mode_enabled: true,
          can_use_test_tools: true,
          real_date: '2026-09-24',
          effective_date: '2026-09-24',
          simulated_date: null,
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<DateControl onDateChanged={onDateChanged} />)

    const input = await screen.findByLabelText('当前日期')
    await waitFor(() => expect(input).toHaveValue('2026/09/24'))
    await user.clear(input)
    await user.type(input, '2030/01/02')
    await user.click(screen.getByRole('button', { name: '应用日期' }))

    await waitFor(() => expect(onDateChanged).toHaveBeenCalledOnce())
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/test-context/simulated-date',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ simulated_date: '2030-01-02' }),
      }),
    )
  })
})
