/**
 * 组件名称：OwnershipTransferDialog.tsx
 * 功能说明：管理员选择新的责任医生，并在真正提交前再次核对变更双方。
 */

import { useState } from 'react'

import type { AssignableDoctor, Patient } from '../types'
import ConfirmDialog from './ConfirmDialog'
import ErrorBanner from './ErrorBanner'
import FieldRow from './FieldRow'

interface OwnershipTransferDialogProps {
  patient: Patient
  doctors: AssignableDoctor[]
  transferring: boolean
  error: string
  onTransfer: (ownerId: number) => Promise<void>
}

export default function OwnershipTransferDialog({
  patient,
  doctors,
  transferring,
  error,
  onTransfer,
}: OwnershipTransferDialogProps) {
  const [open, setOpen] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [ownerId, setOwnerId] = useState('')
  const selected = doctors.find((doctor) => doctor.id === Number(ownerId))

  function close() {
    setOpen(false)
    setConfirmOpen(false)
    setOwnerId('')
  }

  async function confirmTransfer() {
    if (!selected || transferring) return
    try {
      await onTransfer(selected.id)
      close()
    } catch {
      // 具体错误由父页面统一转换为医生可读提示并传回本对话框。
    }
  }

  return (
    <>
      <button type="button" className="btn btn--outlined" onClick={() => setOpen(true)}>
        转移责任医生
      </button>
      {open && !confirmOpen ? (
        <div className="confirm-dialog__scrim" role="presentation">
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-label="转移责任医生">
            <span className="confirm-dialog__title">转移责任医生</span>
            <p>
              当前责任医生：{patient.owner_display_name ?? '未指定'}。转移后，原责任医生将立即变为只读。
            </p>
            {error ? <ErrorBanner message={error} /> : null}
            <FieldRow label="新的责任医生">
              {(fieldProps) => (
                <select
                  {...fieldProps}
                  className="select"
                  value={ownerId}
                  onChange={(event) => setOwnerId(event.target.value)}
                >
                  <option value="">请选择启用中的普通医生</option>
                  {doctors.map((doctor) => (
                    <option key={doctor.id} value={doctor.id}>
                      {doctor.display_name}{doctor.department ? ` · ${doctor.department}` : ''}
                    </option>
                  ))}
                </select>
              )}
            </FieldRow>
            <div className="confirm-dialog__actions">
              <button type="button" className="btn btn--text" onClick={close}>
                取消转移
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={!selected || selected.id === patient.owner_id}
                onClick={() => setConfirmOpen(true)}
              >
                下一步：核对变更
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <ConfirmDialog
        open={confirmOpen}
        title="确认转移责任归属"
        description={`患者“${patient.name}”将从“${patient.owner_display_name ?? '未指定'}”转给“${selected?.display_name ?? '未选择'}”。提交后双方权限立即改变。`}
        confirmLabel={transferring ? '正在转移…' : '确认转移责任医生'}
        cancelLabel="返回重新选择"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void confirmTransfer()}
      />
    </>
  )
}
