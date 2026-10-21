import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../api/client'
import { clinicalV03Api, testSupportApi } from '../../api/endpoints'
import { AssessmentMeasurementFields, CheckboxGroup, ConfirmDialog, ErrorBanner, LoadingBlock, ResultBanner } from '../../components'
import { useAsync } from '../../hooks/useAsync'
import type { ClinicalV03Result, Patient } from '../../types'
import { clinicalDataApi } from './api'
import AssessmentForms from './AssessmentForms'
import { initialValues } from './defaults'
import { confirmationSummary } from './confirmationSummary'
import ExaminationEditor, { examinationSummary } from './ExaminationEditor'
import { DateField, SelectField, TextField } from './Fields'
import MedicationEditor from './MedicationEditor'
import type { ClinicalContext, Examination, Medication } from './types'
import { latestExaminations, medicationState, medicationStatus } from './types'

interface Props { patient: Patient; onUpdated: () => void }
const actualInterventions = ['结构化生活方式', '代谢手术', '其他']

/** 先读取本病例资料再初始化草稿；异步刷新不覆盖正在输入的内容。 */
export default function ClinicalPage({patient, onUpdated}: Props) {
  const data = useAsync(signal => clinicalDataApi.context(patient.id, signal), [patient.id])
  const lastOwnRevision = useRef<number | null>(null)
  const ownObjective = useRef(false)
  const clock = useAsync(signal => testSupportApi.context(signal), [patient.id])
  if (!data.data || !clock.data) return <>{data.error || clock.error ? <ErrorBanner message={data.error || clock.error} action={<button className="btn btn--outlined" onClick={() => {data.reload(); clock.reload()}}>重新加载资料</button>} /> : <LoadingBlock message="正在读取病例资料…" />}</>
  // 普通保存后等待病例状态与资料同时刷新，避免短暂展示旧方案并覆盖新输入。
  // 同次E4客观核对保持表单，以便继续独立确认。
  if (lastOwnRevision.current !== null && !ownObjective.current &&
      (data.data.patient_revision < lastOwnRevision.current || patient.clinical_revision < lastOwnRevision.current)) {
    return <LoadingBlock message="记录已保存，正在更新本次病例资料…" />
  }
  const stale = patient.clinical_revision > data.data.patient_revision && patient.clinical_revision !== lastOwnRevision.current
  return <>
    {stale ? <ErrorBanner message="病例资料已更新，当前未保存内容仍保留；请载入最新资料后重新核对。" action={<button type="button" className="btn btn--outlined" onClick={() => {lastOwnRevision.current = null; data.reload()}}>载入最新资料（放弃本页草稿）</button>} /> : null}
    <fieldset className="permission-lock" disabled={stale} style={{border: 0, padding: 0, margin: 0, minWidth: 0}}>
      <ClinicalForm key={`${patient.id}:${patient.current_state}:${data.data.patient_revision}`} patient={patient} context={data.data} today={clock.data.effective_date}
        onCommitted={(objective, revision) => {lastOwnRevision.current = revision; ownObjective.current = objective; if (!objective) data.reload(); onUpdated()}} />
    </fieldset>
  </>
}

