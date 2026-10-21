import type { ReactNode } from 'react'
import { CheckboxGroup } from '../../components'
import type { ClinicalV03Result, Patient } from '../../types'
import { DateField, SelectField, TextField } from './Fields'
import type { Medication } from './types'
const safetyOptions = ['无', '低血糖', '急性高血糖', '其他安全问题']
const changeOptions = ['无', '生活方式调整', '药物调整', '手术相关变化', '其他变化']
const planOptions = ['结构化生活方式', '降糖治疗调整', '体重管理药物', '代谢手术评估', '其他']
const riskOptions = ['无', '体重回升', '生活方式变化', '血糖趋势升高', '其他风险']
interface FormProps {
  patient: Patient; v: Record<string, string>; set: (key: string) => (v: string) => void;
  measurementFields: ReactNode; anchorFields: ReactNode; examinationFields: ReactNode; medicationFields: ReactNode;
  holds: string[]; setHolds: (v: string[]) => void; medications: Medication[]; setMedications: (v: Medication[]) => void;
  interventions: string[]; setInterventions: (v: string[]) => void; safety: string[]; setSafety: (v: string[]) => void;
  changes: string[]; setChanges: (v: string[]) => void; risks: string[]; setRisks: (v: string[]) => void;
  constraints: string[]; setConstraints: (v: string[]) => void; submitting: boolean; result: ClinicalV03Result | null;
  submitPre: () => Promise<void>; submitRecovery: () => Promise<void>; submitFull: () => Promise<void>;
  submitPhase: () => Promise<void>; saveAnchors: () => Promise<void>; restartMedication: () => Promise<void>;
  submitJudge: () => Promise<void>; confirmRemission: (v: '确认' | '暂不确认') => Promise<void>; submitPost: () => Promise<void>;
}
/** 按当前临床事件选择表单；字段状态、保存和资料引用由ClinicalForm统一管理。 */
/** RegularCareForm：独立事件表单，只接收本环节使用的显示与操作。 */
function RegularCareForm(_props: FormProps) {
  return <section className="section"><h2 className="section__title">常规糖尿病综合管理</h2><p>当前不在主动缓解路径。条件或意愿改变时，由医生填写原因和相关资料，明确重新发起预评估。</p></section>
}

/** PreAssessmentForm：独立事件表单，只接收本环节使用的显示与操作。 */
function PreAssessmentForm(props: FormProps) {
  const {v, set, measurementFields, holds, setHolds, submitting, submitPre, submitRecovery, interventions, setInterventions, examinationFields, medicationFields, constraints, setConstraints} = props
  return (
      <>
        <section className="section"><h2 className="section__title">60秒缓解预评估</h2><p className="section__description">只决定是否进入完整评估；诊断和启动均由医生确认。</p>
          <div className="card">{measurementFields}<div className="form-grid">
            <SelectField label="成人T2DM" value={v.t2dm} onChange={set('t2dm')} options={['是', '否', '待确认']} />
            <SelectField label="急性不安全" value={v.acute} onChange={set('acute')} options={['否', '是']} />
            <SelectField label="分型疑点" value={v.typeDoubt} onChange={set('typeDoubt')} options={['否', '是']} />
            <SelectField label="治疗背景充分" value={v.contextEnough} onChange={set('contextEnough')} options={['是', '否']} />
            <SelectField label="患者拒绝" value={v.refused} onChange={set('refused')} options={['否', '是']} />
            <SelectField label="医生结论" value={v.conclusion} onChange={set('conclusion')} options={['进入完整评估', '暂缓进入', '当前不启动']} />
          </div>
          {v.conclusion === '暂缓进入' ? <><CheckboxGroup legend="暂缓原因" values={holds} onChange={setHolds} options={['急性安全', '分型存疑', '关键资料不足'].map((item) => ({ value: item, label: item }))} /><TextField label="前置任务" value={v.tasks} onChange={set('tasks')} /></> : null}
          {medicationFields}
          <button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submitPre()}>保存预评估结论</button></div>
        </section>
        <details className="section"><summary>前置问题处理结果</summary><div className="card card--muted">
          <SelectField label="复核结果" value={v.recovery} onChange={set('recovery')} options={['分型仍为T2DM', '分型明确其他类型', '急性已处理返回结论', '急性已处理进入血糖稳定']} />
          <TextField label="复核依据" value={v.evidence} onChange={set('evidence')} />
          {v.recovery === '急性已处理进入血糖稳定' ? <><TextField label="阶段目标" value={v.goal} onChange={set('goal')} />{examinationFields}<CheckboxGroup legend="会改变方案的管理约束" values={constraints} onChange={setConstraints} options={['无','CKD','ASCVD或心衰','严重视网膜病变','低血糖','衰弱','相关用药'].map(item => ({value:item,label:item}))} /><CheckboxGroup legend="干预组合" values={interventions} onChange={setInterventions} options={planOptions.map((item) => ({ value: item, label: item }))} />{interventions.includes('其他') ? <TextField label="其他干预说明" value={v.otherIntervention} onChange={set('otherIntervention')} /> : null}<DateField label="下次复评" value={v.nextDate} onChange={set('nextDate')} /></> : null}
          <button type="button" className="btn btn--outlined" disabled={submitting} onClick={() => void submitRecovery()}>保存处理结果</button>
        </div></details>
      </>
    )
}

