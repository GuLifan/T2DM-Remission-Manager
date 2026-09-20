/**
 * 页面名称：LoginPage.tsx
 * 所属层级：页面组件（pages）
 * 功能说明：登录页。首次运行时同一页面承担"创建首个医生账号"的引导
 *   （由 /api/auth/status 的 needs_bootstrap 决定显示哪套表单）。
 *
 * 交互要点：
 *   - 密码不预置、不显示默认值；账号由医生本人创建；
 *   - 提交前就地校验（用户名/密码长度），不只依赖后端报错；
 *   - 提交中禁用按钮，避免重复提交；
 *   - 后端返回的错误文案为自然语言，直接展示。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { authApi } from '../api/endpoints'
import { ApiError, session } from '../api/client'
import { ErrorBanner, FieldRow, LoadingBlock } from '../components'
import { useAsync } from '../hooks/useAsync'
import type { UserOut } from '../types'

interface LoginPageProps {
  /** 登录成功后回调（由 App 记录当前账号并跳转） */
  onLoggedIn: (user: UserOut) => void
}

/** 登录 / 首次创建账号。 */
export default function LoginPage({ onLoggedIn }: LoginPageProps) {
  const status = useAsync((signal) => authApi.status(signal), [])
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const needsBootstrap = status.data?.needs_bootstrap ?? false

  /** 提交登录或创建首个账号。 */
  async function handleSubmit() {
    setError('')
    // 提交前校验：给出明确字段提示，不依赖后端 422
    if (username.trim().length < 3) {
      setError('登录名至少 3 个字符。')
      return
    }
    if (password.length < 8) {
      setError('密码至少 8 位。')
      return
    }
    if (needsBootstrap && displayName.trim().length === 0) {
      setError('请填写界面显示姓名。')
      return
    }
    setSubmitting(true)
    try {
      const result = needsBootstrap
        ? await authApi.bootstrap({ username: username.trim(), display_name: displayName.trim(), password })
        : await authApi.login({ username: username.trim(), password })
      session.token = result.token
      onLoggedIn(result.user)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '登录失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  if (status.loading) {
    return (
      <div className="login-page">
        <div className="login-card card">
          <LoadingBlock message="正在检查系统状态…" />
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card card">
        <h1 className="login-title">早期2型糖尿病缓解管理软件</h1>
        <p className="login-subtitle">
          系统负责计算与提醒，医生负责医学决定。
        </p>

        {status.error ? <ErrorBanner message={status.error} /> : null}
        {error ? <ErrorBanner message={error} /> : null}

        <p className="page__subtitle">
          {needsBootstrap
            ? '首次使用：请创建第一个医生账号（不设默认密码）。'
            : '请使用医生账号登录。'}
        </p>

        <div className="stack">
          <FieldRow label="登录名">
            {(fieldProps) => (
              <input
                {...fieldProps}
                className="input"
                value={username}
                autoComplete="username"
                onChange={(event) => setUsername(event.target.value)}
              />
            )}
          </FieldRow>

          {needsBootstrap ? (
            <FieldRow label="界面显示姓名" hint="会记入临床事件流水的操作者。">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                />
              )}
            </FieldRow>
          ) : null}

          <FieldRow label="密码" hint={needsBootstrap ? '至少 8 位，请自行妥善保管。' : undefined}>
            {(fieldProps) => (
              <input
                {...fieldProps}
                className="input"
                type="password"
                value={password}
                autoComplete={needsBootstrap ? 'new-password' : 'current-password'}
                onChange={(event) => setPassword(event.target.value)}
              />
            )}
          </FieldRow>
        </div>

        <div className="login-actions">
          <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleSubmit}>
            {submitting ? '正在提交…' : needsBootstrap ? '创建账号并进入系统' : '登录'}
          </button>
        </div>
      </div>
    </div>
  )
}
