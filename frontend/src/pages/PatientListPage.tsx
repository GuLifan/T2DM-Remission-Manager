/** 患者工作台：个人进度、归档记录、场景创建及重置。 */
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import { domainApi, patientApi, referenceApi, testSupportApi } from '../api/endpoints'
import { ConfirmDialog, DateControl, EmptyState, ErrorBanner, FieldRow, LoadingBlock, PageHeader, StatusBadge, YearMonthInput } from '../components'
import { useAsync } from '../hooks/useAsync'
import { patientNumber } from '../presentation'
import type { Patient, UserOut } from '../types'
interface Props { currentUser: UserOut; onOpenPatient: (id: number) => void; onLogout: () => void }
export function dueState(patient: Patient, today: string): 'overdue' | 'today' | 'future' | 'none' {
  if (!patient.next_review_date) return 'none'
  return patient.next_review_date < today ? 'overdue' : patient.next_review_date === today ? 'today' : 'future'
}
export default function PatientListPage({currentUser, onOpenPatient, onLogout}: Props) {
  const patients = useAsync((signal) => patientApi.list(signal), [])
  const states = useAsync((signal) => domainApi.states(signal), [])
  const context = useAsync((signal) => testSupportApi.context(signal), [])
  const references = useAsync((signal) => referenceApi.get(signal), [])
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [resetPatient, setResetPatient] = useState<Patient | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState('')
  const [gender, setGender] = useState('')
  const [birthYear, setBirthYear] = useState('')
  const [birthMonth, setBirthMonth] = useState('')
  const [department, setDepartment] = useState('内分泌科')
  const [sort, setSort] = useState<'updated' | 'name' | 'date'>('updated')
  const names = new Map(states.data?.map((s) => [s.code, s.name]))
  const visible = useMemo(() => (patients.data ?? [])
    .filter((p) => !!p.archived === history && `${p.name} ${patientNumber(p)} ${p.owner_display_name ?? ''}`.includes(query.trim()))
    .sort((a,b) => sort === 'name' ? a.name.localeCompare(b.name, 'zh-CN') : sort === 'date'
      ? (a.next_review_date ?? '9999').localeCompare(b.next_review_date ?? '9999') : b.updated_at.localeCompare(a.updated_at)),
    [patients.data, query, history, sort])
  async function run(action: () => Promise<Patient>) {
    setBusy(true); setError('')
    try { const value = await action(); patients.reload(); onOpenPatient(value.id) }
    catch (e) { setError(e instanceof Error ? e.message : '操作失败，请重试。') }
    finally { setBusy(false) }
  }
  async function createCase() {
    if (!name.trim() || !gender || !birthYear || !birthMonth || !department) {
      setError('请填写姓名、性别、出生年月和科室。')
      return
    }
    await run(() => api.post<Patient>('/api/demo/cases', {
      name: name.trim(), gender, birth_date: `${birthYear}-${birthMonth.padStart(2, '0')}-01`, department,
    }))
  }
  return <div className="page">
    <PageHeader title="患者工作台" context={`当前账号：${currentUser.display_name}`} actions={<>
      <DateControl onDateChanged={context.reload} />
      {currentUser.role === 'admin' ? <a className="btn btn--text" href="/admin">账号管理</a> : null}
      <button className="btn btn--text" onClick={onLogout}>退出登录</button>
    </>} />
    <p>新建患者后，从预评估开始管理；请按实际日期记录检查、用药及随访情况。</p>
    <a href="/guide" className="btn btn--text">使用指南</a>
    {error || patients.error ? <ErrorBanner message={error || patients.error || ''} /> : null}
    <section className="card stack">
      <div className="page__actions">
        <button className={`btn ${!history ? 'btn--primary' : 'btn--text'}`} onClick={() => setHistory(false)}>当前病例</button>
        <button className={`btn ${history ? 'btn--primary' : 'btn--text'}`} onClick={() => setHistory(true)}>已归档病例</button>
        <button className="btn btn--outlined" disabled={busy} onClick={() => setCreateOpen(!createOpen)}>{createOpen ? '收起建档表单' : '新建患者'}</button>
      </div>
      {createOpen ? <div className="card card--muted stack"><h2>新建患者</h2><p>填写患者基本资料，系统生成病例编号；后续检查、测量和用药由医生记录。</p>
        <div className="form-grid">
          <FieldRow label="姓名">{(props) => <input {...props} className="input" value={name} maxLength={64} onChange={(e) => setName(e.target.value)} />}</FieldRow>
          <FieldRow label="性别">{(props) => <select {...props} className="select" value={gender} onChange={(e) => setGender(e.target.value)}><option value="">待选择</option><option>女</option><option>男</option></select>}</FieldRow>
          <FieldRow label="出生年月">{(props) => <YearMonthInput {...props} year={birthYear} month={birthMonth} onYearChange={setBirthYear} onMonthChange={setBirthMonth} />}</FieldRow>
          <FieldRow label="科室">{(props) => <select {...props} className="select" value={department} onChange={(e) => setDepartment(e.target.value)}>
            {(references.data?.departments ?? ['内分泌科']).map((item) => <option key={item}>{item}</option>)}
          </select>}</FieldRow>
        </div><button className="btn btn--primary" disabled={busy} onClick={() => void createCase()}>保存并开始预评估</button>
      </div> : null}
      <div className="page__actions">
        <label>搜索病例 <input className="input" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label>排序 <select className="select" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
          <option value="updated">最近更新</option><option value="name">病例名称</option><option value="date">复评日期</option>
        </select></label>
      </div>
      {patients.loading ? <LoadingBlock message="正在加载病例…" /> : visible.length === 0 ? <EmptyState message={history ? '暂无归档记录' : query ? '暂无匹配病例' : '暂无病例，请新建患者。'} /> :
        <div className="table-scroll"><table className="table"><thead><tr>
          <th>患者</th><th>当前状态</th><th>责任医生</th><th>下次复评</th><th>操作</th>
        </tr></thead><tbody>{visible.map((p) => <tr key={p.id}>
          <td>{p.name}<div className="field-row__hint">{patientNumber(p)}</div></td>
          <td><StatusBadge>{names.get(p.current_state) ?? '加载中'}</StatusBadge></td>
          <td>{p.owner_display_name}</td><td>{p.next_review_date ?? '尚未约定'}</td>
          <td><button className="btn btn--text" onClick={() => onOpenPatient(p.id)}>{history ? '查看历史' : '继续管理'}</button>
            {!history ? <button className="btn btn--text" disabled={busy} onClick={() => setResetPatient(p)}>归档并新建</button> : null}</td>
        </tr>)}</tbody></table></div>}
      <ConfirmDialog open={Boolean(resetPatient)} title="归档并新建" confirmLabel="归档并建立新管理记录" cancelLabel="保留当前病例" danger
        description={`${resetPatient?.name ?? ''}：当前病例将归档并保留历史，基于基本资料建立新的管理记录。既往测量、检查、用药和临床结论不会自动带入。`}
        onCancel={() => setResetPatient(null)} onConfirm={() => {if (!resetPatient || busy) return; const pid = resetPatient.id; setResetPatient(null); void run(() => api.post<Patient>(`/api/patients/${pid}/reset`))}} />
    </section>
  </div>
}
