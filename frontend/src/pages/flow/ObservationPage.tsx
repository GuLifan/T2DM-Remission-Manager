/**
 * 页面名称：ObservationPage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元4｜缓解观察期（系统自动状态）。
 *
 * 临床要点：
 *   - 观察期由"停用最后一种降糖药"自动进入，**界面上没有"进入观察期"按钮**；
 *   - 系统只计算最早可判定日期；到日期后才开放"进入缓解判定"；
 *   - 观察期因高血糖或因器官/体重获益用药退出时，返回阶段由**医生选择**。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { flowApi } from '../../api/endpoints'
import { ErrorBanner, FieldRow, LoadingBlock, ResultBanner } from '../../components'
import { useAsync } from '../../hooks/useAsync'
import { MED_FOR_ORGAN, MED_FOR_WEIGHT, STAGES, type Patient } from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 单元4：缓解观察期。 */
export default function ObservationPage({ patient, onUpdated }: FlowPageProps) {
  const status = useAsync((signal) => flowApi.observation(patient.id, signal), [patient.id])
  const [restartReason, setRestartReason] = useState<string>('因高血糖')
  const [targetStage, setTargetStage] = useState<string>('血糖稳定')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  /** 到期后进入正式缓解判定。 */
  async function handleEnterJudge() {
    setError('')
    setSubmitting(true)
    try {
      await flowApi.enterJudge(patient.id)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  /** 观察期重新使用降糖作用药物 → 退出观察期。 */
  async function handleRestart() {
    setError('')
    setSubmitting(true)
    try {
      await flowApi.medicationRestart(patient.id, {
        f037_reason: restartReason,
        target_stage: targetStage,
      })
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  if (status.loading) return <LoadingBlock message="正在读取观察期状态…" />
  if (status.error) {
    return (
      <ErrorBanner
        message={status.error}
        action={
          <button type="button" className="btn btn--text" onClick={status.reload}>
            重新读取
          </button>
        }
      />
    )
  }

  return (
    <>
      <section className="section">
        <h2 className="section__title">缓解观察期</h2>
        <p className="section__description">
          停用最后一种具有降糖作用的药物后由系统自动进入本状态，无需医生点击任何「进入观察期」操作。
        </p>

        {error ? <ErrorBanner message={error} /> : null}
        {status.data ? (
          <>
            <ResultBanner text={status.data.output_text} tone={status.data.due ? 'success' : 'neutral'} />

            <div className="card card--muted">
              <h3 className="section__title">时间锚点</h3>
              <ul className="kv">
                <li className="kv__row">
                  <span className="kv__key">最后一种降糖作用药物停用日期</span>
                  <span className="kv__value num">{status.data.last_med_stop_date ?? '—'}</span>
                </li>
                <li className="kv__row">
                  <span className="kv__key">结构化生活方式干预开始日期</span>
                  <span className="kv__value num">{status.data.lifestyle_start_date ?? '如适用'}</span>
                </li>
                <li className="kv__row">
                  <span className="kv__key">代谢手术日期</span>
                  <span className="kv__value num">{status.data.surgery_date ?? '如适用'}</span>
                </li>
                <li className="kv__row">
                  <span className="kv__key">最早可判定日期（系统计算）</span>
                  <span className="kv__value num">{status.data.earliest_judge_date ?? '待确定'}</span>
                </li>
              </ul>
            </div>
          </>
        ) : null}
      </section>

      <div className="card">
        <h3 className="section__title">观察期重新使用具有降糖作用的药物</h3>
        <p className="section__description">
          因器官或体重获益用药退出时，保留既往观察记录，不等同于缓解失败或复发。
        </p>
        <div className="form-grid">
          <FieldRow label="重新用药的原因">
            {(fieldProps) => (
              <select
                {...fieldProps}
                className="select"
                value={restartReason}
                onChange={(event) => setRestartReason(event.target.value)}
              >
                <option value="因高血糖">因高血糖</option>
                <option value={MED_FOR_ORGAN}>因器官获益</option>
                <option value={MED_FOR_WEIGHT}>因体重获益</option>
                <option value="其他">其他</option>
              </select>
            )}
          </FieldRow>
          <FieldRow label="返回阶段复评后的管理阶段" hint="由医生选择，系统不代为决定。">
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
        </div>
      </div>

      <div className="action-bar">
        <span className="action-bar__note">
          {status.data?.due ? '已到最早可判定日期' : '未到最早可判定日期，暂不能判定'}
        </span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--outlined" disabled={submitting} onClick={handleRestart}>
          记录重新用药并返回阶段复评
        </button>
        <button
          type="button"
          className="btn btn--primary"
          disabled={submitting || !status.data?.due}
          onClick={handleEnterJudge}
        >
          {submitting ? '正在处理…' : '进入缓解判定'}
        </button>
      </div>
    </>
  )
}
