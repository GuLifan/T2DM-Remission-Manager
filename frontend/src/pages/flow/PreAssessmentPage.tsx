/**
 * 页面名称：PreAssessmentPage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元1｜60秒缓解预评估。
 *
 * 临床要点：
 *   - 只判断"是否值得进入完整评估"，不判断能否缓解；
 *   - 机会信息（病程、BMI 线索、血糖、胰岛素、诉求）缺项不阻断；
 *   - 暂缓必须给出前置事项与返回位置；急性安全稳定化后可快速建档，
 *     分型复核为其他类型可关闭本路径。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { flowApi } from '../../api/endpoints'
import {
  CheckboxGroup,
  ErrorBanner,
  FieldRow,
  NumericInput,
  ResultBanner,
  SettingsRow,
} from '../../components'
import type { Tone } from '../../components'
import {
  HOLD_ACUTE,
  HOLD_TYPE,
  NO,
  OPT_DEMANDS,
  OPT_INSULIN,
  OPT_INTERVENTIONS,
  PENDING,
  YES,
  type Patient,
  type PreAssessmentResult,
} from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 结论 → 语义色调。 */
function toneOf(conclusion: string): Tone {
  if (conclusion === '进入完整评估') return 'success'
  if (conclusion === '暂缓进入') return 'warning'
  return 'neutral'
}

