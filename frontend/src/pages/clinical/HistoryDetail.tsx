import { useState } from 'react'
import { ErrorBanner } from '../../components'
import { clinicalDataApi } from './api'
import { historicalSource } from '../../presentation'

const labels: Record<string, string> = {
  补正前: '补正前', 补正后: '补正后', medications: '药物方案', complete: '已完整核对', before: '补正前', after: '补正后',
  intervention_other: '其他干预说明', f001_t2dm_established: '成人T2DM', f002_acute_unsafe: '急性不安全', f003_type_doubt: '分型疑点', f004_treatment_context_sufficient: '治疗背景充分', f005_refused: '患者拒绝',
  f061_conclusion: '医生结论', f011_hold_reasons: '暂缓原因', f012_pre_tasks: '定向任务', opportunity_info: '机会信息', f016_medications: '当时用药方案',
  f018_weight: '新增体重（kg）', f019_height: '首次确认身高（cm）', measurement_snapshot: '当时测量', clinical_date: '评估采用日期', tasks: '待处理事项',
  duration_years: '病程年', duration_months: '病程月', measured_on: '测量日期', years: '年', months: '月',
  f026_start: '启动决定', f013_diagnosis_basis: '诊断依据', recent_examination: '近期检查', examinations: '新增检查',
  f015_recent_glucose: '近期血糖摘要', f015_test_date: '近期血糖日期', recent_glucose_reliable: '血糖摘要可靠性',
  f016_no_medication_confirmed: '旧版无药核对', medication_review_complete: '用药核对完整', current_medication_confirmation: '本次用药核对结论',
  f023_constraints: '管理约束', f024_willing: '干预意愿', f025_review_accept: '接受复评', f027_stage: '管理阶段', f028_stage_goal: '主要目标', f029_interventions: '计划干预', next_review_date: '下次复评日期',
  f030_safety_issues: '安全问题', f031_stage_indicator: '阶段指标', f032_treatment_changes: '治疗变化', f033_executable: '执行情况', f034_action: '复评动作', f035_stop_last_med: '停药决定', f057_actual_stop: '实际执行状态', planned_stop_date: '计划停药日', f036_stop_date: '最后实际停药日', f053_has_drug: '仍有降糖作用药', f054_purpose: '本次主要用途', f060_non_diabetic_on_treatment: '治疗下达非糖尿病范围', f056_uncontrolled: '明显失控', f062_target_stage: '返回阶段', stage_goal: '阶段目标', adjustment_summary: '调整内容', end_reason: '结束原因',
  anchors: '实际观察锚点', f063_applicable_interventions: '实际适用干预', f038_lifestyle_start_date: '生活方式开始日', f039_surgery_date: '实际手术日',
  f041_diagnosis_credible: '既往诊断可信', f042_drug_free_3m: '停药满3个月', f043_hba1c_reliable: 'HbA1c可解释', f059_completeness: '资料完整性', f058_examination: '本次判定检查', f048_confirm: '医生缓解决定',
  f049_glucose: '本次血糖摘要', f049_test_date: '本次检测日期', f050_med_status: '用药状态', f055_glucose_state: '医生判定血糖状态', f051_risk_triggers: '风险线索', risk_increase_confirmed: '医生确认风险上升', f037_reason: '重新用药原因',
  result: '前置复核结果', doctor_confirmed: '医生确认', evidence_summary: '相关证据', interventions: '干预组合', reason: '原因', remission_termination_confirmed: '确认缓解终止',
  name: '药物名称', dose: '剂量/用法', status: '使用状态', has_glucose_lowering_effect: '有降糖作用', purpose: '旧版用途', purposes: '用药目的', started_on: '完整开始日期', stopped_on: '实际停用日', start_precision: '开始时间精度', start_value: '已知开始时间',
  kind: '指标', value: '数值', text: '报告摘要', unit: '单位', source: '来源', test_date: '检测日期', report_start_date: '报告开始日', report_end_date: '报告结束日', reliability: '可靠性', independently_reviewed: '替代指标独立复核', note: '补充说明',
  height_cm: '确认身高（cm）', weight_kg: '体重（kg）', bmi: 'BMI', date_basis: '日期来源',
}
const hidden = new Set(['record_id', 'replacement_id', 'source_event_id', 'legacy', 'operator_id', 'request_id', 'expected_revision', 'clinical_contract_version', 'input_schema_version', 'regimen_source_id', 'measurement_id', 'examination_ids', 'record_refs', 'f058_examination_id', 'assessment_event_id', 'medication_id', 'catalog_id', 'category_id', 'transition_id'])
const words: Record<string, string> = {day: '完整日期', month: '仅年月', year: '仅年份', unknown: '不详'}

/** 使用当时payload，不用当前资料覆盖历史；工程字段不进入医生视图。 */
export function PayloadView({value, fieldKey}: {value: unknown; fieldKey?: string}) {
  if (value == null || value === '') return <span className="field-row__hint">未记录</span>
  if (typeof value === 'boolean') return <span>{value ? '是' : '否'}</span>
  if (typeof value !== 'object') return <span>{fieldKey === 'source' ? historicalSource(String(value)) : words[String(value)] ?? String(value)}</span>
  if (Array.isArray(value)) return value.length ? <ul className="detail-list">{value.map((v, i) => <li key={i}><PayloadView value={v} /></li>)}</ul> : <span className="field-row__hint">未记录条目</span>
  return <dl className="clinical-detail">{Object.entries(value).filter(([k]) => !hidden.has(k)).map(([k, v]) => <div key={k}><dt>{labels[k] ?? '补充资料'}</dt><dd><PayloadView value={v} fieldKey={k} /></dd></div>)}</dl>
}

export default function HistoryDetail({patientId, eventId}: {patientId: number; eventId: number}) {
  const [data, setData] = useState<Awaited<ReturnType<typeof clinicalDataApi.detail>> | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  async function load() { if (data || loading) return; setLoading(true); setError(''); try {setData(await clinicalDataApi.detail(patientId, eventId))} catch (e) {setError(e instanceof Error ? e.message : '详情读取失败')} finally {setLoading(false)} }
  return <details className="event-detail" onToggle={e => {if (e.currentTarget.open) void load()}}><summary>查看本次完整资料</summary>{error ? <ErrorBanner message={error} action={<button className="btn btn--text" onClick={() => void load()}>重新读取</button>} /> : null}{loading ? <p>正在读取…</p> : null}{data ? <><p className="field-row__hint">记录医生：{data.operator_display_name} · 记录于 {data.created_at.replace('T', ' ').slice(0,16)}</p><PayloadView value={data.payload} />{data.corrections.length ? <div className="clinical-summary"><h4>后续资料补正（原结论保持当时记录）</h4>{data.corrections.map(r => <div key={r.id}><p>{r.created_at.replace('T', ' ').slice(0,16)} · {r.operator_display_name ?? '历史账号'} · {String(r.data.reason)}</p><PayloadView value={{补正前: r.data.before, 补正后: r.data.after}} /></div>)}</div> : null}</> : null}</details>
}