/** FullAssessmentForm：独立事件表单，只接收本环节使用的显示与操作。 */
function FullAssessmentForm(props: FormProps) {
  const {v, set, measurementFields, submitting, interventions, setInterventions, submitFull, examinationFields, medicationFields, constraints, setConstraints} = props
  return (
      <section className="section"><h2 className="section__title">完整评估与主动管理计划</h2><div className="card">{measurementFields}
        <SelectField label="医生决定" value={v.start} onChange={set('start')} options={['启动', '暂缓补充关键资料', '当前不启动']} />
        {v.start === '启动' ? <><div className="form-grid"><TextField label="诊断依据" value={v.diagnosis} onChange={set('diagnosis')} /><SelectField label="干预意愿" value={v.willing} onChange={set('willing')} options={['是', '否']} /><SelectField label="接受复评" value={v.reviewAccept} onChange={set('reviewAccept')} options={['是', '否']} /><SelectField label="管理阶段" value={v.stage} onChange={set('stage')} options={['血糖稳定', '缓解诱导']} /><TextField label="主要目标" value={v.goal} onChange={set('goal')} /><DateField label="下次复评" value={v.nextDate} onChange={set('nextDate')} /></div>{examinationFields}<CheckboxGroup legend="会改变方案的管理约束" values={constraints} onChange={setConstraints} options={['无','CKD','ASCVD或心衰','严重视网膜病变','低血糖','衰弱','相关用药'].map(item => ({value:item,label:item}))} /><CheckboxGroup legend="干预组合" values={interventions} onChange={setInterventions} options={planOptions.map((item) => ({ value: item, label: item }))} />{interventions.includes('其他') ? <TextField label="其他干预说明" value={v.otherIntervention} onChange={set('otherIntervention')} /> : null}{medicationFields}</> : <TextField label="待办或原因" value={v.tasks} onChange={set('tasks')} />}
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submitFull()}>保存完整评估</button>
      </div></section>
    )
}

