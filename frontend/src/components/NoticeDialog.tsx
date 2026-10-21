import { createPortal } from 'react-dom'
import { useModalFocus } from '../hooks/useModalFocus'

/** 单次操作提示独立于表单布局，避免被禁用fieldset或长页面遮挡。 */
export default function NoticeDialog({open, title, message, onClose, onLocate}: {
  open: boolean; title: string; message: string; onClose: () => void; onLocate?: () => void
}) {
  const panel = useModalFocus(open, onClose)
  if (!open) return null
  return createPortal(<div className="confirm-dialog__scrim notice-dialog__scrim">
    <div ref={panel} className="confirm-dialog" role="dialog" aria-modal="true" aria-label={title}>
      <h2 className="confirm-dialog__title">{title}</h2>
      <p className="notice-dialog__message">{message}</p>
      <div className="confirm-dialog__actions">
        <button type="button" className="btn btn--outlined" onClick={onClose}>返回修改</button>
        {onLocate ? <button type="button" className="btn btn--primary" onClick={onLocate}>定位需要核对的位置</button> : null}
      </div>
    </div>
  </div>, document.body)
}
