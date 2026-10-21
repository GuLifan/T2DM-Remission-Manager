import { ChoiceGroup, DateInput, FieldRow } from '../../components'

export function TextField({label, value, onChange, hint}: {label: string; value: string; onChange: (v: string) => void; hint?: string}) {
  return <FieldRow label={label} hint={hint}>{props => <input {...props} className="input" value={value} onChange={e => onChange(e.target.value)} />}</FieldRow>
}
export function SelectField({label, value, onChange, options, hint}: {label: string; value: string; onChange: (v: string) => void; options: string[]; hint?: string}) {
  const meaningful = options.filter(Boolean)
  const labels: Record<string, string> = {reference: '沿用上次测量', new: '新增体重', P04: '确认缓解终止，返回完整评估', P05A: '获益用药，进入血糖稳定', P05B: '获益用药，进入缓解诱导'}
  if (meaningful.length <= 4) return <ChoiceGroup legend={label} description={hint} value={value || null} onChange={onChange} options={meaningful.map(v => ({value: v, label: labels[v] ?? v}))} />
  return <FieldRow label={label} hint={hint}>{props => <select {...props} className="select" value={value} onChange={e => onChange(e.target.value)}><option value="">待选择</option>{meaningful.map(v => <option key={v} value={v}>{labels[v] ?? v}</option>)}</select>}</FieldRow>
}
export function DateField({label, value, onChange, hint, max}: {label: string; value: string; onChange: (v: string) => void; hint?: string; max?: string}) {
  return <FieldRow label={label} hint={hint}>{props => <DateInput {...props} max={max} value={value} onChange={onChange} />}</FieldRow>
}