/** PhaseReviewForm：独立事件表单，只接收本环节使用的显示与操作。 */
function PhaseReviewForm(props: FormProps) {
  const {v, set, measurementFields, submitting, safety, setSafety, changes, setChanges, anchorFields, submitPhase, examinationFields, medicationFields} = props
  return (
      <section className="section"><h2 className="section__title">阶段复评与治疗调整</h2><div className="card">{measurementFields}
        {examinationFields}<CheckboxGroup legend="安全问题" values={safety} onChange={setSafety} options={safetyOptions.map((item) => ({ value: item, label: item }))} />
        <CheckboxGroup legend="治疗变化" values={changes} onChange={setChanges} options={changeOptions.map((item) => ({ value: item, label: item }))} />
        <div className="form-grid"><TextField label="阶段指标" value={v.stageIndicator} onChange={set('stageIndicator')} /><SelectField label="执行情况" value={v.executable} onChange={set('executable')} options={['可继续', '需调整', '无法继续']} /><SelectField label="复评动作" value={v.action} onChange={set('action')} options={['继续当前阶段', '调整方案或目标', '转换阶段', '结束主动管理']} /><SelectField label="停药决定" value={v.stopDecision} onChange={set('stopDecision')} options={['否', '是']} />
          {v.stopDecision === '是' ? <SelectField label="执行状态" value={v.stopExecution} onChange={set('stopExecution')} options={['', '仅计划停用', '已实际停用', '待核对']} /> : null}
          {v.stopDecision === '是' && v.stopExecution === '仅计划停用' ? <DateField label="计划停药日" value={v.plannedStopDate} onChange={set('plannedStopDate')} /> : null}
          {v.stopDecision === '是' && v.stopExecution === '已实际停用' ? <DateField label="实际停药日" value={v.actualStopDate} onChange={set('actualStopDate')} /> : null}
          <p className="clinical-summary">系统提示：仍有降糖作用药物：{v.hasDrug || '待核实'}。请在药物明细中核对。</p>{v.hasDrug === '是' ? <SelectField label="主要用途" value={v.purpose} onChange={set('purpose')} options={['', '高血糖治疗', '器官获益', '体重获益', '其他']} /> : null}<SelectField label="使用降糖药期间，血糖低于糖尿病诊断界值？" value={v.onTreatment} onChange={set('onTreatment')} options={['待确认', '是', '否']} /><SelectField label="医生确认明显失控" value={v.uncontrolled} onChange={set('uncontrolled')} options={['否', '是']} />
          {(v.action === '转换阶段' || v.uncontrolled === '是') ? <SelectField label="返回阶段" value={v.stage} onChange={set('stage')} options={['血糖稳定', '缓解诱导']} /> : null}<TextField label="阶段目标" value={v.goal} onChange={set('goal')} />{v.action === '调整方案或目标' ? <TextField label="调整内容" value={v.adjustment} onChange={set('adjustment')} /> : null}{v.action === '结束主动管理' ? <TextField label="结束原因" value={v.endReason} onChange={set('endReason')} /> : null}<DateField label="下次复评" value={v.nextDate} onChange={set('nextDate')} />
        </div>{v.stopDecision === '是' && v.stopExecution === '已实际停用' ? anchorFields : null}{medicationFields}
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submitPhase()}>保存本次复评</button>
      </div></section>
    )
}

/** ObservationForm：独立事件表单，只接收本环节使用的显示与操作。 */
function ObservationForm(props: FormProps) {
  const {patient, v, set, submitting, anchorFields, saveAnchors, restartMedication, medicationFields} = props
  return (
      <section className="section"><h2 className="section__title">缓解观察</h2><p className="section__description">系统按实际停药及全部适用干预日期计算；获益用药后停止本轮计时。</p>
        <div className="card"><p>实际停药日：{patient.last_med_stop_date?.replaceAll('-', '/') ?? '待核对'}　最早判定日：{patient.earliest_judge_date?.replaceAll('-', '/') ?? '待核对'}</p>{anchorFields}<button type="button" className="btn btn--outlined" disabled={submitting} onClick={() => void saveAnchors()}>保存日期核对</button></div>
        <div className="card"><h3 className="section__title">重新用药</h3><div className="form-grid"><SelectField label="重新用药原因" value={v.restartReason} onChange={set('restartReason')} options={['因高血糖', '因器官获益', '因体重获益']} /><SelectField label="后续阶段" value={v.stage} onChange={set('stage')} options={['血糖稳定', '缓解诱导']} /></div>{medicationFields}<button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void restartMedication()}>确认重新用药</button></div>
      </section>
    )
}

