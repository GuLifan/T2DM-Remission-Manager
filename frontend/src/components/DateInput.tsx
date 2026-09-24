import { useEffect, useState } from 'react'

function displayDate(value: string): string {
  return value ? value.replaceAll('-', '/') : ''
}

function isoDate(value: string): string | null {
  const match = value.trim().match(/^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/)
  if (!match) return null
  const [, yearText, monthText, dayText] = match
  const year = Number(yearText)
  const month = Number(monthText)
  const day = Number(dayText)
  const candidate = new Date(Date.UTC(year, month - 1, day))
  if (
    candidate.getUTCFullYear() !== year ||
    candidate.getUTCMonth() + 1 !== month ||
    candidate.getUTCDate() !== day
  ) return null
  return `${yearText}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

interface DateInputProps {
  id?: string
  'aria-describedby'?: string
  value: string
  onChange: (isoValue: string) => void
  disabled?: boolean
}

/** 明确使用 yyyy/mm/dd 文本格式，避免浏览器原生日期控件随系统语言变化。 */
export default function DateInput({ value, onChange, ...props }: DateInputProps) {
  const [draft, setDraft] = useState(displayDate(value))
  const [invalid, setInvalid] = useState(false)
  useEffect(() => setDraft(displayDate(value)), [value])

  function commit() {
    if (!draft.trim()) {
      setInvalid(false)
      onChange('')
      return
    }
    const parsed = isoDate(draft)
    setInvalid(parsed === null)
    if (parsed) onChange(parsed)
  }

  return (
    <div className="date-input">
      <input
        {...props}
        className={invalid ? 'input num input--invalid' : 'input num'}
        inputMode="numeric"
        placeholder="yyyy/mm/dd"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        aria-invalid={invalid}
      />
      {invalid ? <span className="field-row__error">请按 yyyy/mm/dd 填写有效日期。</span> : null}
    </div>
  )
}
