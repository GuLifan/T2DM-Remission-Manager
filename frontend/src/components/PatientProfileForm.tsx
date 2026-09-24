import { useState } from 'react'

import { ApiError } from '../api/client'
import { patientApi } from '../api/endpoints'
import type { Patient } from '../types'
import ErrorBanner from './ErrorBanner'
import FieldRow from './FieldRow'
import YearMonthInput from './YearMonthInput'

interface PatientProfileFormProps {
  patient: Patient
  departments: string[]
  onSaved: () => void
}

/** 导入患者首次使用前的资料核对表；保存成功后才解除临床流程门禁。 */
export default function PatientProfileForm({ patient, departments, onSaved }: PatientProfileFormProps) {
  const [name, setName] = useState(patient.name)
  const [gender, setGender] = useState<'男' | '女'>(patient.gender as '男' | '女')
  const [birthYear, setBirthYear] = useState(patient.birth_date.slice(0, 4))
  const [birthMonth, setBirthMonth] = useState(String(Number(patient.birth_date.slice(5, 7))))
  const [medicalRecordNo, setMedicalRecordNo] = useState(patient.medical_record_no)
  const [department, setDepartment] = useState(patient.department)
  const [contactPhone, setContactPhone] = useState(patient.contact_phone ?? '')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function save() {
    if (!name.trim() || !birthYear || !birthMonth || !medicalRecordNo.trim() || !department) {
      setError('请完整核对姓名、出生年月、住院号和当前科室。')
      return
    }
    setError('')
    setSaving(true)
    try {
      await patientApi.updateProfile(patient.id, {
        name: name.trim(),
        gender,
        birth_date: `${birthYear}-${birthMonth.padStart(2, '0')}-01`,
        medical_record_no: medicalRecordNo.trim(),
        department,
        contact_phone: contactPhone.trim() || null,
      })
      onSaved()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '保存患者资料失败，请重试。')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="section">
      <h2 className="section__title">完善患者基本资料</h2>
      <p className="section__description">该患者来自表格导入。请由医生核对资料，保存后才能发起 60 秒缓解预评估。</p>
      <div className="card">
        {error ? <ErrorBanner message={error} /> : null}
        <div className="form-grid">
          <FieldRow label="姓名">{(props) => <input {...props} className="input" value={name} onChange={(event) => setName(event.target.value)} />}</FieldRow>
          <FieldRow label="性别">{(props) => <select {...props} className="select" value={gender} onChange={(event) => setGender(event.target.value as '男' | '女')}><option value="女">女</option><option value="男">男</option></select>}</FieldRow>
          <FieldRow label="出生年月">{(props) => <YearMonthInput {...props} year={birthYear} month={birthMonth} onYearChange={setBirthYear} onMonthChange={setBirthMonth} />}</FieldRow>
          <FieldRow label="住院号">{(props) => <input {...props} className="input" value={medicalRecordNo} onChange={(event) => setMedicalRecordNo(event.target.value)} />}</FieldRow>
          <FieldRow label="当前科室">{(props) => <select {...props} className="select" value={department} onChange={(event) => setDepartment(event.target.value)}>{departments.map((item) => <option key={item} value={item}>{item}</option>)}</select>}</FieldRow>
          <FieldRow label="联系方式" hint="选填">{(props) => <input {...props} className="input" value={contactPhone} onChange={(event) => setContactPhone(event.target.value)} />}</FieldRow>
        </div>
        <div className="page__actions"><button type="button" className="btn btn--primary" disabled={saving} onClick={() => void save()}>{saving ? '正在保存…' : '确认资料并继续'}</button></div>
      </div>
    </section>
  )
}
