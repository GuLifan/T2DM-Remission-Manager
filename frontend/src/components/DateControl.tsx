/**
 * 组件名称：DateControl.tsx
 * 所属层级：通用组件（components）
 * 功能说明：在页头显示当前有效日期；测试账号可设置或清除账号级模拟日期。
 *
 * 安全说明：界面只控制入口可见性，真正的测试模式与账号权限由后端校验。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  第一批测试日期模拟
 */

import { useEffect, useState } from 'react'

import { ApiError } from '../api/client'
import { testSupportApi } from '../api/endpoints'
import { useAsync } from '../hooks/useAsync'

interface DateControlProps {
  /** 日期修改后执行；患者工作台用它返回患者列表 */
  onDateChanged?: () => void
}

/** 把后端 ISO 日期转换成统一的 yyyy/mm/dd 展示。 */
function displayDate(value: string): string {
  return value.replaceAll('-', '/')
}

/** 校验并把 yyyy/mm/dd 转换成后端 ISO 日期。 */
function parseDate(value: string): string | null {
  const match = /^(\d{4})\/(\d{2})\/(\d{2})$/.exec(value.trim())
  if (!match) return null
  const iso = `${match[1]}-${match[2]}-${match[3]}`
  // 使用 UTC 构造，避免中国时区把本地零点换算成前一天而误判合法日期
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== iso) return null
  return iso
}

/** 页头日期控件。 */
export default function DateControl({ onDateChanged }: DateControlProps) {
  const context = useAsync((signal) => testSupportApi.context(signal), [])
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (context.data) setValue(displayDate(context.data.effective_date))
  }, [context.data])

  /** 保存模拟日期并通知页面返回患者列表。 */
  async function applyDate() {
    const parsed = parseDate(value)
    if (!parsed) {
      setError('请按 yyyy/mm/dd 输入有效日期。')
      return
    }
    setSaving(true)
    setError('')
    try {
      await testSupportApi.setSimulatedDate(parsed)
      context.reload()
      onDateChanged?.()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '设置模拟日期失败，请重试。')
    } finally {
      setSaving(false)
    }
  }

  /** 清除模拟日期并恢复读取本机真实日期。 */
  async function restoreRealDate() {
    setSaving(true)
    setError('')
    try {
      await testSupportApi.setSimulatedDate(null)
      context.reload()
      onDateChanged?.()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '恢复真实日期失败，请重试。')
    } finally {
      setSaving(false)
    }
  }

  if (context.error) {
    return <span className="date-control__error">{context.error}</span>
  }
  if (context.loading || !context.data?.effective_date) {
    return <span className="date-control__readonly">正在读取日期…</span>
  }

  const loaded = context.data
  return (
    <div className={`date-control${loaded.simulated_date ? ' date-control--simulated' : ''}`}>
      {loaded.simulated_date ? <span className="date-control__warning">正在使用模拟日期</span> : null}
      {loaded.can_use_test_tools ? (
        <>
          <label className="date-control__label" htmlFor="effective-date">
            当前日期
          </label>
          <input
            className="date-control__input num"
            id="effective-date"
            inputMode="numeric"
            maxLength={10}
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="yyyy/mm/dd"
          />
          <button type="button" className="btn btn--text" disabled={saving} onClick={applyDate}>
            {saving ? '正在保存…' : '应用日期'}
          </button>
          {loaded.simulated_date ? (
            <button type="button" className="btn btn--text" disabled={saving} onClick={restoreRealDate}>
              恢复真实日期
            </button>
          ) : null}
        </>
      ) : (
        <span className="date-control__readonly">当前日期：{displayDate(loaded.effective_date)}</span>
      )}
      {error ? <span className="date-control__error" role="alert">{error}</span> : null}
    </div>
  )
}
