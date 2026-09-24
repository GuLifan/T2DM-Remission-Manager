/**
 * 页面名称：PhaseReviewPage.tsx
 * 所属层级：页面组件（pages/flow）
 * 功能说明：单元3｜阶段复评与治疗调整（同一页面反复使用）。
 *
 * V1.0 关键改进（相对 V0.1 的实测缺陷）：
 *   - 分支**用单选**呈现，选项顺序即优先级（来自后端 /api/domain/branches，前端不硬编码）；
 *   - 未选中的分支显示"本次不适用"及原因，绝不静默丢弃医生已填内容；
 *   - 互斥情形（既停药又仍用药）在界面上不可能同时发生。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useState } from 'react'

import { ApiError } from '../../api/client'
import { domainApi, flowApi } from '../../api/endpoints'
import {
  CheckboxGroup,
  ChoiceGroup,
  DateInput,
  ErrorBanner,
  FieldRow,
  ResultBanner,
  SettingsRow,
} from '../../components'
import { useAsync } from '../../hooks/useAsync'
import {
  ACT_ADJUST,
  ACT_CONTINUE,
  ACT_END,
  ACT_SWITCH,
  OPT_DRUG_PURPOSE_FALLBACK,
  OPT_SAFETY_ISSUES,
  OPT_TREATMENT_CHANGES,
  STAGES,
  type Patient,
  type PhaseReviewResult,
} from '../../types'

interface FlowPageProps {
  patient: Patient
  onUpdated: () => void
}

/** 单元3：阶段复评。 */
export default function PhaseReviewPage({ patient, onUpdated }: FlowPageProps) {
  // 分支定义来自后端（单一数据源），前端只渲染
  const branches = useAsync((signal) => domainApi.branches(signal), [])

  const [branchKey, setBranchKey] = useState<string>('routine_action')
  const [safetyIssues, setSafetyIssues] = useState<string[]>(['无'])
  const [treatmentChanges, setTreatmentChanges] = useState<string[]>(['无'])
  const [stageIndicator, setStageIndicator] = useState('')
  const [executable, setExecutable] = useState('')
  const [nextReviewDate, setNextReviewDate] = useState('')

  // 常规动作相关
  const [action, setAction] = useState<string>(ACT_CONTINUE)
  const [adjustmentSummary, setAdjustmentSummary] = useState('')
  const [newStage, setNewStage] = useState('')
  const [stageGoal, setStageGoal] = useState('')
  const [endReason, setEndReason] = useState('')

  // 各分支的专属输入
  const [stopDate, setStopDate] = useState('')
  const [drugPurpose, setDrugPurpose] = useState('')
  const [glucoseNonDiabetic, setGlucoseNonDiabetic] = useState(false)
  const [emergencyNote, setEmergencyNote] = useState('')
  const [uncontrolledSummary, setUncontrolledSummary] = useState('')

  const [result, setResult] = useState<PhaseReviewResult | null>(null)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const branchOptions = (branches.data ?? []).map((item) => ({
    value: item.key,
    label: item.label,
    hint: item.hint,
  }))

  // 未选中的分支：以"本次不适用"的形式列出并说明原因（不静默丢弃）
  const notApplied = (branches.data ?? []).filter((item) => item.key !== branchKey)
  const chosen = (branches.data ?? []).find((item) => item.key === branchKey)

  /** 按所选分支组装请求体（前端保证互斥，后端仍会二次裁决）。 */
  function buildPayload(): Record<string, unknown> {
    const base = {
      f030_safety_issues: safetyIssues,
      f031_stage_indicator: stageIndicator || null,
      f032_treatment_changes: treatmentChanges,
      f033_executable: executable || null,
      next_review_date: nextReviewDate || null,
      f034_action: action,
      f035_stop_last_med: false,
      f053_has_drug: false,
      f054_purpose: null,
      glucose_non_diabetic: false,
      f056_uncontrolled: false,
    }
    if (branchKey === 'uncontrolled') {
      return { ...base, f056_uncontrolled: true, adjustment_summary: uncontrolledSummary || null, emergency_note: emergencyNote || null }
    }
    if (branchKey === 'on_treatment_non_diabetic') {
      return {
        ...base,
        // 该分支的前置事实：仍在用药、且本次血糖已达非糖尿病范围
        f053_has_drug: true,
        f054_purpose: drugPurpose || null,
        glucose_non_diabetic: glucoseNonDiabetic,
      }
    }
    if (branchKey === 'stop_last_med') {
      return { ...base, f035_stop_last_med: true, f036_stop_date: stopDate || null }
    }
    // 常规复评动作
    return {
      ...base,
      f053_has_drug: false,
      adjustment_summary: action === ACT_ADJUST ? adjustmentSummary || null : null,
      new_stage: action === ACT_SWITCH ? newStage || null : null,
      stage_goal: action === ACT_SWITCH ? stageGoal || null : null,
      end_reason: action === ACT_END ? endReason || null : null,
    }
  }

  /** 提交阶段复评。 */
  async function handleSubmit() {
    setError('')
    setSubmitting(true)
    try {
      const response = await flowApi.phaseReview(patient.id, buildPayload())
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
        <h2 className="section__title">阶段复评与治疗调整</h2>
        <p className="section__description">
          当前阶段：{patient.stage ?? '—'}。日常滴定、上传血糖和一般随访不生成正式复评节点。
        </p>

        <div className="card">
          {error ? <ErrorBanner message={error} /> : null}

          <div className="form-grid">
            <FieldRow label="一个主要阶段指标">
              {(fieldProps) => (
                <input
                  {...fieldProps}
                  className="input"
                  value={stageIndicator}
                  placeholder="如：体重下降 4%，HbA1c 稳定"
                  onChange={(event) => setStageIndicator(event.target.value)}
                />
              )}
            </FieldRow>
            <FieldRow label="实际可执行性">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={executable}
                  onChange={(event) => setExecutable(event.target.value)}
                >
                  <option value="">未填写</option>
                  <option value="可继续">可继续</option>
                  <option value="需调整">需调整</option>
                  <option value="无法继续">无法继续</option>
                </select>
              )}
            </FieldRow>
          </div>

          <SettingsRow
            label="新发生的安全问题（可多选）"
            stacked
            control={
              <CheckboxGroup
                legend="安全问题"
                values={safetyIssues}
                onChange={setSafetyIssues}
                options={OPT_SAFETY_ISSUES.map((item) => ({ value: item, label: item }))}
              />
            }
          />
          <SettingsRow
            label="核心治疗变化（可多选）"
            stacked
            control={
              <CheckboxGroup
                legend="治疗变化"
                values={treatmentChanges}
                onChange={setTreatmentChanges}
                options={OPT_TREATMENT_CHANGES.map((item) => ({ value: item, label: item }))}
              />
            }
          />
        </div>

        <div className="card">
          <h3 className="section__title">本次复评分支（单选，自上而下为优先级）</h3>
          {branches.error ? (
            <ErrorBanner
              message={branches.error}
              action={
                <button type="button" className="btn btn--text" onClick={branches.reload}>
                  重新读取分支定义
                </button>
              }
            />
          ) : null}
          <ChoiceGroup
            legend="选择本次实际发生的分支"
            value={branchKey}
            onChange={setBranchKey}
            options={branchOptions}
          />

          {/* 未选中的分支：显式说明本次为何不适用（禁止静默丢弃） */}
          {notApplied.length > 0 ? (
            <div className="branch-notes">
              <span className="branch-notes__title">本次未生效的分支</span>
              {notApplied.map((item) => (
                <span className="branch-notes__item" key={item.key}>
                  {item.label}：本次选择的是「{chosen?.label ?? '—'}」，该项不参与本次记录。
                </span>
              ))}
            </div>
          ) : null}

          {branchKey === 'uncontrolled' ? (
            <>
              <FieldRow label="明显血糖失控的处理说明" hint="由医生确认，系统不设自动阈值。">
                {(fieldProps) => (
                  <textarea
                    {...fieldProps}
                    className="textarea"
                    value={uncontrolledSummary}
                    onChange={(event) => setUncontrolledSummary(event.target.value)}
                  />
                )}
              </FieldRow>
              <FieldRow label="急症处理情况（如适用）">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input"
                    value={emergencyNote}
                    onChange={(event) => setEmergencyNote(event.target.value)}
                  />
                )}
              </FieldRow>
            </>
          ) : null}

          {branchKey === 'on_treatment_non_diabetic' ? (
            <>
              <FieldRow
                label="当前降糖作用药物的主要使用目的"
                hint="用于心肾或体重获益时不建议为获得缓解标签而停药。"
              >
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={drugPurpose}
                    onChange={(event) => setDrugPurpose(event.target.value)}
                  >
                    <option value="">请选择</option>
                    {OPT_DRUG_PURPOSE_FALLBACK.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                )}
              </FieldRow>
              <SettingsRow
                label="本次血糖已达非糖尿病范围（医生判断）"
                control={
                  <label className="checkbox-line">
                    <input
                      type="checkbox"
                      checked={glucoseNonDiabetic}
                      onChange={(event) => setGlucoseNonDiabetic(event.target.checked)}
                    />
                    <span>确认已达非糖尿病范围</span>
                  </label>
                }
              />
            </>
          ) : null}

          {branchKey === 'stop_last_med' ? (
            <FieldRow label="停用最后一种具有降糖作用药物的日期" hint="记录后系统自动进入缓解观察期，无需其他操作。">
              {(fieldProps) => (
                <DateInput
                  {...fieldProps}
                  value={stopDate}
                  onChange={setStopDate}
                />
              )}
            </FieldRow>
          ) : null}

          {branchKey === 'routine_action' ? (
            <>
              <FieldRow label="本次复评动作">
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={action}
                    onChange={(event) => setAction(event.target.value)}
                  >
                    <option value={ACT_CONTINUE}>继续当前阶段</option>
                    <option value={ACT_ADJUST}>调整方案或目标</option>
                    <option value={ACT_SWITCH}>转换阶段</option>
                    <option value={ACT_END}>结束主动管理</option>
                  </select>
                )}
              </FieldRow>
              {action === ACT_ADJUST ? (
                <FieldRow label="调整内容">
                  {(fieldProps) => (
                    <textarea
                      {...fieldProps}
                      className="textarea"
                      value={adjustmentSummary}
                      onChange={(event) => setAdjustmentSummary(event.target.value)}
                    />
                  )}
                </FieldRow>
              ) : null}
              {action === ACT_SWITCH ? (
                <div className="form-grid">
                  <FieldRow label="新的管理阶段">
                    {(fieldProps) => (
                      <select
                        {...fieldProps}
                        className="select"
                        value={newStage}
                        onChange={(event) => setNewStage(event.target.value)}
                      >
                        <option value="">请选择</option>
                        {STAGES.filter((item) => item !== patient.stage).map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    )}
                  </FieldRow>
                  <FieldRow label="新的主要阶段目标">
                    {(fieldProps) => (
                      <input
                        {...fieldProps}
                        className="input"
                        value={stageGoal}
                        onChange={(event) => setStageGoal(event.target.value)}
                      />
                    )}
                  </FieldRow>
                </div>
              ) : null}
              {action === ACT_END ? (
                <FieldRow label="结束主动管理的原因">
                  {(fieldProps) => (
                    <textarea
                      {...fieldProps}
                      className="textarea"
                      value={endReason}
                      onChange={(event) => setEndReason(event.target.value)}
                    />
                  )}
                </FieldRow>
              ) : null}
            </>
          ) : null}

          <FieldRow label="下次正式复评日期" hint="留空按默认 12 周计算。">
            {(fieldProps) => (
              <DateInput
                {...fieldProps}
                value={nextReviewDate}
                onChange={setNextReviewDate}
              />
            )}
          </FieldRow>
        </div>

        {result ? (
          <>
            <ResultBanner
              text={result.output_text}
              tone={result.entered_observation ? 'neutral' : 'success'}
            />
            {result.ignored_branches.length > 0 ? (
              <div className="branch-notes">
                <span className="branch-notes__title">系统按优先级处理，以下分支本次未生效</span>
                {result.ignored_branches.map((note) => (
                  <span className="branch-notes__item" key={note}>
                    {note}
                  </span>
                ))}
              </div>
            ) : null}
          </>
        ) : null}
      </section>

      <div className="action-bar">
        <span className="action-bar__note">同一分支只能选一项；被覆盖的分支会在此说明</span>
        <div className="action-bar__spacer" />
        <button type="button" className="btn btn--primary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? '正在记录…' : '记录复评结论'}
        </button>
      </div>
    </>
  )
}
