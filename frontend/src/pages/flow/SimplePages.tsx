/**
 * 文件名称：SimplePages.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：两个简单流程页面——常规糖尿病综合管理、关闭缓解路径。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { patientApi } from '../../api/endpoints'
import { ErrorBanner } from '../../components'
import type { Patient } from '../../types'

interface FlowPageProps {
  patient: Patient
  /** 决策完成后刷新患者（壳层据此切换页面） */
  onUpdated: () => void
}

/** 常规糖尿病综合管理（ST00）：可重新发起预评估。 */
export function RegularCarePage({ patient, onUpdated }: FlowPageProps) {
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  /** 重新发起 60 秒缓解预评估（不构成新增临床节点）。 */
  async function handleReopen() {
    setError('')
    setSubmitting(true)
    try {
      await patientApi.reopen(patient.id)
      onUpdated()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '操作失败，请重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="section">
      <h2 className="section__title">常规糖尿病综合管理</h2>
      <p className="section__description">
        该患者当前未处于主动缓解管理路径。临床条件或患者意愿改变时，可重新发起 60 秒缓解预评估。
      </p>
      <div className="card">
        {error ? <ErrorBanner message={error} /> : null}
        <div className="page__actions">
          <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleReopen}>
            {submitting ? '正在发起…' : '重新发起60秒缓解预评估'}
          </button>
        </div>
      </div>
    </section>
  )
}

/** 关闭 T2DM 缓解路径（ST99，终态）。 */
export function ClosedPathPage({ patient }: FlowPageProps) {
  return (
    <section className="section">
      <h2 className="section__title">已关闭 T2DM 缓解管理路径</h2>
      <p className="section__description">
        {patient.name} 的分型复核明确为其他类型糖尿病，不再按 2 型糖尿病缓解路径管理。
      </p>
      <div className="card">
        <p>该路径为终态，无后续缓解管理环节；后续按相应类型糖尿病的常规诊疗管理。</p>
      </div>
    </section>
  )
}
