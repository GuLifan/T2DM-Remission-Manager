/** 管理员测试管理：邀请码原文仅创建后展示一次，不读取或暴露摘要。 */
import { useState } from 'react'
import { api } from '../api/client'
import { DateControl, ErrorBanner, FieldRow, PageHeader } from '../components'
import { useAsync } from '../hooks/useAsync'

interface Invite { id: number; label: string; expires_at: string; used: boolean; revoked: boolean }
interface Doctor { id: number; username: string; display_name: string; is_active: boolean }

export default function AdminPage({ onBack }: { onBack: () => void }) {
  const invites = useAsync((signal) => api.get<Invite[]>('/api/admin/invites', signal), [])
  const doctors = useAsync((signal) => api.get<Doctor[]>('/api/admin/users', signal), [])
  const [label, setLabel] = useState('')
  const [days, setDays] = useState('7')
  const [created, setCreated] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError('')
    try { await action(); invites.reload(); doctors.reload() }
    catch (e) { setError(e instanceof Error ? e.message : '操作失败，请重试。') }
    finally { setBusy(false) }
  }
  return <div className="page">
    <PageHeader title="账号管理" actions={<button className="btn btn--text" onClick={onBack}>返回患者工作台</button>} />
    <section className="card stack"><h2>日期维护</h2><p>仅调整当前管理员账号的业务日期，不改变系统时间或其他账号日期。临床记录保留实际采用的业务日期。</p><DateControl editable /></section>
    {error || invites.error || doctors.error ? <ErrorBanner message={error || invites.error || doctors.error || ''} /> : null}
    <section className="card stack">
      <h2>创建邀请码</h2>
      <FieldRow label="备注">{(fieldProps) => <input {...fieldProps} className="input" value={label} maxLength={80} onChange={(e) => setLabel(e.target.value)} />}</FieldRow>
      <FieldRow label="有效天数">{(fieldProps) => <input {...fieldProps} className="input" type="number" min={1} max={90} value={days} onChange={(e) => setDays(e.target.value)} />}</FieldRow>
      <button className="btn btn--primary" disabled={busy || !Number.isInteger(Number(days)) || Number(days) < 1 || Number(days) > 90}
        onClick={() => void run(async () => {
          const value = await api.post<{code: string}>('/api/admin/invites', {label, valid_days: Number(days)})
          setCreated(value.code)
        })}>生成一次性邀请码</button>
      {created ? <FieldRow label="新邀请码" hint="请现在复制并分发；离开此页面后无法再次查看原文。">
        {(fieldProps) => <input {...fieldProps} className="input" readOnly value={created} onFocus={(e) => e.target.select()} />}
      </FieldRow> : null}
    </section>
    <section className="card stack"><h2>邀请码记录</h2>
      {invites.data?.map((i) => <div className="settings-row" key={i.id}>
        <span>{i.label || '无备注'} · {i.used ? '已使用' : i.revoked ? '已撤销' : Date.parse(i.expires_at) < Date.now() ? '已过期' : '待使用'} · 到期 {i.expires_at.slice(0, 10)}</span>
        <button className="btn btn--text" disabled={busy || i.used || i.revoked}
          onClick={() => void run(() => api.post(`/api/admin/invites/${i.id}/revoke`))}>撤销邀请</button>
      </div>)}
    </section>
    <section className="card stack"><h2>医生账号</h2>
      {doctors.data?.map((d) => <div className="settings-row" key={d.id}>
        <span>{d.display_name} · {d.username} · {d.is_active ? '使用中' : '已停用'}</span>
        <button className="btn btn--text" disabled={busy} onClick={() => {
          if (window.confirm(`${d.is_active ? '停用' : '启用'}此账号？已有会话将失效，历史记录保留。`)) {
            void run(() => api.put(`/api/admin/users/${d.id}/enabled`, {is_active: !d.is_active}))
          }
        }}>{d.is_active ? '停用账号' : '重新启用'}</button>
      </div>)}
    </section>
  </div>
}
