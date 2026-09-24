interface SelectWithOtherProps {
  id?: string
  'aria-describedby'?: string
  options: readonly string[]
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

/** 单选字典附“其他”说明；存储时输出具体自由文本，不丢失信息。 */
export default function SelectWithOther({ options, value, onChange, placeholder = '未填写', ...props }: SelectWithOtherProps) {
  const known = options.includes(value)
  const selected = known ? value : value ? '其他' : ''
  return (
    <div className="stack stack--compact">
      <select {...props} className="select" value={selected} onChange={(event) => onChange(event.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((item) => <option key={item} value={item}>{item}</option>)}
        {!options.includes('其他') ? <option value="其他">其他</option> : null}
      </select>
      {selected === '其他' ? (
        <input
          className="input"
          aria-label="其他说明"
          placeholder="请填写其他说明"
          value={known ? '' : value === '其他' ? '' : value}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : null}
    </div>
  )
}
