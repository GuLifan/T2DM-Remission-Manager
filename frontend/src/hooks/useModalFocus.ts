import { useEffect, useRef } from 'react'

/** 共用模态键盘行为；回调变化不重新抢焦点，嵌套原生药物选择器优先处理。 */
export function useModalFocus(open: boolean, onClose: () => void) {
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const selector = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex="0"]'
    panel.current?.querySelector<HTMLElement>(selector)?.focus()
    const handle = (event: KeyboardEvent) => {
      if (document.querySelector('dialog[open]')) return
      if (event.key === 'Escape') {event.preventDefault(); close.current(); return}
      if (event.key !== 'Tab') return
      const items = Array.from(panel.current?.querySelectorAll<HTMLElement>(selector) ?? [])
      const first = items[0], last = items.at(-1)
      if (!first) {event.preventDefault(); panel.current?.focus(); return}
      if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus()}
      else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first.focus()}
    }
    window.addEventListener('keydown',handle)
    return () => {window.removeEventListener('keydown',handle); previous?.focus()}
  },[open])
  return panel
}
