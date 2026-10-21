import { useModalFocus } from '../../hooks/useModalFocus'
import { useState } from 'react'
import { DateInput, ErrorBanner } from '../../components'
import { useAsync } from '../../hooks/useAsync'
import type { Patient } from '../../types'
import { clinicalDataApi } from './api'
import ExaminationEditor from './ExaminationEditor'
import { PayloadView } from './HistoryDetail'
import MedicationEditor from './MedicationEditor'
import type { DataRecord, Examination, Medication } from './types'

const names: Record<string, string> = {measurement: '体重测量', examination: '检查资料', medication_regimen: '用药方案', duration: '病程', correction: '补正记录'}
export default function RecordCorrections({patient, onUpdated}: {patient: Patient; onUpdated: () => void}) {
  const data = useAsync(signal => clinicalDataApi.records(patient.id, signal), [patient.id, patient.clinical_revision])
  const [record, setRecord] = useState<DataRecord<Record<string, unknown>> | null>(null)
  const [replacement, setReplacement] = useState<Record<string, unknown>>({})
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const panel = useModalFocus(Boolean(record), () => {if (!busy) setRecord(null)})
  async function save() {
    if (!record || !reason.trim()) {setError('请填写补正原因。'); return}
    setBusy(true); setError('')
    try { await clinicalDataApi.correct(patient.id, patient.clinical_revision, record, replacement, reason); setRecord(null); data.reload(); onUpdated() }
    catch (e) {setError(e instanceof Error ? e.message : '补正保存失败')} finally {setBusy(false)}
  }
  const rows = Array.isArray(data.data) ? data.data : []
  const superseded = new Set(rows.map(r => r.supersedes_id).filter(Boolean))
  return <details className="section records-section"><summary>资料记录与补正</summary><p>记录只增不改。误录可补正；真实停药请在当前评估中记录实际状态与日期。补正影响判定依据后，须重新进行临床核对。</p>
    {data.error || error ? <ErrorBanner message={error || data.error} /> : null}
    {rows.map(r => <details key={r.id} className="record-item"><summary>{names[r.kind] ?? '资料'} · {r.clinical_date ?? '日期未记录'}{superseded.has(r.id) ? ' · 已有补正' : ''}</summary><p className="field-row__hint">记录医生：{r.operator_display_name ?? '历史账号'} · {r.created_at.replace('T', ' ').slice(0,16)}</p><PayloadView value={r.data} />
      {r.kind !== 'correction' && patient.can_edit && !patient.archived && !superseded.has(r.id) ? <button type="button" className="btn btn--text" onClick={() => {setRecord(r); setReplacement(structuredClone(r.data)); setReason(''); setError('')}}>补正此条资料</button> : null}</details>)}
    {record ? <div className="confirm-dialog__scrim"><div ref={panel} className="card correction-form" role="dialog" aria-modal="true" aria-label="资料补正"><h3>补正{names[record.kind]}</h3>
      {record.kind === 'measurement' ? <div className="form-grid"><label>正确体重（kg）<input className="input" type="number" step="0.1" value={Number(replacement.weight_kg) || ''} onChange={e => setReplacement(v => ({...v, weight_kg: Number(e.target.value)}))} /></label><label>正确测量日期<DateInput value={String(replacement.measured_on ?? '')} onChange={v => setReplacement(p => ({...p, measured_on: v || null}))} /></label></div> : null}
      {record.kind === 'examination' ? <ExaminationEditor value={[replacement as unknown as Examination]} onChange={v => {if (v[0]) setReplacement(v[0] as unknown as Record<string, unknown>)}} saved={[]} selectedIds={[]} onSelect={() => undefined} /> : null}
      {record.kind === 'medication_regimen' ? <><MedicationEditor value={(replacement.medications ?? []) as Medication[]} allowRemoveSaved onChange={v => setReplacement(p => ({medications: v, complete: p.complete ?? false}))} /><label><input type="checkbox" checked={Boolean(replacement.complete)} onChange={e => setReplacement(p => ({medications: p.medications, complete: e.target.checked}))} />已完整核对补正后方案</label></> : null}
      {record.kind === 'duration' ? <div className="form-grid">{['years', 'months'].map(k => <label key={k}>{k === 'years' ? '病程年' : '病程月'}<input className="input" type="number" min="0" step="1" value={replacement[k] == null ? '' : Number(replacement[k])} onChange={e => setReplacement(p => ({...p, [k]: e.target.value === '' ? null : Number(e.target.value)}))} /></label>)}</div> : null}
      <label>补正原因<textarea className="input" value={reason} onChange={e => setReason(e.target.value)} /></label><div className="page__actions"><button type="button" className="btn btn--outlined" disabled={busy} onClick={() => setRecord(null)}>取消补正</button><button type="button" className="btn btn--primary" disabled={busy} onClick={() => void save()}>保存补正并保留原记录</button></div>
    </div></div> : null}
  </details>
}
