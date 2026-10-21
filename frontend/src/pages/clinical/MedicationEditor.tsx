import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { CheckboxGroup, DateInput, FieldRow } from '../../components'
import type { Medication, MedicationCatalog } from './types'
import { purposesOf } from './types'

const purposes = ['降糖治疗', '肾脏保护', '心血管保护', '体重管理', '其他']
export const blankMedication = (name = ''): Medication => ({
  name, dose: '', status: '使用中', has_glucose_lowering_effect: null, purposes: [],
  purpose: null, started_on: null, stopped_on: null, start_precision: 'unknown', start_value: null,
})

/** 本项目独立目录；选中只生成草稿，不推断药效、剂量和临床目的。 */
export default function MedicationEditor({value, onChange, allowRemoveSaved = true}: {
  value: Medication[]; onChange: (v: Medication[]) => void; allowRemoveSaved?: boolean
}) {
  const [catalog, setCatalog] = useState<MedicationCatalog | null>(null)
  const [catalogError, setCatalogError] = useState('')
  const [category, setCategory] = useState('insulin')
  const [selected, setSelected] = useState<string[]>([])
  const [search, setSearch] = useState('')
  const [triggerIndex, setTriggerIndex] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  const lastTrigger = useRef<HTMLElement | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    api.get<{medication_catalog: MedicationCatalog}>('/api/reference', controller.signal)
      .then(r => setCatalog(r.medication_catalog)).catch(() => { if (!controller.signal.aborted) setCatalogError('常用药物目录读取失败，可继续手动填写。') })
    return () => controller.abort()
  }, [])
  const entries = catalog?.categories.flatMap(c => c.medications.map(m => ({...m, category: c.id}))) ?? []
  const choices = search ? entries.filter(e => [e.name, ...e.aliases].some(n => n.includes(search))) : entries.filter(e => e.category === category)
  function open(index: number | null) {
    lastTrigger.current = document.activeElement as HTMLElement
    setTriggerIndex(index); setSelected([]); setSearch(''); dialog.current?.showModal()
  }
  function close() { dialog.current?.close(); lastTrigger.current?.focus() }
  function addSelected() {
    const next = entries.filter(e => selected.includes(e.id)).map(e => ({...blankMedication(e.category === 'other' ? '' : e.name), catalog_id: e.id, category_id: e.category}))
    if (next.some(n => value.some(m => m.name && m.name === n.name))) setNotice('所选药物中有同名记录，已分别保留；请核对剂型、剂量和用途。')
    const target = triggerIndex == null ? null : value[triggerIndex]
    // 完全空白卡才承接第一条；已有名称、剂量或事实均不覆盖。
    if (target && !target.medication_id && !target.name && !target.dose && !purposesOf(target).length && !target.start_value && !target.started_on && !target.stopped_on && target.has_glucose_lowering_effect == null && target.status === '使用中' && next.length) {
      onChange([...value.slice(0, triggerIndex!), next[0]!, ...value.slice(triggerIndex! + 1), ...next.slice(1)])
    } else onChange([...value, ...next])
    close()
  }
  function update(index: number, patch: Partial<Medication>) {
    onChange(value.map((m, i) => i === index ? {...m, ...patch} : m))
  }
  return <section className="medication-section" aria-label="当前药物核对">
    <div className="section-heading"><h3>当前药物核对 <span className="count-badge">{value.length}</span></h3><div className="page__actions">
      <button type="button" className="btn btn--outlined" onClick={() => open(null)}>选择常用药物</button>
      <button type="button" className="btn btn--text" onClick={() => onChange([...value, blankMedication()])}>手动添加药物</button>
    </div></div>
    {notice || catalogError ? <p role="status" className="field-row__hint">{notice || catalogError}</p> : null}
    {!value.length ? <p className="empty-inline">尚无药物记录。请填写实际方案，或在完整核对后确认无药。</p> : null}
    {value.map((m, i) => <details className="medication-card" key={m.medication_id ?? `draft-${i}`} open={!m.medication_id || undefined}>
      <summary><strong>{m.name || '待填写药名'}</strong><span>{m.dose || '剂量待填写'} · {m.status}</span><span>{purposesOf(m).join('、') || '用途待核对'}</span></summary>
      <div className="form-grid">
        <FieldRow label="药物名称">{p => <div className="input-with-action"><input {...p} className="input" value={m.name} onChange={e => update(i, {name: e.target.value})} /><button type="button" className="btn btn--text" aria-label={`为第${i+1}张药物卡选择常用药物`} title="选择常用药物" onClick={() => open(i)}>▾</button></div>}</FieldRow>
        <FieldRow label="剂量/用法" hint="未知请写“待核对”，不根据药名推断。">{p => <input {...p} className="input" value={m.dose} onChange={e => update(i, {dose: e.target.value})} />}</FieldRow>
        <FieldRow label="使用状态">{p => <select {...p} className="select" value={m.status} onChange={e => update(i, {status: e.target.value as Medication['status'], stopped_on: e.target.value === '已停用' ? m.stopped_on : null})}><option>使用中</option><option>已停用</option><option>待核对</option></select>}</FieldRow>
        <FieldRow label="有降糖作用">{p => <select {...p} className="select" value={m.has_glucose_lowering_effect == null ? '' : String(m.has_glucose_lowering_effect)} onChange={e => update(i, {has_glucose_lowering_effect: e.target.value === '' ? null : e.target.value === 'true'})}><option value="">待核实</option><option value="true">是</option><option value="false">否</option></select>}</FieldRow>
        <FieldRow label="开始时间精度">{p => <select {...p} className="select" value={m.start_precision ?? (m.started_on ? 'day' : 'unknown')} onChange={e => update(i, {start_precision: e.target.value as Medication['start_precision'], start_value: null, started_on: null})}><option value="unknown">不详</option><option value="year">仅年份</option><option value="month">仅年月</option><option value="day">完整日期</option></select>}</FieldRow>
        {m.start_precision === 'day' || (!m.start_precision && m.started_on) ? <FieldRow label="开始日期">{p => <DateInput {...p} value={m.start_value ?? m.started_on ?? ''} onChange={v => update(i, {start_value: v || null, started_on: v || null})} />}</FieldRow> : null}
        {m.start_precision === 'year' || m.start_precision === 'month' ? <FieldRow label={m.start_precision === 'year' ? '开始年份' : '开始年月'} hint="按实际已知精度填写，不补造具体日。">{p => <input {...p} className="input num" placeholder={m.start_precision === 'year' ? 'YYYY' : 'YYYY-MM'} value={m.start_value ?? ''} onChange={e => update(i, {start_value: e.target.value || null})} />}</FieldRow> : null}
        {m.status === '已停用' ? <FieldRow label="实际停用日">{p => <DateInput {...p} value={m.stopped_on ?? ''} onChange={v => update(i, {stopped_on: v || null})} />}</FieldRow> : null}
      </div>
      <CheckboxGroup legend="用药目的（可多选）" values={purposesOf(m)} options={[...purposes, ...(purposesOf(m).includes('器官获益') ? ['器官获益'] : [])].map(v => ({value: v, label: v}))} onChange={v => update(i, {purposes: v, purpose: null})} />
      {!m.medication_id || allowRemoveSaved ? <button type="button" className="btn btn--text" onClick={() => onChange(value.filter((_, index) => index !== i))}>{m.medication_id ? '从本次方案移除' : '移除未保存药物'}</button> : null}
      {m.medication_id ? <p className="field-row__hint">移除只影响本次方案，历史保留；实际停药仍须单独核对状态和日期。</p> : null}
    </details>)}
    <dialog ref={dialog} className="clinical-dialog medication-picker" onCancel={e => {e.preventDefault(); close()}} aria-label="选择常用药物">
      <div className="section-heading"><h2>选择常用药物</h2><button type="button" className="btn btn--text" onClick={close}>关闭</button></div>
      <p>先选类别，再勾选药名；可跨类别多选。确认后每个药名生成一张药物卡。</p>
      <label className="field-row">搜索药名<input className="input" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <div className="medication-picker__columns"><nav aria-label="药物类别">{catalog?.categories.map(c => <button key={c.id} type="button" className={`btn ${category === c.id ? 'btn--primary' : 'btn--text'}`} aria-pressed={category === c.id} onClick={() => {setCategory(c.id); setSearch('')}}>{c.name}</button>)}</nav>
        <div className="medication-picker__names">{choices.map(m => <label key={m.id}><input type="checkbox" checked={selected.includes(m.id)} onChange={e => setSelected(v => e.target.checked ? [...v, m.id] : v.filter(id => id !== m.id))} />{m.name}</label>)}{!choices.length ? <p>{catalog ? '未找到，可取消后手动输入。' : catalogError || '正在加载目录…'}</p> : null}</div></div>
      <div className="selection-summary" aria-live="polite">已选 {selected.length} 项：{entries.filter(m => selected.includes(m.id)).map(m => m.name).join('、') || '无'}</div>
      <div className="dialog-actions"><button type="button" className="btn btn--outlined" onClick={close}>取消</button><button type="button" className="btn btn--primary" disabled={!selected.length} onClick={addSelected}>添加所选药物</button></div>
    </dialog>
  </section>
}
