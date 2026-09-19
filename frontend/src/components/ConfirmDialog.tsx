/**
 * 组件名称：ConfirmDialog.tsx
 * 所属层级：通用组件（components）
 * 功能说明：不可逆操作的二次确认对话框（UI.md 8.1 第 2 条）。
 *   确认按钮文案必须写明后果（如"结束主动管理"），禁止"确定"。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { useEffect } from 'react'

interface ConfirmDialogProps {
  /** 是否显示 */
  open: boolean
  /** 标题 */
  title: string
  /** 后果说明 */
  description: string
  /** 确认按钮文案（动词短语） */
  confirmLabel: string
  /** 取消按钮文案（动词短语） */
  cancelLabel?: string
  /** 是否用危险样式（不可逆操作） */
  danger?: boolean
  /** 确认回调 */
  onConfirm: () => void
  /** 取消回调 */
  onCancel: () => void
}

/** 二次确认对话框。 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = '返回上一页',
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  // Esc 关闭：键盘可达性要求（UI.md 8.2）
  useEffect(() => {
    if (!open) return undefined
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onCancel])

  if (!open) return null
  return (
    <div className="confirm-dialog__scrim" role="presentation">
      <div className="confirm-dialog" role="dialog" aria-modal="true" aria-label={title}>
        <span className="confirm-dialog__title">{title}</span>
        <p>{description}</p>
        <div className="confirm-dialog__actions">
          <button type="button" className="btn btn--text" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? 'btn btn--danger' : 'btn btn--primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
