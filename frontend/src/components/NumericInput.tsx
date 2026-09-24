/** 带固定单位的数值输入；单位始终可见，避免医生误判口径。 */
interface NumericInputProps {
  id?: string
  'aria-describedby'?: string
  value: string
  onChange: (value: string) => void
  unit: string
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}

export default function NumericInput({ unit, onChange, ...props }: NumericInputProps) {
  return (
    <div className="input-with-unit">
      <input
        {...props}
        className="input input-with-unit__control num"
        type="number"
        inputMode="decimal"
        onChange={(event) => onChange(event.target.value)}
      />
      <span className="input-with-unit__suffix" aria-hidden="true">{unit}</span>
    </div>
  )
}