/** 单元1：60秒缓解预评估。 */
export default function PreAssessmentPage({ patient, onUpdated }: FlowPageProps) {
  // 核心五问（默认值取"无风险"一侧，仍需医生逐个确认）
  const [t2dm, setT2dm] = useState<string>(YES)
  const [acute, setAcute] = useState<string>(NO)
  const [typeDoubt, setTypeDoubt] = useState<string>(NO)
  const [contextEnough, setContextEnough] = useState<string>(YES)
  const [refused, setRefused] = useState<string>(NO)
  // 机会信息（不阻断）
  const [durationYears, setDurationYears] = useState('')
  const [durationMonths, setDurationMonths] = useState('0')
  const [weight, setWeight] = useState(patient.weight_kg?.toString() ?? '')
  const [height, setHeight] = useState(patient.height_cm?.toString() ?? '')
  const [glucoseHint, setGlucoseHint] = useState('')
  const [insulin, setInsulin] = useState('')
  const [demands, setDemands] = useState<string[]>([])
  // 暂缓前置事项
  const [preTasks, setPreTasks] = useState('')
  // 急性安全稳定化后的快速建档
  const [acuteGoal, setAcuteGoal] = useState('安全改善明显高血糖')
  const [acuteInterventions, setAcuteInterventions] = useState<string[]>(['结构化生活方式'])

  const [result, setResult] = useState<PreAssessmentResult | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const bmi = weight && height ? Number(weight) / ((Number(height) / 100) ** 2) : null

  /** 提交预评估。 */
  async function handleSubmit() {
    setError('')
    setSubmitting(true)
    try {
      const response = await flowApi.preAssessment(patient.id, {
        f001_t2dm_established: t2dm,
        f002_acute_unsafe: acute,
        f003_type_doubt: typeDoubt,
        f004_treatment_context_sufficient: contextEnough,
        f005_refused: refused,
        f006_duration:
          durationYears || durationMonths !== '0'
            ? `${durationYears || '0'} 年 ${durationMonths || '0'} 个月`
            : null,
        f006_duration_years: durationYears === '' ? null : Number(durationYears),
        f006_duration_months: Number(durationMonths || 0),
        f007_bmi_hint: bmi && Number.isFinite(bmi) ? `BMI ${bmi.toFixed(1)}` : null,
        f018_weight: weight === '' ? null : Number(weight),
        f019_height: height === '' ? null : Number(height),
        f008_glucose_status: glucoseHint || null,
        f009_insulin: insulin || null,
        f010_demands: demands,
        f012_pre_tasks: preTasks || null,
      })
      setResult(response)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '提交失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  /** 急性安全稳定化后快速建档：直接进入血糖稳定阶段。 */
  async function handleAcuteStabilized() {
    setError('')
    setSubmitting(true)
    try {
      await flowApi.acuteStabilized(patient.id, {
        stage_goal: acuteGoal,
        interventions: acuteInterventions,
      })
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  /** 分型复核明确为其他类型：关闭本路径。 */
  async function handleClosePath() {
    setError('')
    setSubmitting(true)
    try {
      await flowApi.closePath(patient.id)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  const acuteHold = result?.hold_reasons.includes(HOLD_ACUTE) ?? false
  const typeHold = result?.hold_reasons.includes(HOLD_TYPE) ?? false

  return (
    <>
      <section className="section">
        <h2 className="section__title">60秒缓解预评估</h2>
        <p className="section__description">
          只判断患者目前是否值得进入完整评估，不判断最终能否缓解。机会信息可不填，不阻断判断。
        </p>

        <div className="card">
          {error ? <ErrorBanner message={error} /> : null}

          <div className="form-grid">
            <FieldRow label="成人T2DM判断是否基本成立">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={t2dm}
                  onChange={(event) => setT2dm(event.target.value)}
                >
                  <option value={YES}>是</option>
                  <option value={NO}>否</option>
                  <option value={PENDING}>待确认</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="当前是否存在急性不安全状态">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={acute}
                  onChange={(event) => setAcute(event.target.value)}
                >
                  <option value={NO}>否</option>
                  <option value={YES}>是</option>
                </select>
              )}
            </FieldRow>
            <FieldRow
              label="是否存在明显分型疑点"
              hint="BMI 正常、使用胰岛素或 C 肽缺失本身不能自动判为分型疑点。"
            >
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={typeDoubt}
                  onChange={(event) => setTypeDoubt(event.target.value)}
                >
                  <option value={NO}>否</option>
                  <option value={YES}>是</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="当前治疗背景是否足以判断">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={contextEnough}
                  onChange={(event) => setContextEnough(event.target.value)}
                >
                  <option value={YES}>是</option>
                  <option value={NO}>否</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="患者是否明确拒绝进一步了解或参与">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={refused}
                  onChange={(event) => setRefused(event.target.value)}
                >
                  <option value={NO}>否</option>
                  <option value={YES}>是</option>
                </select>
              )}
            </FieldRow>
          </div>

          <h3 className="section__title">机会信息（不阻断判断）</h3>
          <div className="form-grid">
            <FieldRow label="大致病程">
              {(fieldProps) => (
                <div className="duration-input" {...fieldProps}>
                  <NumericInput value={durationYears} onChange={setDurationYears} unit="年" min={0} max={60} step={1} />
                  <NumericInput value={durationMonths} onChange={setDurationMonths} unit="月" min={0} max={11} step={1} />
                </div>
              )}
            </FieldRow>
            <FieldRow label="体重">
              {(fieldProps) => (
                <NumericInput {...fieldProps} value={weight} onChange={setWeight} unit="kg" min={0.1} max={500} step={0.1} />
              )}
            </FieldRow>
            <FieldRow label="身高">
              {(fieldProps) => (
                <NumericInput {...fieldProps} value={height} onChange={setHeight} unit="cm" min={50} max={250} step={0.1} />
              )}
            </FieldRow>
            <FieldRow label="BMI" hint="系统按本次身高与体重计算，仅作记录，不参与准入判断。">
              {(fieldProps) => <input {...fieldProps} className="input num" readOnly value={bmi && Number.isFinite(bmi) ? bmi.toFixed(1) : ''} />}
            </FieldRow>
            <FieldRow label="近期血糖状态">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input num"
                  value={glucoseHint}
                  placeholder="如：HbA1c 10.6%"
                  onChange={(event) => setGlucoseHint(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="当前胰岛素使用背景">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={insulin}
                  onChange={(event) => setInsulin(event.target.value)}
                >
                  <option value="">未填写</option>
                  {OPT_INSULIN.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              )}
            </FieldRow>
          </div>

          <SettingsRow
            label="患者诉求（可多选）"
            stacked
            control={
              <CheckboxGroup
                legend="患者本次的诉求"
                values={demands}
                onChange={setDemands}
                options={OPT_DEMANDS.map((item) => ({ value: item, label: item }))}
              />
            }
          />

          <FieldRow label="前置事项" hint="选择「暂缓进入」时必填，写明需要先完成的事情。">
            {(fieldProps) => (
              <textarea
                {...fieldProps}
                className="textarea"
                value={preTasks}
                onChange={(event) => setPreTasks(event.target.value)}
              />
            )}
          </FieldRow>
        </div>
      </section>

      {result ? (
        <section className="section">
          <ResultBanner text={result.output_text} tone={toneOf(result.conclusion)} />
          {result.return_hint ? <p className="page__subtitle">{result.return_hint}</p> : null}

          {acuteHold ? (
            <div className="card">
              <h3 className="section__title">急性安全问题已处理完毕</h3>
              <p className="section__description">
                医生确认已稳定化时，可直接进入血糖稳定阶段（快速建档，不重复预评估与完整评估）。
              </p>
              <FieldRow label="一个主要阶段目标">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input"
                    value={acuteGoal}
                    onChange={(event) => setAcuteGoal(event.target.value)}
                  />
                )}
              </FieldRow>
              <CheckboxGroup
                legend="干预组合（可组合）"
                values={acuteInterventions}
                onChange={setAcuteInterventions}
                options={OPT_INTERVENTIONS.map((item) => ({ value: item, label: item }))}
              />
              <div className="page__actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={submitting}
                  onClick={handleAcuteStabilized}
                >
                  {submitting ? '正在建档…' : '确认进入血糖稳定阶段'}
                </button>
              </div>
            </div>
          ) : null}

          {typeHold ? (
            <div className="card card--muted">
              <h3 className="section__title">分型复核结果</h3>
              <p className="section__description">
                复核明确仍为 T2DM：重新提交预评估即可进入完整评估。
                复核明确为其他类型糖尿病：关闭本路径（终态）。
              </p>
              <div className="page__actions">
                <button
                  type="button"
                  className="btn btn--outlined"
                  disabled={submitting}
                  onClick={handleClosePath}
                >
                  分型明确为其他类型，关闭本路径
                </button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="action-bar">
        <span className="action-bar__note">三项暂缓原因皆无时，进入完整评估</span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? '正在评估…' : '完成预评估并查看结论'}
        </button>
      </div>
    </>
  )
}