function ClinicalForm({patient, context, today, onCommitted}: {
  patient: Patient; context: ClinicalContext; today: string; onCommitted: (objective: boolean, revision: number) => void
}) {
  const [v, setV] = useState(() => initialValues(patient, context, today))
  const set = (key: string) => (value: string) => setV(current => ({...current, [key]: value}))
  const [holds, setHolds] = useState<string[]>([])
  const [interventions, setInterventions] = useState<string[]>(() => {
    const previous = context.carried.f029_interventions
    return Array.isArray(previous) ? previous : patient.interventions?.split('、') ?? []
  })
  const [anchors, setAnchors] = useState<string[]>(patient.applicable_interventions ?? [])
  const [safety, setSafety] = useState<string[]>(['无'])
  const [changes, setChanges] = useState<string[]>(['无'])
  const [risks, setRisks] = useState<string[]>(['无'])
  const [constraints, setConstraints] = useState<string[]>(Array.isArray(context.carried.f023_constraints) ? context.carried.f023_constraints : [])
  const [medications, setMedications] = useState<Medication[]>(context.regimen?.data.medications ?? [])
  const [complete, setComplete] = useState(context.regimen?.data.complete ?? false)
  const [reconciled, setReconciled] = useState(false)
  const inheritedDrug = medicationState(context.regimen?.data.medications ?? [], context.regimen?.data.complete ?? false)
  const inheritedFact = inheritedDrug === '待核实' ? null : inheritedDrug === '是'
  const medicationMismatch = Boolean(context.regimen && ['ST31','ST32','ST40','ST50','ST60'].includes(patient.current_state) && inheritedFact !== patient.has_glucose_lowering_drug)
  const [measurementMode, setMeasurementMode] = useState(context.measurement ? 'reference' : 'new')
  const [examinations, setExaminations] = useState<Examination[]>([])
  const [examIds, setExamIds] = useState<number[]>(latestExaminations(context.examinations, today).map(e => e.id))
  const [judgeKey, setJudgeKey] = useState('')
  const [result, setResult] = useState<ClinicalV03Result | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmation, setConfirmation] = useState<{action: string; payload: Record<string, unknown>; title: string; review: string} | null>(null)
  const root = useRef<HTMLDivElement>(null)
  // 草稿绑定初始化资料版本；只允许自己的成功提交推进，不跟随外部资料变化。
  const revision = useRef(context.patient_revision)
  const refreshed = useRef('')
  const objectiveSignature = useRef('')
  const signature = JSON.stringify([v, medications, complete, anchors, measurementMode, examinations, examIds, judgeKey])
  useEffect(() => { if (result?.objective_met && objectiveSignature.current !== signature) setResult(null) }, [signature, result?.objective_met])

  const selectedExams = [...context.examinations.filter(e => examIds.includes(e.id)).map(e => e.data), ...examinations]
  const summary = examinationSummary(selectedExams)
  const systemDrug = medicationState(medications, complete)
  const measurement = {
    f018_weight: measurementMode === 'new' && v.weight !== '' ? Number(v.weight) : null,
    f019_height: patient.height_cm == null && v.height !== '' ? Number(v.height) : null,
    measurement_id: measurementMode === 'reference' ? context.measurement?.id ?? null : null,
    measured_on: measurementMode === 'new' && v.weight ? v.measuredOn || null : null,
    duration_years: v.years === '' ? null : Number(v.years), duration_months: v.months === '' ? null : Number(v.months),
    examinations, examination_ids: examIds,
    intervention_other: interventions.includes('其他') ? v.otherIntervention || null : null,
  }
  const regimen = {f016_medications: medications, regimen_source_id: context.regimen?.id ?? null,
    medication_reconciliation_confirmed: reconciled,
    medication_review_complete: complete, current_medication_confirmation: v.medicationConfirmation || null}
  const hasDrug = systemDrug === '待核实' ? null : systemDrug === '是'
  const anchorPayload = {f063_applicable_interventions: anchors,
    f038_lifestyle_start_date: anchors.includes('结构化生活方式') ? v.lifestyleDate || null : null,
    f039_surgery_date: anchors.includes('代谢手术') ? v.surgeryDate || null : null}

  function complain(message: string) {
    setError(message)
    window.setTimeout(() => {
      const invalid = root.current?.querySelector<HTMLElement>('[data-invalid-date="true"], input:invalid, [aria-invalid="true"]')
      const banner = root.current?.querySelector<HTMLElement>('[role="alert"]')
      ;(invalid ?? banner)?.scrollIntoView({block: 'center', behavior: 'smooth'}); invalid?.focus()
    }, 0)
  }
  async function run(action: string, payload: Record<string, unknown>) {
    setError('')
    if (medicationMismatch && Array.isArray(payload.f016_medications) && !reconciled) {complain('请先明确核对历史药物不一致，再确认本次当前方案。'); return}
    if (root.current?.querySelector('[data-invalid-date="true"]')) {complain('日期输入尚未有效，请修正标红日期后保存。'); return}
    if (measurement.f018_weight !== null && (!Number.isFinite(measurement.f018_weight) || measurement.f018_weight <= 0)) {complain('请填写有效体重。'); return}
    const required: Record<string, string[]> = {
      'pre-assessment': ['t2dm', 'acute', 'typeDoubt', 'contextEnough', 'refused', 'conclusion'],
      'pre-recovery': ['recovery'], 'full-assessment': v.start === '启动' ? ['start', 'stage', 'medicationConfirmation'] : ['start'],
      'medication-restart': ['restartReason'], 'remission-judge': ['diagnosisCredible', 'drugFree', 'hbaReliable'],
      'post-remission': ['medStatus', 'glucoseState'],
    }
    if ((required[action] ?? []).some(key => !v[key])) {complain('请完成本次必选的事实核对与医生决定。'); return}
    if (v.years !== '' && v.months !== '' && Number(v.months) >= 12) {complain('填写病程年后，月只能为0—11；只填月时可填18个月。'); return}
    if ([v.years, v.months].some(n => n !== '' && (!Number.isInteger(Number(n)) || Number(n) < 0))) {complain('病程年、月请填写非负整数或留空。'); return}
    if (action === 'full-assessment' && v.start === '启动' && !constraints.length) {complain('请核对管理约束；没有时选择无。'); return}
    if (action === 'full-assessment' && v.start === '启动' && ((!measurement.measurement_id && !measurement.f018_weight) || (!patient.height_cm && !measurement.f019_height && !context.measurement?.data.height_cm))) {complain('首次启动请补齐体重与确认身高，或沿用已有测量。'); return}
    const labels: Record<string, string> = {'pre-assessment': '保存预评估结论', 'pre-recovery': '保存前置复核', 'full-assessment': '保存完整评估', 'phase-review': '保存本次复评', 'observation-anchors': '保存日期核对', 'medication-restart': '确认重新用药', 'remission-judge': '核对客观条件', 'remission-confirm': '保存本次缓解决定', 'post-remission': '保存缓解后复评', 'supplemental-decision': '确认返回处理'}
    if (action === 'post-remission' && v.glucoseDate > today) {complain('检测日期不能晚于本次业务日期，请修正检测日期。'); return}
    setConfirmation({action, payload: {input_schema_version: 'v0.4', ...payload}, title: labels[action] ?? '保存本次记录', review: `${measurementMode === 'reference' ? `沿用体重 ${context.measurement?.data.weight_kg ?? '待核对'} kg` : `本次体重 ${v.weight || '未填'} kg`}\n${summary}`})
  }
  async function execute() {
    if (!confirmation || submitting) return
    const {action, payload} = confirmation
    setConfirmation(null); setSubmitting(true)
    try {
      const response = await clinicalV03Api.submit(patient.id, action, revision.current, payload)
      setResult(response)
      revision.current = response.patient_revision
      if (response.objective_met) objectiveSignature.current = signature
      onCommitted(Boolean(response.objective_met), response.patient_revision)
    } catch (e) {complain(e instanceof ApiError ? e.message : '保存失败，请重试。')} finally {setSubmitting(false)}
  }
  useEffect(() => {
    if (patient.current_state !== 'ST40' || patient.archived || !patient.can_edit) return
    const key = `${patient.id}:${patient.clinical_revision}`
    if (refreshed.current === key) return
    refreshed.current = key
    clinicalV03Api.submit(patient.id, 'refresh', patient.clinical_revision, {}).then(r => {setResult(r); if (r.advanced) onCommitted(false, r.patient_revision)})
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : '观察状态刷新失败'))
  }, [patient.id, patient.current_state, patient.clinical_revision, patient.archived, patient.can_edit])

  async function submitPre() { await run('pre-assessment', {...measurement, ...regimen,
    f001_t2dm_established: v.t2dm, f002_acute_unsafe: v.acute, f003_type_doubt: v.typeDoubt,
    f004_treatment_context_sufficient: v.contextEnough, f005_refused: v.refused, f061_conclusion: v.conclusion,
    f011_hold_reasons: v.conclusion === '暂缓进入' ? holds : [], f012_pre_tasks: v.tasks || null, opportunity_info: {}}) }
  async function submitRecovery() { await run('pre-recovery', {...measurement, ...regimen, result: v.recovery, doctor_confirmed: true, evidence_summary: v.evidence, stage_goal: v.goal || null, interventions, f023_constraints: constraints, next_review_date: v.nextDate || null}) }
  async function submitFull() {
    if (v.start !== '启动') {
      await run('full-assessment', {...measurement, examinations: [], examination_ids: [], intervention_other: null, f026_start: v.start, f012_pre_tasks: v.tasks || null})
      return
    }
    await run('full-assessment', {...measurement, ...regimen,
    f026_start: v.start, f013_diagnosis_basis: v.diagnosis || null, recent_examination: null,
    f015_recent_glucose: summary || null, f015_test_date: null, recent_glucose_reliable: null,
    f016_no_medication_confirmed: false, f023_constraints: constraints, f024_willing: v.willing, f025_review_accept: v.reviewAccept,
    f027_stage: v.start === '启动' ? v.stage : null, f028_stage_goal: v.goal || null,
    f029_interventions: v.start === '启动' ? interventions : [], intervention_other: v.start === '启动' && interventions.includes('其他') ? v.otherIntervention || null : null, f012_pre_tasks: v.tasks || null, next_review_date: v.nextDate || null}) }
  async function submitPhase() {
    const stop = v.stopDecision === '是'
    await run('phase-review', {...measurement, ...regimen, f030_safety_issues: safety, f031_stage_indicator: v.stageIndicator || summary,
      f032_treatment_changes: changes, f033_executable: v.executable, f034_action: v.action, f035_stop_last_med: stop,
      f057_actual_stop: stop ? v.stopExecution : null, planned_stop_date: stop && v.stopExecution === '仅计划停用' ? v.plannedStopDate || null : null,
      f036_stop_date: stop && v.stopExecution === '已实际停用' ? v.actualStopDate || null : null,
      f053_has_drug: hasDrug, f054_purpose: hasDrug === true ? v.purpose || null : null,
      f060_non_diabetic_on_treatment: v.onTreatment, f056_uncontrolled: v.uncontrolled === '是',
      anchors: stop && v.stopExecution === '已实际停用' ? anchorPayload : null,
      f062_target_stage: v.action === '转换阶段' || v.uncontrolled === '是' ? v.stage : null,
      stage_goal: v.goal || null, adjustment_summary: v.action === '调整方案或目标' ? v.adjustment || null : null,
      end_reason: v.action === '结束主动管理' ? v.endReason || null : null, next_review_date: v.action === '结束主动管理' ? null : v.nextDate || null})
  }
  async function saveAnchors() {await run('observation-anchors', {anchors: anchorPayload})}
  async function restartMedication() {await run('medication-restart', {...regimen, f037_reason: v.restartReason, f062_target_stage: v.stage || null})}
  const judgeExam = judgeKey.startsWith('saved:') ? context.examinations.find(e => e.id === Number(judgeKey.split(':')[1]))?.data : judgeKey.startsWith('new:') ? examinations[Number(judgeKey.split(':')[1])] : undefined
  const judgeDate = judgeExam?.report_end_date || judgeExam?.test_date
  const completeness = !judgeExam || !judgeDate || !complete || !patient.earliest_judge_date ? '缺失'
    : judgeDate > today || judgeDate < patient.earliest_judge_date || today < patient.earliest_judge_date ? '时间未满足'
    : judgeExam.reliability !== '可靠' || v.hbaReliable === '待复核' || (v.hbaReliable === '否' && v.independent !== '是') ? '结果待复核' : '完整'
  function selectedJudgeExamination() {
    if (!judgeExam) return null
    const {kind, value, unit, source, test_date, report_start_date, report_end_date, reliability} = judgeExam
    return {kind, value, unit, source, test_date, report_start_date: report_start_date ?? null, report_end_date, reliability, independently_reviewed: v.independent === '是'}
  }
  async function submitJudge() {await run('remission-judge', {...measurement, ...regimen,
    f041_diagnosis_credible: v.diagnosisCredible, f042_drug_free_3m: v.drugFree, f043_hba1c_reliable: v.hbaReliable,
    f053_has_drug: hasDrug, f059_completeness: completeness, f058_examination: selectedJudgeExamination(),
    f058_examination_id: judgeKey.startsWith('saved:') ? Number(judgeKey.split(':')[1]) : null,
    f062_target_stage: hasDrug || (judgeExam?.value ?? 0) >= (judgeExam?.kind === 'FPG' ? 7 : 6.5) ? v.stage : null,
    f012_pre_tasks: v.tasks || null, anchors: anchorPayload})}
  async function confirmRemission(confirm: '确认' | '暂不确认') {
    if (!result?.assessment_event_id) {complain('请先完成当前资料的客观核对。'); return}
    await run('remission-confirm', {f048_confirm: confirm, assessment_event_id: result.assessment_event_id, f012_pre_tasks: confirm === '暂不确认' ? v.tasks || null : null})
  }
  async function submitPost() {await run('post-remission', {...measurement, ...regimen,
    f049_glucose: v.glucose || summary || null, f049_test_date: v.glucoseDate || null, f050_med_status: v.medStatus, f055_glucose_state: v.glucoseState,
    f051_risk_triggers: risks, risk_increase_confirmed: v.riskConfirmed === '是', f062_target_stage: v.medStatus === '因高血糖' || v.glucoseState === '达到糖尿病范围' ? v.stage : null,
    f012_pre_tasks: v.tasks || null, next_review_date: v.nextDate || null})}
  async function submitSupplement() {
    const map: Record<string, string> = {ST00: 'P01', ST31: 'P03A', ST32: 'P03B', ST50: 'P02'}
    const transition = patient.current_state === 'ST60' ? v.supplementChoice : map[patient.current_state]
    if (!transition) {complain('请选择后续管理方向。'); return}
    await run('supplemental-decision', {...(transition.startsWith('P05') ? regimen : {}), transition_id: transition, doctor_confirmed: true, reason: v.supplementReason, evidence_summary: v.supplementEvidence, remission_termination_confirmed: transition === 'P04', f050_med_status: transition.startsWith('P05') ? v.medStatus : null})
  }
  function applyExaminations(next: Examination[], ids = examIds) {
    setExaminations(next); setExamIds(ids)
    const combined = [...context.examinations.filter(e => ids.includes(e.id)).map(e => e.data), ...next]
    const generated = examinationSummary(combined)
    setV(current => ({...current, stageIndicator: generated, glucose: generated,
      glucoseDate: combined.map(e => e.report_end_date || e.test_date || '').sort().at(-1) ?? '',
      hbaReliable: '待复核', independent: '否', onTreatment: '待确认'}))
  }
  const examinationFields = <ExaminationEditor value={examinations} onChange={next => applyExaminations(next)}
    saved={context.examinations} selectedIds={examIds} onSelect={ids => {applyExaminations(examinations, ids); if (judgeKey.startsWith('saved:') && !ids.includes(Number(judgeKey.split(':')[1]))) setJudgeKey('')}} selectedJudge={judgeKey}
    onJudge={patient.current_state === 'ST50' ? key => {setJudgeKey(key); if (key.startsWith('saved:') && !examIds.includes(Number(key.split(':')[1]))) setExamIds(ids => [...ids, Number(key.split(':')[1])]); setV(current => ({...current, hbaReliable: '待复核', independent: '否'}))} : undefined} />
  const medicationFields = <><MedicationEditor value={medications} onChange={next => {setMedications(next); setReconciled(false); set('medicationConfirmation')(''); set('medStatus')(medicationStatus(next, complete)); set('onTreatment')('待确认')}} />
    <label className="review-complete"><input type="checkbox" checked={complete} onChange={e => {setComplete(e.target.checked); set('medicationConfirmation')(''); set('medStatus')(medicationStatus(medications, e.target.checked)); set('onTreatment')('待确认')}} />已完整核对当前方案，包括在用、停用和是否遗漏</label>
    <div className="medication-reconciliation">{medicationMismatch ? <><p role="alert">历史药物明细与既存汇总不一致。请核对当前方案、药物状态及用途；原记录保留。</p><label><input type="checkbox" checked={reconciled} onChange={e => setReconciled(e.target.checked)} />已核对历史药物不一致，本次以当前方案为准</label></> : null}<p><strong>系统提示：</strong>仍有降糖作用药物：{systemDrug}。空列表本身不代表无药。</p>
      {patient.current_state === 'ST20' ? <SelectField label="本次用药核对结论" value={v.medicationConfirmation} onChange={set('medicationConfirmation')} options={['是', '否', '待核实']} hint="请选择是否仍有降糖作用药物；本次必须由医生确认。" /> : null}</div></>
  const m = context.measurement
  const referenceHeight = patient.height_cm ?? (v.height ? Number(v.height) : m?.data.height_cm)
  const referenceBMI = m && referenceHeight ? (m.data.weight_kg / (referenceHeight / 100) ** 2).toFixed(1) : '未计算'
  const measurementFields = <section className="measurement-section"><div className="section-heading"><h3>测量与病程</h3>{m ? <SelectField label="体重记录方式" value={measurementMode} onChange={setMeasurementMode} options={['reference', 'new'].map(x => x)} /> : null}</div>
    {m && measurementMode === 'reference' ? <div className="clinical-summary"><strong>沿用体重 {m.data.weight_kg} kg</strong> · 测量日 {m.data.measured_on ?? '未单独记录'}{m.data.date_basis ? `（${m.data.date_basis}）` : ''} · BMI {referenceBMI}<button type="button" className="btn btn--text" onClick={() => setMeasurementMode('new')}>新增体重</button></div> : <div className="form-grid"><AssessmentMeasurementFields patient={patient} optional weight={v.weight} onWeightChange={set('weight')} height={v.height} onHeightChange={set('height')} /><DateField label="测量日期" value={v.measuredOn} onChange={set('measuredOn')} /></div>}
    {m && !patient.height_cm && measurementMode === 'reference' ? <TextField label="首次确认身高（cm）" value={v.height} onChange={set('height')} /> : null}
    <div className="duration-input"><span>糖尿病病程（选填）</span><label><input aria-label="病程年" className="input num" type="number" min="0" step="1" value={v.years} onChange={e => set('years')(e.target.value)} />年</label><label><input aria-label="病程月" className="input num" type="number" min="0" max={v.years !== '' ? '11' : undefined} step="1" value={v.months} onChange={e => set('months')(e.target.value)} />月</label><span className="field-row__hint">可只填其一；有年时月0—11，全空表示未知。</span></div>
    {context.weight_reduction_percent !== null ? <p className="field-row__hint">相对首次体重下降 {context.weight_reduction_percent.toFixed(1)}%</p> : null}
  </section>
  const anchorFields = <details className="card card--muted" open><summary>实际干预与观察时间</summary><CheckboxGroup legend="适用干预" values={anchors} onChange={setAnchors} options={actualInterventions.map(x => ({value: x, label: x}))} /><div className="form-grid">{anchors.includes('结构化生活方式') ? <DateField label="生活方式开始日" value={v.lifestyleDate} onChange={set('lifestyleDate')} /> : null}{anchors.includes('代谢手术') ? <DateField label="代谢手术日期" value={v.surgeryDate} onChange={set('surgeryDate')} /> : null}</div></details>

  return <div ref={root} className="clinical-workspace" aria-busy={submitting}>
    {error ? <ErrorBanner message={error} /> : null}
    {result?.output_text ? <ResultBanner text={result.output_text} tone={result.objective_met ? 'success' : result.tasks.length ? 'warning' : 'neutral'} /> : null}
    {result?.tasks.length ? <div className="clinical-summary"><strong>待处理事项</strong><ul>{result.tasks.map(t => <li key={t}>{t}</li>)}</ul></div> : null}
    <details className="clinical-context" open><summary>已有资料 · 本次只需更新变化</summary><p>诊断依据：{String(context.carried.f013_diagnosis_basis ?? '未记录')}　管理约束：{Array.isArray(context.carried.f023_constraints) ? context.carried.f023_constraints.join('、') || '待核对' : '未记录'}</p><p>用药：{context.regimen ? `沿用上次方案（${context.regimen.clinical_date ?? '日期未记录'}），${context.regimen.data.medications.map(med => `${med.name} ${med.dose} · ${med.status}`).join('；') || (context.regimen.data.complete ? '已完整核对无药' : '待核实')}` : '尚无保存方案'}</p>{summary ? <p>检查：{summary}</p> : null}</details>
    <AssessmentForms {...{patient, v: {...v, businessDate: today, completeness, hasDrug: systemDrug === '待核实' ? '' : systemDrug}, set, measurementFields, holds, setHolds, medications, setMedications, submitting, submitPre, submitRecovery, interventions, setInterventions, submitFull, safety, setSafety, changes, setChanges, anchorFields, submitPhase, saveAnchors, restartMedication, result, submitJudge, confirmRemission, risks, setRisks, submitPost, examinationFields, medicationFields, constraints, setConstraints}} />
    {['ST00', 'ST31', 'ST32', 'ST50', 'ST60'].includes(patient.current_state) ? <details className="section supplementary"><summary>重大变化后的返回处理</summary><p>仅新分型证据或重大变化时使用，保留医生原因与依据。</p><div className="form-grid">{patient.current_state === 'ST60' ? <SelectField label="后续方向" value={v.supplementChoice} onChange={set('supplementChoice')} options={['P04', 'P05A', 'P05B']} /> : null}<TextField label="医生决定原因" value={v.supplementReason} onChange={set('supplementReason')} /><TextField label="相关证据摘要" value={v.supplementEvidence} onChange={set('supplementEvidence')} />{patient.current_state === 'ST60' && v.supplementChoice.startsWith('P05') ? <SelectField label="获益用药原因" value={v.medStatus} onChange={set('medStatus')} options={['因器官获益', '因体重获益']} /> : null}</div><button type="button" className="btn btn--outlined" disabled={submitting} onClick={() => void submitSupplement()}>确认返回处理</button></details> : null}
    <ConfirmDialog open={Boolean(confirmation)} title={confirmation?.title ?? ''} confirmLabel={confirmation?.title ?? '保存本次记录'} cancelLabel="返回核对" onCancel={() => setConfirmation(null)} onConfirm={() => void execute()}
      description={`${patient.name} · ${today}\n${confirmation ? confirmationSummary(confirmation.action, confirmation.payload) : ''}\n${confirmation?.review ?? ''}\n保存后记录本次事实和医生决定，原历史记录保留。`} />
  </div>
}
