/** 年月分栏输入；后端统一把日固定为 1。 */
interface YearMonthInputProps {
  id?: string
  'aria-describedby'?: string
  year: string
  month: string
  onYearChange: (value: string) => void
  onMonthChange: (value: string) => void
}

export default function YearMonthInput({
  id,
  year,
  month,
  onYearChange,
  onMonthChange,
  ...ariaProps
}: YearMonthInputProps) {
  const currentYear = new Date().getFullYear()
  return (
    <div className="year-month-input" {...ariaProps}>
      <input
        id={id}
        className="input num"
        type="number"
        inputMode="numeric"
        min="1900"
        max={currentYear}
        placeholder="年份"
        aria-label="出生年"
        value={year}
        onChange={(event) => onYearChange(event.target.value)}
      />
      <span>年</span>
      <select
        className="select num"
        aria-label="出生月"
        value={month}
        onChange={(event) => onMonthChange(event.target.value)}
      >
        <option value="">月份</option>
        {Array.from({ length: 12 }, (_, index) => String(index + 1)).map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
      <span>月</span>
    </div>
  )
}