/** RemissionJudgeForm：独立事件表单，只接收本环节使用的显示与操作。 */
function RemissionJudgeForm(props: FormProps) {
  const {v, set, measurementFields, submitting, anchorFields, result, submitJudge, confirmRemission, examinationFields, medicationFields} = props
  return (
      <section className="section"><h2 className="section__title">缓解判定</h2><p className="section__description">先核对时间、检查日期、可靠指标和药物状态；客观符合后仍须医生确认。</p><div className="card">{measurementFields}<div className="form-grid"><SelectField label="既往诊断可信" value={v.diagnosisCredible} onChange={set('diagnosisCredible')} options={['是', '否', '待复核']} /><SelectField label="停药满3个月" value={v.drugFree} onChange={set('drugFree')} options={['是', '否', '待核对']} /><SelectField label="HbA1c可解释" value={v.hbaReliable} onChange={set('hbaReliable')} options={['是', '否', '待复核']} /><p className="clinical-summary">系统提示：仍有降糖作用药物：{v.hasDrug || '待核实'}。请在药物明细中核对。</p><p className="clinical-summary">资料完整性：{v.completeness}（根据所选检查、日期及核对状态计算）</p>{v.hbaReliable === '否' ? <SelectField label="替代指标独立复核" value={v.independent} onChange={set('independent')} options={['否', '是']} /> : null}<SelectField label="未达标/仍用药后阶段" value={v.stage} onChange={set('stage')} options={['血糖稳定', '缓解诱导']} /><TextField label="定向复核任务" value={v.tasks} onChange={set('tasks')} /></div>{examinationFields}{anchorFields}{medicationFields}<button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submitJudge()}>核对客观条件</button>
          {result?.objective_met ? <div className="page__actions"><button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void confirmRemission('确认')}>医生确认缓解</button><button type="button" className="btn btn--outlined" disabled={submitting} onClick={() => void confirmRemission('暂不确认')}>暂不确认，定向复核</button></div> : null}
        </div></section>
    )
}

/** PostRemissionForm：独立事件表单，只接收本环节使用的显示与操作。 */
function PostRemissionForm(props: FormProps) {
  const {v, set, measurementFields, submitting, risks, setRisks, submitPost, examinationFields, medicationFields} = props
  return (
      <section className="section"><h2 className="section__title">缓解后复评</h2><div className="card">{measurementFields}{examinationFields}<div className="form-grid"><TextField label="本次采用血糖摘要" value={v.glucose} onChange={set('glucose')} /><DateField label="检测日期" max={v.businessDate} value={v.glucoseDate} onChange={set('glucoseDate')} /><SelectField label="药物状态" value={v.medStatus} onChange={set('medStatus')} options={['未使用', '因高血糖', '因器官获益', '因体重获益', '待核对']} /><SelectField label="医生判定血糖状态" value={v.glucoseState} onChange={set('glucoseState')} options={['低于糖尿病诊断阈值', '达到糖尿病范围', '暂不能可靠解释']} /><SelectField label="医生确认风险上升" value={v.riskConfirmed} onChange={set('riskConfirmed')} options={['否', '是']} />{(v.medStatus === '因高血糖' || v.glucoseState === '达到糖尿病范围') ? <SelectField label="返回阶段" value={v.stage} onChange={set('stage')} options={['血糖稳定', '缓解诱导']} /> : null}<TextField label="定向复核任务" value={v.tasks} onChange={set('tasks')} /><DateField label="下次复评" value={v.nextDate} onChange={set('nextDate')} /></div><CheckboxGroup legend="风险线索" values={risks} onChange={setRisks} options={riskOptions.map((item) => ({ value: item, label: item }))} />{medicationFields}<button type="button" className="btn btn--primary" disabled={submitting} onClick={() => void submitPost()}>保存缓解后复评</button></div></section>
    )
}

/** 仅负责根据当前环节分发；表单与共享编辑器各自维护清晰职责。 */
export default function AssessmentForms(props: FormProps) {
  if (props.patient.current_state === 'ST00') return <RegularCareForm {...props} />
  if (props.patient.current_state === 'ST10') return <PreAssessmentForm {...props} />
  if (props.patient.current_state === 'ST20') return <FullAssessmentForm {...props} />
  if (props.patient.current_state === 'ST31' || props.patient.current_state === 'ST32') return <PhaseReviewForm {...props} />
  if (props.patient.current_state === 'ST40') return <ObservationForm {...props} />
  if (props.patient.current_state === 'ST50') return <RemissionJudgeForm {...props} />
  if (props.patient.current_state === 'ST60') return <PostRemissionForm {...props} />
  return <section className="section"><h2 className="section__title">本路径已关闭</h2><p>保留既往记录供追溯，后续按相应糖尿病类型管理。</p></section>
}
