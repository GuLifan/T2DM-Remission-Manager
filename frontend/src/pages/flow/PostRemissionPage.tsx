/**
 * 页面名称：PostRemissionPage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元6｜缓解后复评。
 *
 * 临床要点：因器官/体重获益用药导致「当前缓解状态不可评价」时，**不等同于复发**；
 * 缓解终止直接返回阶段复评，仅新分型证据或重大变化才返回完整评估。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { flowApi } from '../../api/endpoints'
import { CheckboxGroup, DateInput, ErrorBanner, FieldRow, ResultBanner, SettingsRow } from '../../components'
import {
  GLUCOSE_BELOW,
  GLUCOSE_DIABETIC,
  GLUCOSE_UNEXPLAINED,
  MED_FOR_HYPERGLYCEMIA,
  MED_FOR_ORGAN,
  MED_FOR_WEIGHT,
  MED_UNUSED,
  OPT_RISK_TRIGGERS,
  STAGES,
  type Patient,
  type PostRemissionResult,
} from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 单元6：缓解后复评。 */
export default function PostRemissionPage({ patient, onUpdated }: FlowPageProps) {
  const [glucose, setGlucose] = useState('')
  const [medStatus, setMedStatus] = useState<string>(MED_UNUSED)
  const [glucoseState, setGlucoseState] = useState<string>(GLUCOSE_BELOW)
  const [riskTriggers, setRiskTriggers] = useState<string[]>([])
  const [targetStage, setTargetStage] = useState<string>('血糖稳定')
  const [nextReviewDate, setNextReviewDate] = useState('')
  const [hasNewEvidence, setHasNewEvidence] = useState(false)

  const [result, setResult] = useState<PostRemissionResult | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // 需要医生选择返回阶段的三种情形：因获益用药、因高血糖、血糖回到糖尿病范围
  const needStage =
    medStatus === MED_FOR_ORGAN ||
    medStatus === MED_FOR_WEIGHT ||
    medStatus === MED_FOR_HYPERGLYCEMIA ||
    glucoseState === GLUCOSE_DIABETIC

  /** 提交缓解后复评。 */
  async function handleSubmit() {
    setError('')
    setSubmitting(true)
    try {
      const response = await flowApi.postRemission(patient.id, {
        f049_glucose: glucose || null,
        f050_med_status: medStatus,
        f051_risk_triggers: riskTriggers,
        f055_glucose_state: glucoseState,
        target_stage: needStage ? targetStage : null,
        next_review_date: nextReviewDate || null,
        has_new_type_evidence: hasNewEvidence,
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
        <h2 className="section__title">缓解后复评</h2>
        <p className="section__description">
          默认随访：第 1 年每 6 个月；第 2 年每 6 个月；满 2 年后每年。医生可根据异常结果或临床事件提前调整。
        </p>

        <div className="card">
          {error ? <ErrorBanner message={error} /> : null}

          <div className="form-grid">
            <FieldRow label="当前血糖指标及日期">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input num"
                  value={glucose}
                  placeholder="如：HbA1c 6.1%（复评当日）"
                  onChange={(event) => setGlucose(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="当前是否使用具有降糖作用的药物及原因">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={medStatus}
                  onChange={(event) => setMedStatus(event.target.value)}
                >
                  <option value={MED_UNUSED}>未使用</option>
                  <option value={MED_FOR_HYPERGLYCEMIA}>因高血糖</option>
                  <option value={MED_FOR_ORGAN}>因器官获益</option>
                  <option value={MED_FOR_WEIGHT}>因体重获益</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="当前血糖状态（医生确认）">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={glucoseState}
                  onChange={(event) => setGlucoseState(event.target.value)}
                >
                  <option value={GLUCOSE_BELOW}>低于糖尿病诊断阈值</option>
                  <option value={GLUCOSE_DIABETIC}>达到糖尿病范围</option>
                  <option value={GLUCOSE_UNEXPLAINED}>暂不能可靠解释</option>
                </select>
              )}
            </FieldRow>
            <FieldRow label="下次复评日期" hint="留空按随访节奏自动计算。">
              {(fieldProps) => (
                <DateInput
                  {...fieldProps}
                  value={nextReviewDate}
                  onChange={setNextReviewDate}
                />
              )}
            </FieldRow>
          </div>

          <SettingsRow
            label="辅助触发信息（可多选）"
            description="存在风险触发信息时提示加强维持干预，可由医生决定是否提前复评。"
            stacked
            control={
              <CheckboxGroup
                legend="风险触发信息"
                values={riskTriggers}
                onChange={setRiskTriggers}
                options={OPT_RISK_TRIGGERS.map((item) => ({ value: item, label: item }))}
              />
            }
          />

          {needStage ? (
            <div className="form-grid">
              <FieldRow label="返回主动管理后的管理阶段" hint="由医生选择，系统不代为决定。">
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={targetStage}
                    onChange={(event) => setTargetStage(event.target.value)}
                  >
                    {STAGES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                )}
              </FieldRow>
              <FieldRow
                label="是否出现新分型证据或重大临床变化"
                hint="仅此类情况才返回完整评估复核，否则返回阶段复评。"
              >
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={hasNewEvidence ? '是' : '否'}
                    onChange={(event) => setHasNewEvidence(event.target.value === '是')}
                  >
                    <option value="否">否</option>
                    <option value="是">是</option>
                  </select>
                )}
              </FieldRow>
            </div>
          ) : null}
        </div>

        {result ? <ResultBanner text={result.output_text} tone="success" /> : null}
      </section>

      <div className="action-bar">
        <span className="action-bar__note">缓解状态下仍需监测与常规并发症管理</span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? '正在记录…' : '记录复评结论'}
        </button>
      </div>
    </>
  )
}
