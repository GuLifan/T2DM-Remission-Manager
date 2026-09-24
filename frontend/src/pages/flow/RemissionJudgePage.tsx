/**
 * 页面名称：RemissionJudgePage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元5｜缓解判定。
 *
 * 关键纪律（锁定稿§9）：**系统只核对客观条件，绝不自动确认缓解**。界面因此分三步：
 *   1. 核对客观条件（只读，可反复点击，不留痕）；
 *   2. 需要返回阶段复评时，医生选择返回阶段后「记录判定结论」（落库）；
 *   3. 客观条件满足时，由医生「确认 2 型糖尿病缓解」或「暂不确认」。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { flowApi } from '../../api/endpoints'
import { ErrorBanner, FieldRow, NumericInput, ResultBanner, SettingsRow } from '../../components'
import { STAGES, type Patient, type RemissionJudgeResult } from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 单元5：缓解判定。 */
export default function RemissionJudgePage({ patient, onUpdated }: FlowPageProps) {
  const [credible, setCredible] = useState('是')
  const [drugFree, setDrugFree] = useState('是')
  const [hba1cReliable, setHba1cReliable] = useState('是')
  const [hba1c, setHba1c] = useState('')
  const [fpg, setFpg] = useState('')
  const [ea1c, setEa1c] = useState('')
  const [independentReview, setIndependentReview] = useState('否')
  const [targetStage, setTargetStage] = useState('')
  const [reviewTasks, setReviewTasks] = useState('')

  const [result, setResult] = useState<RemissionJudgeResult | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  /** 把输入转成数字或 null（0 是合法值，不能被吞掉）。 */
  function toNumberOrNull(value: string): number | null {
    return value === '' ? null : Number(value)
  }

  /** 组装核对输入。 */
  function buildPayload(): Record<string, unknown> {
    return {
      f041_diagnosis_credible: credible,
      f042_drug_free_3m: drugFree,
      f043_hba1c_reliable: hba1cReliable,
      f014_hba1c: hba1cReliable === '是' ? toNumberOrNull(hba1c) : null,
      f044_fpg: hba1cReliable === '否' ? toNumberOrNull(fpg) : null,
      f045_ea1c: hba1cReliable === '否' ? toNumberOrNull(ea1c) : null,
      f046_independent_review: hba1cReliable === '否' ? independentReview : null,
      target_stage: targetStage || null,
    }
  }

  /** 步骤1：核对客观条件（只读，不落库）。 */
  async function handleCheck() {
    setError('')
    setSubmitting(true)
    try {
      setResult(await flowApi.judgeCheck(patient.id, buildPayload()))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '核对失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  /** 步骤2：记录判定结论（落库，可能改变患者状态）。 */
  async function handleRoute() {
    setError('')
    setSubmitting(true)
    try {
      const response = await flowApi.judgeRoute(patient.id, buildPayload())
      setResult(response)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '记录失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  /** 步骤3：医生确认或暂不确认。 */
  async function handleConfirm(action: '确认' | '暂不确认') {
    setError('')
    setSubmitting(true)
    try {
      await flowApi.judgeConfirm(patient.id, {
        f048_confirm: action,
        f012_pre_tasks: action === '暂不确认' ? reviewTasks : null,
      })
      setResult(null)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <section className="section">
        <h2 className="section__title">缓解判定</h2>
        <p className="section__description">
          系统先核对客观条件；最终是否形成「2 型糖尿病缓解」结论，必须由医生确认。
        </p>

        <div className="card">
          {error ? <ErrorBanner message={error} /> : null}

          <div className="form-grid">
            <FieldRow label="既往 T2DM 诊断是否可信" hint="不是短暂应激性或诊断依据不足的高血糖。">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={credible}
                  onChange={(event) => setCredible(event.target.value)}
                >
                  <option value="是">是</option>
                  <option value="待复核">待复核</option>
                  <option value="否">否</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="已停用全部降糖作用药物至少 3 个月" hint="停药日期是观察期计时锚点。">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={drugFree}
                  onChange={(event) => setDrugFree(event.target.value)}
                >
                  <option value="是">是</option>
                  <option value="待核对">待核对</option>
                  <option value="否">否</option>
                </select>
              )}
            </FieldRow>
            <FieldRow
              label="HbA1c 结果是否可可靠解释"
              hint="可靠时只使用 HbA1c；不可靠时才允许使用替代指标。"
            >
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={hba1cReliable}
                  onChange={(event) => setHba1cReliable(event.target.value)}
                >
                  <option value="是">是</option>
                  <option value="否">否</option>
                  <option value="待复核">待复核</option>
                </select>
              )}
            </FieldRow>

            {hba1cReliable === '是' ? (
              <FieldRow label="最近 HbA1c（%）" hint="缓解标准：低于 6.5%。">
                {(fieldProps) => (
                  <NumericInput
                    {...fieldProps}
                    unit="%"
                    min={0}
                    max={30}
                    step={0.1}
                    value={hba1c}
                    onChange={setHba1c}
                  />
                )}
              </FieldRow>
            ) : null}
          </div>

          {hba1cReliable === '否' ? (
            <div className="form-grid">
              <FieldRow label="空腹血糖 FPG（mmol/L）" hint="替代标准：低于 7.0。">
                {(fieldProps) => (
                  <NumericInput
                    {...fieldProps}
                    unit="mmol/L"
                    min={0}
                    max={50}
                    step={0.1}
                    value={fpg}
                    onChange={setFpg}
                  />
                )}
              </FieldRow>
              <FieldRow label="CGM 估算 HbA1c（%）" hint="替代标准：低于 6.5，由医生手工录入。">
                {(fieldProps) => (
                  <NumericInput
                    {...fieldProps}
                    unit="%"
                    min={0}
                    max={30}
                    step={0.1}
                    value={ea1c}
                    onChange={setEa1c}
                  />
                )}
              </FieldRow>
              <FieldRow label="替代指标是否完成独立复核" hint="未完成独立复核不得形成客观条件满足。">
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={independentReview}
                    onChange={(event) => setIndependentReview(event.target.value)}
                  >
                    <option value="否">否</option>
                    <option value="是">是</option>
                  </select>
                )}
              </FieldRow>
            </div>
          ) : null}

          <SettingsRow
            label="返回主动管理后的管理阶段"
            description="若本次需要返回阶段复评（仍用药或未达标），请先选择返回的管理阶段。"
            control={
              <select
                className="select"
                aria-label="返回主动管理后的管理阶段"
                value={targetStage}
                onChange={(event) => setTargetStage(event.target.value)}
              >
                <option value="">暂不返回阶段</option>
                {STAGES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            }
          />
        </div>

        {result ? (
          <ResultBanner
            text={result.output_text}
            tone={result.objective_met ? 'success' : result.blocked ? 'warning' : 'neutral'}
          />
        ) : null}

        {result?.doctor_confirmation_required ? (
          <div className="card card--muted">
            <h3 className="section__title">医生确认</h3>
            <p className="section__description">
              客观资料符合缓解标准，但系统不会自动形成结论——请由医生确认。
            </p>
            <FieldRow label="定向复核项目" hint="选择「暂不确认」时必填。">
              {(fieldProps) => (
                <textarea
                  {...fieldProps}
                  className="textarea"
                  value={reviewTasks}
                  onChange={(event) => setReviewTasks(event.target.value)}
                />
              )}
            </FieldRow>
          </div>
        ) : null}
      </section>

      <div className="action-bar">
        <span className="action-bar__note">核对可反复进行；确认缓解不可撤销</span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--outlined" disabled={submitting} onClick={handleCheck}>
          {submitting ? '正在核对…' : '核对客观条件'}
        </button>
        {result && (result.needs_target_stage || result.blocked) ? (
          <button type="button" className="btn btn--outlined" disabled={submitting} onClick={handleRoute}>
            记录判定结论
          </button>
        ) : null}
        {result?.doctor_confirmation_required ? (
          <>
            <button
              type="button"
              className="btn btn--outlined"
              disabled={submitting}
              onClick={() => handleConfirm('暂不确认')}
            >
              暂不确认缓解
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={submitting}
              onClick={() => handleConfirm('确认')}
            >
              确认2型糖尿病缓解
            </button>
          </>
        ) : null}
      </div>
    </>
  )
}
