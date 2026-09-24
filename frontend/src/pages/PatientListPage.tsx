/**
 * 页面名称：PatientListPage.tsx
 * 所属层级：页面组件（pages）
 * 功能说明：患者列表与建档。建档成功后进入患者工作台继续完成预评估。
 *
 * 交互要点：
 *   - 表单提交前就地校验（姓名、住院号、出生年月、当前科室必填）；
 *   - 住院号重复由后端给出自然语言提示，直接展示；
 *   - 列表为空时给出空态与明确动作。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { useMemo, useState } from 'react'

import { ApiError } from '../api/client'
import { domainApi, patientApi, referenceApi } from '../api/endpoints'
import {
  DateControl,
  EmptyState,
  ErrorBanner,
  FieldRow,
  ImportDialog,
  LoadingBlock,
  PageHeader,
  StatusBadge,
  YearMonthInput,
} from '../components'
import { useAsync } from '../hooks/useAsync'
import type { Patient, UserOut } from '../types'

interface PatientListPageProps {
  /** 当前登录医生 */
  currentUser: UserOut
  /** 打开某位患者的工作台 */
  onOpenPatient: (patientId: number) => void
  /** 退出登录 */
  onLogout: () => void
}

/** 患者列表 + 建档。 */
export default function PatientListPage({ currentUser, onOpenPatient, onLogout }: PatientListPageProps) {
  const patients = useAsync((signal) => patientApi.list(signal), [])
  const states = useAsync((signal) => domainApi.states(signal), [])
  const references = useAsync((signal) => referenceApi.get(signal), [])
  const [name, setName] = useState('')
  const [gender, setGender] = useState<'男' | '女'>('女')
  const [birthYear, setBirthYear] = useState('')
  const [birthMonth, setBirthMonth] = useState('')
  const [medicalRecordNo, setMedicalRecordNo] = useState('')
  const [department, setDepartment] = useState('内分泌科')
  const [contactPhone, setContactPhone] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)

  /**
   * 患者列表必须显示“当前状态”，不能用仅适用于主动管理期的 stage 字段代替。
   * 状态中文名继续来自后端领域表，避免在前端复制一份临床状态映射。
   */
  const stateNames = useMemo(
    () => new Map((states.data ?? []).map((state) => [state.code, state.name])),
    [states.data],
  )

  /** 建立患者档案并进入工作台。 */
  async function handleCreate() {
    setError('')
    if (!name.trim() || !medicalRecordNo.trim() || !birthYear || !birthMonth || !department) {
      setError('请填写姓名、出生年月、住院号和当前科室。')
      return
    }
    setCreating(true)
    try {
      const created: Patient = await patientApi.create({
        name: name.trim(),
        gender,
        birth_date: `${birthYear}-${birthMonth.padStart(2, '0')}-01`,
        medical_record_no: medicalRecordNo.trim(),
        department,
        contact_phone: contactPhone.trim() || null,
      })
      onOpenPatient(created.id)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '建立患者档案失败，请重试。')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="page">
      <PageHeader
        title="患者管理"
        context={`当前医生：${currentUser.display_name}`}
        actions={
          <>
            <DateControl />
            <button type="button" className="btn btn--text" onClick={onLogout}>
              退出登录
            </button>
          </>
        }
      />

      <div className="page__body">
        <section className="section">
          <div className="section-heading">
            <h2 className="section__title">建立患者档案</h2>
            <button type="button" className="btn btn--outlined" onClick={() => setImportOpen(true)}>
              从表格批量导入
            </button>
          </div>
          <p className="section__description">
            建档后患者进入常规糖尿病综合管理，可由医生发起 60 秒缓解预评估。
          </p>
          <div className="card">
            {error ? <ErrorBanner message={error} /> : null}
            <div className="form-grid">
              <FieldRow label="姓名">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                )}
              </FieldRow>
              <FieldRow label="住院号" hint="同一住院号不可重复建档。">
                {(fieldProps) => (
                  <input
                    {...fieldProps}
                    className="input"
                    value={medicalRecordNo}
                    onChange={(event) => setMedicalRecordNo(event.target.value)}
                  />
                )}
              </FieldRow>
              <FieldRow label="性别">
                {(fieldProps) => (
                  <select
                    {...fieldProps}
                    className="select"
                    value={gender}
                    onChange={(event) => setGender(event.target.value as '男' | '女')}
                  >
                    <option value="女">女</option>
                    <option value="男">男</option>
                  </select>
                )}
              </FieldRow>
              <FieldRow label="出生年月" hint="系统仅记录到月，日固定为 1。">
                {(fieldProps) => (
                  <YearMonthInput
                    {...fieldProps}
                    year={birthYear}
                    month={birthMonth}
                    onYearChange={setBirthYear}
                    onMonthChange={setBirthMonth}
                  />
                )}
              </FieldRow>
              <FieldRow label="当前科室">
                {(fieldProps) => (
                  <select {...fieldProps} className="select" value={department} onChange={(event) => setDepartment(event.target.value)}>
                    {(references.data?.departments ?? ['内分泌科']).map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                )}
              </FieldRow>
              <FieldRow label="联系方式" hint="选填；请填写院内允许记录的联系方式。">
                {(fieldProps) => (
                  <input {...fieldProps} className="input num" value={contactPhone} onChange={(event) => setContactPhone(event.target.value)} />
                )}
              </FieldRow>
            </div>
            <div className="page__actions">
              <button type="button" className="btn btn--primary" disabled={creating} onClick={handleCreate}>
                {creating ? '正在建档…' : '建立患者档案'}
              </button>
            </div>
          </div>
        </section>

        <section className="section">
          <h2 className="section__title">患者列表</h2>
          {patients.loading ? <LoadingBlock message="正在读取患者列表…" /> : null}
          {patients.error ? (
            <ErrorBanner
              message={patients.error}
              action={
                <button type="button" className="btn btn--text" onClick={patients.reload}>
                  重新读取
                </button>
              }
            />
          ) : null}
          {!patients.loading && !patients.error ? (
            patients.data && patients.data.length > 0 ? (
              <div className="card">
                <table className="table">
                  <thead>
                    <tr>
                      <th>姓名</th>
                      <th>性别</th>
                      <th>住院号</th>
                      <th>当前科室</th>
                      <th>当前环节</th>
                      <th aria-label="操作" />
                    </tr>
                  </thead>
                  <tbody>
                    {patients.data.map((patient) => (
                      <tr key={patient.id}>
                        <td>{patient.name}</td>
                        <td>{patient.gender}</td>
                        <td className="num">{patient.medical_record_no}</td>
                        <td>{patient.department}</td>
                        {/* 只显示后端领域表提供的自然语言状态名，不泄漏状态代码 */}
                        <td>
                          {stateNames.get(patient.current_state) ?? patient.stage ?? '当前管理环节'}
                          {!patient.profile_complete ? <StatusBadge tone="warning">待完善资料</StatusBadge> : null}
                          {patient.is_test_patient ? <StatusBadge tone="neutral">测试患者</StatusBadge> : null}
                        </td>
                        <td className="table__actions">
                          <button
                            type="button"
                            className="btn btn--text"
                            onClick={() => onOpenPatient(patient.id)}
                          >
                            进入患者管理
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="暂无患者档案。" />
            )
          ) : null}
        </section>
      </div>
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={patientApi.importFile}
        onCompleted={patients.reload}
      />
    </div>
  )
}
