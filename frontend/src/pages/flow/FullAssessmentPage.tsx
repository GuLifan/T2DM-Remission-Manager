/**
 * 页面名称：FullAssessmentPage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元2｜完整评估并形成主动管理计划。
 *
 * 临床要点（锁定稿§6）：是否启动、当前阶段、一个主要目标和干预组合必须在
 * **同一次决策**中完成，不得拆成连续重复页面。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { flowApi } from '../../api/endpoints'
import { CheckboxGroup, ErrorBanner, FieldRow, ResultBanner, SettingsRow } from '../../components'
import {
  HOLD_SUPPLEMENT,
  NOT_START,
  OPT_CONSTRAINTS,
  OPT_INTERVENTIONS,
  STAGES,
  STAGE_INDUCTION,
  START,
  type FullAssessmentResult,
  type Patient,
} from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 单元2：完整评估与计划。 */
export default function FullAssessmentPage({ patient, onUpdated }: FlowPageProps) {
  const [diagnosisBasis, setDiagnosisBasis] = useState('')
  const [hba1c, setHba1c] = useState('')
  const [drugs, setDrugs] = useState('')
  const [majorAdjustment, setMajorAdjustment] = useState('')
  const [weight, setWeight] = useState('')
  const [height, setHeight] = useState('')
  const [cpeptide, setCpeptide] = useState('')
  const [constraints, setConstraints] = useState<string[]>([])
  const [willing, setWilling] = useState('')
  const [reviewAccept, setReviewAccept] = useState('')

  const [startPlan, setStartPlan] = useState<string>(START)
  const [stage, setStage] = useState<string>(STAGE_INDUCTION)
  const [stageGoal, setStageGoal] = useState('实现有临床意义的体重下降')
  const [interventions, setInterventions] = useState<string[]>(['结构化生活方式'])
  const [nextReviewDate, setNextReviewDate] = useState('')
  const [preTasks, setPreTasks] = useState('')
  const [notStartReason, setNotStartReason] = useState('')

  const [result, setResult] = useState<FullAssessmentResult | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  /** 把可空输入转成数字或 null（注意 0 是合法值，不能被吞掉）。 */
  function toNumberOrNull(value: string): number | null {
    return value === '' ? null : Number(value)
  }

  /** 提交完整评估与计划。 */
  async function handleSubmit() {
    setError('')
    setSubmitting(true)
    try {
      const response = await flowApi.fullAssessment(patient.id, {
        f013_diagnosis_basis: diagnosisBasis || null,
        f014_hba1c: toNumberOrNull(hba1c),
        f016_drugs: drugs || null,
        f017_major_adjustment: majorAdjustment || null,
        f018_weight: toNumberOrNull(weight),
        f019_height: toNumberOrNull(height),
        f022_cpeptide: cpeptide || null,
        f023_constraints: constraints,
        f024_willing: willing || null,
        f025_review_accept: reviewAccept || null,
        f026_start: startPlan,
        f027_stage: startPlan === START ? stage : null,
        f028_stage_goal: startPlan === START ? stageGoal : null,
        f029_interventions: startPlan === START ? interventions : [],
        next_review_date: nextReviewDate || null,
        f012_pre_tasks: startPlan === HOLD_SUPPLEMENT ? preTasks : null,
        not_start_reason: startPlan === NOT_START ? notStartReason : null,
      })
      setResult(response)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '提交失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <section className="section">
        <h2 className="section__title">完整评估并形成主动管理计划</h2>
        <p className="section__description">
          是否启动、当前阶段、一个主要目标和干预组合在同一次决策中完成，避免重复填表。
        </p>

        <div className="card">
          {error ? <ErrorBanner message={error} /> : null}

          <h3 className="section__title">评估资料（供记录与追溯）</h3>
          <div className="form-grid">
            <FieldRow label="既往 T2DM 诊断基础">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input"
                  value={diagnosisBasis}
                  onChange={(event) => setDiagnosisBasis(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="最近 HbA1c（%）">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input num"
                  type="number"
                  step="0.1"
                  value={hba1c}
                  onChange={(event) => setHba1c(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="当前具有降糖作用的药物">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input"
                  value={drugs}
                  onChange={(event) => setDrugs(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="是否处于重大治疗调整期">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={majorAdjustment}
                  onChange={(event) => setMajorAdjustment(event.target.value)}
                >
                  <option value="">未填写</option>
                  <option value="是">是</option>
                  <option value="否">否</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="体重（kg）">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input num"
                  type="number"
                  step="0.1"
                  value={weight}
                  onChange={(event) => setWeight(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="身高（cm）">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input num"
                  type="number"
                  step="0.1"
                  value={height}
                  onChange={(event) => setHeight(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="C 肽 / 胰岛功能（条件性）">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input"
                  value={cpeptide}
                  onChange={(event) => setCpeptide(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="是否愿意参与至少一种可行干预">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={willing}
                  onChange={(event) => setWilling(event.target.value)}
                >
                  <option value="">未填写</option>
                  <option value="是">是</option>
                  <option value="否">否</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="是否接受阶段复评">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={reviewAccept}
                  onChange={(event) => setReviewAccept(event.target.value)}
                >
                  <option value="">未填写</option>
                  <option value="是">是</option>
                  <option value="否">否</option>
                </select>
              )}
            </FieldRow>
          </div>

          <SettingsRow
            label="会改变方案的管理约束（可多选）"
            stacked
            control={
              <CheckboxGroup
                legend="管理约束"
                values={constraints}
                onChange={setConstraints}
                options={OPT_CONSTRAINTS.map((item) => ({ value: item, label: item }))}
              />
            }
          />
        </div>

        <div className="card">
          <h3 className="section__title">一次性计划决策</h3>
          <FieldRow label="是否启动主动管理">
            {(fieldProps) => (
              <select
                {...fieldProps}
                className="select"
                value={startPlan}
                onChange={(event) => setStartPlan(event.target.value)}
              >
                <option value={START}>启动</option>
                <option value={HOLD_SUPPLEMENT}>暂缓补充关键资料</option>
                <option value={NOT_START}>当前不启动</option>
              </select>
            )}
          </FieldRow>

          {startPlan === START ? (
            <div className="form-grid">
              <FieldRow label="当前管理阶段">
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={stage}
                    onChange={(event) => setStage(event.target.value)}
                  >
                    {STAGES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                )}
              </FieldRow>
              <FieldRow label="一个主要阶段目标">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input"
                    value={stageGoal}
                    onChange={(event) => setStageGoal(event.target.value)}
                  />
                )}
              </FieldRow>
              <FieldRow label="首次正式复评日期" hint="留空按默认 12 周计算，可自行指定。">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input num"
                    type="date"
                    value={nextReviewDate}
                    onChange={(event) => setNextReviewDate(event.target.value)}
                  />
                )}
              </FieldRow>
            </div>
          ) : null}

          {startPlan === START ? (
            <CheckboxGroup
              legend="干预组合（可组合）"
              values={interventions}
              onChange={setInterventions}
              options={OPT_INTERVENTIONS.map((item) => ({ value: item, label: item }))}
            />
          ) : null}

          {startPlan === HOLD_SUPPLEMENT ? (
            <FieldRow label="需要补充的关键资料" hint="只保留真正影响启动、阶段、目标或干预的缺失资料。">
              {(fieldProps) => (
                <textarea
                  {...fieldProps}
                  className="textarea"
                  value={preTasks}
                  onChange={(event) => setPreTasks(event.target.value)}
                />
              )}
            </FieldRow>
          ) : null}

          {startPlan === NOT_START ? (
            <FieldRow label="不启动的原因">
              {(fieldProps) => (
                <textarea
                  {...fieldProps}
                  className="textarea"
                  value={notStartReason}
                  onChange={(event) => setNotStartReason(event.target.value)}
                />
              )}
            </FieldRow>
          ) : null}
        </div>

        {result ? <ResultBanner text={result.output_text} tone="success" /> : null}
      </section>

      <div className="action-bar">
        <span className="action-bar__note">评估资料与计划决策一次提交</span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? '正在提交…' : '记录完整评估结论'}
        </button>
      </div>
    </>
  )
}
