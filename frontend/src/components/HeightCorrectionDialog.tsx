import { useEffect, useState } from 'react'

import { useModalFocus } from '../hooks/useModalFocus'
import { ApiError } from '../api/client'
import { patientApi } from '../api/endpoints'
import type { Patient } from '../types'
import ErrorBanner from './ErrorBanner'
import FieldRow from './FieldRow'
import NumericInput from './NumericInput'

interface HeightCorrectionDialogProps {
  patient: Patient
  onSaved: () => void
}

/** 管理员专用身高更正入口；后端仍会独立验证管理员角色并写审计。 */
export default function HeightCorrectionDialog({ patient, onSaved }: HeightCorrectionDialogProps) {
  const [open, setOpen] = useState(false)
  const [height, setHeight] = useState(patient.height_cm == null ? '' : String(patient.height_cm))
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const panel = useModalFocus(open, () => {if (!saving) setOpen(false)})

  useEffect(() => {
    if (open) setHeight(patient.height_cm == null ? '' : String(patient.height_cm))
  }, [open, patient.height_cm])

  async function save() {
    if (!height) {
      setError('请填写更正后的身高。')
      return
    }
    setError('')
    setSaving(true)
    try {
      await patientApi.updateHeight(patient.id, Number(height))
      setOpen(false)
      onSaved()
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : '更正身高失败，请重试。')
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <button type="button" className="btn btn--outlined" onClick={() => setOpen(true)}>
        更正身高
      </button>
      {open ? (
        <div className="confirm-dialog__scrim" role="presentation">
          <div ref={panel} className="confirm-dialog" role="dialog" aria-modal="true" aria-label="管理员更正身高">
            <span className="confirm-dialog__title">管理员更正身高</span>
            <p>当前值：{patient.height_cm == null ? '未填写' : `${patient.height_cm} cm`}。更正会重算当前 BMI，但不会修改历史事件。</p>
            {error ? <ErrorBanner message={error} /> : null}
            <FieldRow label="新身高" hint="本操作会记录修改前值、修改后值和操作者。">
              {(fieldProps) => (
                <NumericInput
                  {...fieldProps}
                  required
                  value={height}
                  onChange={setHeight}
                  unit="cm"
                  min={50}
                  max={250}
                  step={0.1}
                />
              )}
            </FieldRow>
            <div className="confirm-dialog__actions">
              <button type="button" className="btn btn--text" disabled={saving} onClick={() => setOpen(false)}>
                取消
              </button>
              <button type="button" className="btn btn--primary" disabled={saving} onClick={() => void save()}>
                {saving ? '正在保存…' : '保存身高更正'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  )
}
