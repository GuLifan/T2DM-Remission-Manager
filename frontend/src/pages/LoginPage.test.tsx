/**
 * 文件名称：LoginPage.test.tsx
 * 所属层级：页面测试（pages）
 * 功能说明：验证登录页的两种形态——首次创建账号与普通登录。

 * 覆盖要点：
 *   1. 后端报告"还没有账号"时，页面显示创建账号引导（含显示姓名）；
 *   2. 提交前就地校验（密码不足 8 位不发起请求）；
 *   3. 创建成功后写入会话令牌。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { session } from '../api/client'
import LoginPage from './LoginPage'

/** 构造 fetch 响应。 */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('LoginPage', () => {
  beforeEach(() => {
    session.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('首次运行时显示创建账号引导，并在提交后写入令牌', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/auth/status')) return Promise.resolve(jsonResponse({ needs_bootstrap: true }))
      if (url.endsWith('/api/auth/bootstrap')) {
        return Promise.resolve(
          jsonResponse({
            token: 'token-abc',
            expires_at: 9999999999,
            user: { id: 1, username: 'doctor', display_name: '张医生', role: 'doctor' },
          }),
        )
      }
      return Promise.resolve(jsonResponse({ detail: '未预期的请求' }, 500))
    })
    vi.stubGlobal('fetch', fetchMock)

    const onLoggedIn = vi.fn()
    const user = userEvent.setup()
    render(<LoginPage onLoggedIn={onLoggedIn} />)

    // 首次使用提示
    expect(await screen.findByText(/首次使用/)).toBeInTheDocument()

    await user.type(screen.getByLabelText('登录名'), 'doctor')
    await user.type(screen.getByLabelText('界面显示姓名'), '张医生')
    await user.type(screen.getByLabelText('密码'), 'Test-Passw0rd')
    await user.click(screen.getByRole('button', { name: /创建账号并进入系统/ }))

    await waitFor(() => expect(onLoggedIn).toHaveBeenCalledWith(expect.objectContaining({ display_name: '张医生' })))
    // 令牌已写入本地会话
    expect(session.token).toBe('token-abc')
  })

  it('密码不足 8 位时就地提示，不发起请求', async () => {
    const fetchMock = vi.fn(() => Promise.resolve(jsonResponse({ needs_bootstrap: true })))
    vi.stubGlobal('fetch', fetchMock)

    const user = userEvent.setup()
    render(<LoginPage onLoggedIn={vi.fn()} />)
    await screen.findByText(/首次使用/)

    await user.type(screen.getByLabelText('登录名'), 'doctor')
    await user.type(screen.getByLabelText('界面显示姓名'), '张医生')
    await user.type(screen.getByLabelText('密码'), 'short')
    await user.click(screen.getByRole('button', { name: /创建账号并进入系统/ }))

    expect(await screen.findByText('密码至少 8 位。')).toBeInTheDocument()
    // 只调用了 /auth/status，没有调用 bootstrap
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
