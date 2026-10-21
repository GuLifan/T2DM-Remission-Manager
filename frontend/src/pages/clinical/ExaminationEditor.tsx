import { DateInput, FieldRow } from '../../components'
import type { DataRecord, Examination } from './types'
import { historicalSource } from '../../presentation'

export const examinationSummary = (exams: Examination[]) => exams.map(e => `${e.kind} ${e.value ?? e.text ?? ''}${e.unit}（${e.report_end_date || e.test_date || '日期待核对'}，${e.reliability}）`).join('；')
export const blankExamination = (): Examination => ({kind: 'HbA1c', value: null, unit: '%', source: '本院检查', test_date: null, report_end_date: null, reliability: '可靠', independently_reviewed: false})

/** 多检查编辑与已保存资料引用分开；摘要直接从同一组资料生成。 */
export default function ExaminationEditor({value, onChange, saved, selectedIds, onSelect, selectedJudge, onJudge}: {
  value: Examination[]; onChange: (v: Examination[]) => void; saved: DataRecord<Examination>[];
  selectedIds: number[]; onSelect: (v: number[]) => void; selectedJudge?: string; onJudge?: (v: string) => void
}) {
  function update(index: number, patch: Partial<Examination>) { onChange(value.map((e, i) => i === index ? {...e, ...patch} : e)) }
  const eligible = ['HbA1c', 'FPG', 'CGM估算HbA1c']
  function selector(key: string, e: Examination) { return onJudge && eligible.includes(e.kind) ? <label className="judge-choice"><input type="radio" name="judge-examination" value={key} checked={selectedJudge === key} onChange={() => onJudge(key)} />作为本次缓解判定检查</label> : null }
  return <section className="examination-section" aria-label="检查资料">
    <div className="section-heading"><h3>检查资料</h3><button type="button" className="btn btn--outlined" onClick={() => onChange([...value, blankExamination()])}>添加检查</button></div>
    {saved.length ? <details className="saved-exams" open><summary>已有检查（保留原检测日期）</summary>{saved.map(r => <div className="saved-exam" key={r.id}><label><input type="checkbox" checked={selectedIds.includes(r.id)} onChange={e => onSelect(e.target.checked ? [...selectedIds, r.id] : selectedIds.filter(id => id !== r.id))} />{examinationSummary([r.data])}</label>{selector(`saved:${r.id}`, r.data)}</div>)}</details> : null}
    {value.map((exam, i) => <div className="card card--muted examination-card" key={i}>
      <div className="form-grid">
        <FieldRow label="检查类型">{p => <select {...p} className="select" value={exam.kind} onChange={e => update(i, {kind: e.target.value, value: null, text: '', unit: ['FPG', '指尖血糖'].includes(e.target.value) ? 'mmol/L' : ['HbA1c', 'CGM估算HbA1c'].includes(e.target.value) ? '%' : ''})}>{['HbA1c', 'FPG', '指尖血糖', 'CGM摘要', 'CGM估算HbA1c', '其他可靠近期资料'].map(v => <option key={v}>{v}</option>)}</select>}</FieldRow>
        {['CGM摘要', '其他可靠近期资料'].includes(exam.kind) ? <FieldRow label="检查摘要">{p => <textarea {...p} className="input" value={exam.text ?? ''} onChange={e => update(i, {text: e.target.value})} />}</FieldRow> : <FieldRow label="检查结果">{p => <input {...p} className="input num" type="number" min="0" step="any" value={exam.value ?? ''} onChange={e => update(i, {value: e.target.value === '' ? null : Number(e.target.value)})} />}</FieldRow>}
        <FieldRow label="单位">{p => <input {...p} className="input" value={exam.unit} readOnly={['HbA1c', 'FPG', 'CGM估算HbA1c'].includes(exam.kind)} onChange={e => update(i, {unit: e.target.value})} />}</FieldRow>
        <FieldRow label={exam.kind.startsWith('CGM') ? '报告结束日' : '检测日期'}>{p => <DateInput {...p} value={(exam.kind.startsWith('CGM') ? exam.report_end_date : exam.test_date) ?? ''} onChange={v => update(i, exam.kind.startsWith('CGM') ? {report_end_date: v || null} : {test_date: v || null})} />}</FieldRow>
        {exam.kind.startsWith('CGM') ? <FieldRow label="报告开始日（选填）">{p => <DateInput {...p} value={exam.report_start_date ?? ''} onChange={v => update(i, {report_start_date: v || null})} />}</FieldRow> : null}
        <FieldRow label="结果来源">{p => <select {...p} className="select" value={['本院检查', '外院检验', '患者提供', '测试数据', '其他'].includes(exam.source) ? exam.source : '其他'} onChange={e => update(i, {source: e.target.value})}>{['本院检查', '外院检验', '患者提供', ...(exam.source === '测试数据' ? ['测试数据'] : []), '其他'].map(v => <option key={v} value={v}>{historicalSource(v)}</option>)}</select>}</FieldRow>
        {!['本院检查', '外院检验', '患者提供', '测试数据'].includes(exam.source) ? <FieldRow label="来源说明">{p => <input {...p} className="input" value={exam.source === '其他' ? '' : exam.source} onChange={e => update(i, {source: e.target.value || '其他'})} />}</FieldRow> : null}
        <FieldRow label="结果可靠性">{p => <select {...p} className="select" value={exam.reliability} onChange={e => update(i, {reliability: e.target.value})}>{['可靠', '不可靠', '待复核'].map(v => <option key={v}>{v}</option>)}</select>}</FieldRow>
      </div>
      {selector(`new:${i}`, exam)}
      <button type="button" className="btn btn--text" onClick={() => {onChange(value.filter((_, j) => i !== j)); if (onJudge) onJudge('')}}>移除未保存检查</button>
    </div>)}
    <p className="clinical-summary"><strong>检查摘要：</strong>{examinationSummary([...saved.filter(r => selectedIds.includes(r.id)).map(r => r.data), ...value]) || '尚无本次采用的检查资料'}</p>
  </section>
}
