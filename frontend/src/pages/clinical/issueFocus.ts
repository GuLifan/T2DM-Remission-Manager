/** 提示关闭后再定位，先恢复焦点管理，避免弹窗与页面争抢焦点。 */
export function locateIssue(root: HTMLElement | null, message: string) {
  window.setTimeout(() => {
    if (!root) return
    let target = root.querySelector<HTMLElement>('[data-invalid-date="true"] input, input:invalid, [aria-invalid="true"]')
    const area = /检查|检测|HbA1c|判定资料/.test(message) ? '.examination-section' : /药物|用药|方案.*核对/.test(message) ? '.medication-section' : null
    if (!target && area) target = root.querySelector<HTMLElement>(`${area} input:not([readonly]), ${area} button`)
    if (!target) {
      const group = [...root.querySelectorAll('fieldset')].find(g => {
        const title = g.querySelector('legend')?.textContent?.trim()
        return title && message.includes(title)
      })
      target = group?.querySelector<HTMLElement>('input, select, button') ?? null
    }
    if (!target) {
      const label = [...root.querySelectorAll('label')].find(l => {
        const title = l.textContent?.trim()
        return title && message.includes(title)
      })
      target = label?.querySelector<HTMLElement>('input, select, textarea') ?? (label?.htmlFor ? document.getElementById(label.htmlFor) : null)
    }
    if (target && !target.matches(':disabled')) {
      target.closest('details')?.setAttribute('open', '')
      target.scrollIntoView?.({block:'center', behavior:'smooth'})
      target.focus()
    }
  }, 0)
}
