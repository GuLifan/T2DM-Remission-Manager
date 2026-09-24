import CheckboxGroup from './CheckboxGroup'

interface MultiSelectWithOtherProps {
  legend: string
  options: readonly string[]
  values: string[]
  onChange: (values: string[]) => void
}

/** 多选字典附“其他”自由文本，最终仍以字符串数组提交。 */
export default function MultiSelectWithOther({ legend, options, values, onChange }: MultiSelectWithOtherProps) {
  const fixed = values.filter((value) => options.includes(value) && value !== '其他')
  const other = values.find((value) => !options.includes(value)) ?? (values.includes('其他') ? '其他' : '')
  const selected = other ? [...fixed, '其他'] : fixed
  const optionItems = options.includes('其他') ? options : [...options, '其他']
  return (
    <div className="stack stack--compact">
      <CheckboxGroup
        legend={legend}
        values={selected}
        options={optionItems.map((item) => ({ value: item, label: item }))}
        onChange={(next) => {
          if (!next.includes('其他')) onChange(next.filter((item) => item !== '其他'))
          else onChange([...next.filter((item) => item !== '其他'), other || '其他'])
        }}
      />
      {selected.includes('其他') ? (
        <input
          className="input"
          aria-label={`${legend}其他说明`}
          placeholder="请填写其他说明"
          value={other === '其他' ? '' : other}
          onChange={(event) => onChange([...fixed, event.target.value || '其他'])}
        />
      ) : null}
    </div>
  )
}
