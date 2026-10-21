import type { Patient } from '../../types'
import type { ClinicalContext } from './types'
import { examinationSummary } from './ExaminationEditor'
import { latestExaminations, medicationState, medicationStatus } from './types'

/** 经Lifan批准的默认策略；本次必须选择的A04/B07/B09始终为空。 */
export function initialValues(patient: Patient, context: ClinicalContext, today: string): Record<string, string> {
  const c = context.carried
  const next = new Date(`${today}T12:00:00Z`); next.setUTCDate(next.getUTCDate()+84)
  if (patient.current_state === 'ST60' && patient.remission_confirmed_date) {
    const [year, month, day] = patient.remission_confirmed_date.split('-').map(Number)
    const addMonths = (n: number) => new Date(Date.UTC(year!, month! - 1+n, Math.min(day!, new Date(Date.UTC(year!, month!+n, 0)).getUTCDate()))).toISOString().slice(0,10)
    let n = [6,12,18,24].find(n => addMonths(n) > today) ?? 36
    while (addMonths(n) <= today) n += 12
    next.setTime(new Date(`${addMonths(n)}T12:00:00Z`).getTime())
  }
  const nextDate = patient.next_review_date && patient.next_review_date > today ? patient.next_review_date : next.toISOString().slice(0,10)
  const meds = context.regimen?.data.medications ?? []; const complete = context.regimen?.data.complete ?? false
  const stop = patient.last_med_stop_date
  let drugFree = '待核对'
  if (patient.actual_stop_confirmed && stop) {
    const [y, m, d] = stop.split('-').map(Number)
    const lastDay = new Date(Date.UTC(y!, m! + 3, 0)).getUTCDate()
    const due = new Date(Date.UTC(y!, m! - 1 + 3, Math.min(d!, lastDay))).toISOString().slice(0,10)
    drugFree = today >= due ? '是' : '否'
  }
  const recent = latestExaminations(context.examinations, today)
  const summary = examinationSummary(recent.map(e => e.data))
  return {
    weight: '', height: patient.height_cm?.toString() ?? '', t2dm: '是', acute: Array.isArray(c.pending_pre_tasks) && c.pending_pre_tasks.includes('急性安全') ? '是' : '否', typeDoubt: Array.isArray(c.pending_pre_tasks) && c.pending_pre_tasks.includes('分型存疑') ? '是' : '否',
    contextEnough: '', refused: '否', conclusion: '进入完整评估', tasks: '', recovery: '', evidence: '',
    otherIntervention: String(c.intervention_other ?? ''), start: '启动', diagnosis: String(c.f013_diagnosis_basis ?? ''), willing: '是', reviewAccept: '是',
    stage: patient.current_state === 'ST20' ? '' : patient.current_state === 'ST31' ? '缓解诱导' : patient.current_state === 'ST32' ? '血糖稳定' : patient.stage ?? String(c.previous_stage ?? '血糖稳定'),
    goal: patient.stage_goal ?? String(c.f028_stage_goal ?? c.stage_goal ?? ''),
    action: '继续当前阶段', executable: '可继续', stageIndicator: summary,
    stopDecision: '否', stopExecution: '待核对', plannedStopDate: '', actualStopDate: '',
    hasDrug: medicationState(meds, complete) === '待核实' ? '' : medicationState(meds, complete),
    purpose: ({因高血糖: '高血糖治疗', 因器官获益: '器官获益', 因体重获益: '体重获益'} as Record<string, string>)[medicationStatus(meds, complete)] ?? '', onTreatment: '待确认', uncontrolled: '否', adjustment: '', endReason: '', nextDate: context.suggested_review_date ?? nextDate,
    lifestyleDate: patient.lifestyle_start_date ?? '', surgeryDate: patient.surgery_date ?? '', restartReason: '',
    diagnosisCredible: Array.isArray(c.pending_pre_tasks) && c.pending_pre_tasks.includes('分型存疑') ? '待复核' : '是', drugFree: context.drug_free_3m ?? drugFree,
    hbaReliable: '待复核', completeness: '缺失', independent: '否', confirm: '', glucose: summary, glucoseDate: recent.map(e => e.data.report_end_date || e.data.test_date || '').sort().at(-1) ?? '',
    medStatus: medicationStatus(meds, complete), glucoseState: '暂不能可靠解释', riskConfirmed: '否',
    supplementReason: '', supplementEvidence: '', supplementChoice: '', medicationConfirmation: '',
    years: context.duration?.data.years?.toString() ?? '', months: context.duration?.data.months?.toString() ?? '', measuredOn: today,
  }
}
