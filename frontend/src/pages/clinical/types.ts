/** v0.4输入资料与临床v0.3契约分离；缺失资料始终保留未知。 */
export interface Medication {
  medication_id?: string | null
  catalog_id?: string | null
  category_id?: string | null
  name: string
  dose: string
  status: '使用中' | '已停用' | '待核对'
  has_glucose_lowering_effect: boolean | null
  purpose?: '高血糖治疗' | '器官获益' | '体重获益' | '其他' | null
  purposes?: string[]
  started_on: string | null
  stopped_on: string | null
  start_precision?: 'day' | 'month' | 'year' | 'unknown'
  start_value?: string | null
}
export interface Examination {
  kind: string
  value: number | null
  text?: string | null
  unit: string
  source: string
  test_date: string | null
  report_start_date?: string | null
  report_end_date: string | null
  reliability: string
  independently_reviewed: boolean
  note?: string | null
}
export interface Measurement {
  weight_kg: number
  height_cm: number | null
  bmi: number | null
  measured_on: string | null
  date_basis?: string
}
export interface DataRecord<T> {
  id: number
  kind: string
  data: T
  clinical_date: string | null
  source_event_id: number | null
  supersedes_id: number | null
  created_at: string
  operator_display_name?: string | null
  operator_id?: number
}
export interface ClinicalContext {
  suggested_review_date?: string
  drug_free_3m?: string
  patient_revision: number
  measurement: DataRecord<Measurement> | null
  measurements: DataRecord<Measurement>[]
  weight_reduction_percent: number | null
  regimen: DataRecord<{ medications: Medication[]; complete: boolean }> | null
  duration: DataRecord<{ years: number | null; months: number | null }> | null
  examinations: DataRecord<Examination>[]
  carried: Record<string, string | string[]>
}
export interface MedicationCatalog {
  version: string
  categories: {id: string; name: string; medications: { id: string; name: string; aliases: string[] }[]}[]
}

export function medicationState(meds: Medication[], complete: boolean): '是' | '否' | '待核实' {
  if (meds.some(m => m.status === '使用中' && m.has_glucose_lowering_effect === true)) return '是'
  if (!complete || meds.some(m => m.status === '待核对' || (m.status === '使用中' && m.has_glucose_lowering_effect == null))) return '待核实'
  return '否'
}
export function purposesOf(m: Medication): string[] {
  if (m.purposes?.length) return m.purposes
  return m.purpose ? [{高血糖治疗: '降糖治疗', 器官获益: '器官获益', 体重获益: '体重管理', 其他: '其他'}[m.purpose]] : []
}
export function medicationStatus(meds: Medication[], complete: boolean): string {
  const state = medicationState(meds, complete)
  if (state === '否') return '未使用'
  if (state === '待核实') return '待核对'
  const purposes = new Set(meds.filter(m => m.status === '使用中' && m.has_glucose_lowering_effect).flatMap(purposesOf))
  const reasons = [purposes.has('降糖治疗') ? '因高血糖' : '', purposes.has('器官获益') || purposes.has('肾脏保护') || purposes.has('心血管保护') ? '因器官获益' : '', purposes.has('体重管理') ? '因体重获益' : ''].filter(Boolean)
  return reasons.length === 1 ? reasons[0]! : '待核对'
}

/** 当前摘要默认每种指标取最近一条，全部历史仍可展开查看/另行选择。 */
export function latestExaminations(rows: DataRecord<Examination>[], today: string): DataRecord<Examination>[] {
  const sorted = [...rows].filter(r => !(r.data.report_end_date || r.data.test_date) || (r.data.report_end_date || r.data.test_date)! <= today)
    .sort((a,b) => (b.data.report_end_date || b.data.test_date || '').localeCompare(a.data.report_end_date || a.data.test_date || '') || b.id-a.id)
  const kinds = new Set<string>()
  return sorted.filter(r => {if (kinds.has(r.data.kind)) return false; kinds.add(r.data.kind); return true})
}
