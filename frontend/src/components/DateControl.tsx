/**
 * 组件名称：DateControl.tsx
 * 所属层级：通用组件（components）
 * 功能说明：工作台左侧显示日期，管理员可直接打开窗口维护自己的业务日期。
 *
 * 安全说明：界面只控制入口可见性，真正的测试模式与账号权限由后端校验。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  第一批测试日期模拟
 */

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { ApiError, notifyDateChanged } from '../api/client'
import { testSupportApi } from '../api/endpoints'
import { useAsync } from '../hooks/useAsync'
import { useModalFocus } from '../hooks/useModalFocus'

interface DateControlProps {
  /** 入口可以在工作台开启，但后端can_manage_date仍决定真实权限。 */
  editable?: boolean
  compact?: boolean
  /** 日期修改成功后通知调用方刷新 */
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
export default function DateControl({ onDateChanged, editable = false, compact = false }: DateControlProps) {
  const context = useAsync((signal) => testSupportApi.context(signal), [])
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const panel = useModalFocus(editOpen, () => {if (!saving) setEditOpen(false)})

  useEffect(() => {
    if (context.data) setValue(displayDate(context.data.effective_date))
  }, [context.data])

  /** 保存管理员业务日期并通知调用方刷新。 */
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
      setEditOpen(false)
      notifyDateChanged()
      context.reload()
      onDateChanged?.()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '设置业务日期失败，请重试。')
    } finally {
      setSaving(false)
    }
  }

  /** 清除管理员日期覆盖并恢复读取系统日期。 */
  async function restoreRealDate() {
    setSaving(true)
    setError('')
    try {
      await testSupportApi.setSimulatedDate(null)
      setEditOpen(false)
      notifyDateChanged()
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
      {compact ? <>
        <span className="date-control__readonly">当前日期：{displayDate(loaded.effective_date)}</span>
        {editable && loaded.can_manage_date ? <button type="button" className="btn btn--outlined" onClick={() => {setValue(displayDate(loaded.effective_date)); setError(''); setEditOpen(true)}}>调整日期</button> : null}
        {editOpen && editable && loaded.can_manage_date ? createPortal(<div className="confirm-dialog__scrim"><div ref={panel} className="confirm-dialog" role="dialog" aria-modal="true" aria-label="调整当前账号业务日期">
          <h2>调整当前账号业务日期</h2><p>仅影响当前管理员；普通医生继续使用系统日期。其他页面的未保存内容须重新核对。</p>
          <p>系统日期：{displayDate(loaded.real_date)}</p>
          <label htmlFor="effective-date">业务日期</label><input className="input num" id="effective-date" inputMode="numeric" maxLength={10} value={value} onChange={e => setValue(e.target.value)} placeholder="yyyy/mm/dd" />
          {error ? <p role="alert" className="date-control__error">{error}</p> : null}
          <div className="confirm-dialog__actions"><button type="button" className="btn btn--text" disabled={saving} onClick={() => setEditOpen(false)}>取消</button>
            {loaded.simulated_date ? <button type="button" className="btn btn--outlined" disabled={saving} onClick={() => void restoreRealDate()}>使用系统日期</button> : null}
            <button type="button" className="btn btn--primary" disabled={saving} onClick={() => void applyDate()}>{saving ? '正在保存…' : '应用日期'}</button>
          </div>
        </div></div>, document.body) : null}
      </> : editable && loaded.can_manage_date ? (
        <>
          <span>系统日期：{displayDate(loaded.real_date)}</span>
          <label className="date-control__label" htmlFor="effective-date">
            业务日期
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
              使用系统日期
            </button>
          ) : null}
        </>
      ) : (
        <span className="date-control__readonly">当前日期：{displayDate(loaded.effective_date)}</span>
      )}
      {error && !compact ? <span className="date-control__error" role="alert">{error}</span> : null}
    </div>
  )
}
