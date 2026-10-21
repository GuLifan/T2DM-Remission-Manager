import type { Patient } from '../types'
import FieldRow from './FieldRow'
import NumericInput from './NumericInput'

interface AssessmentMeasurementFieldsProps {
  patient: Patient
  weight: string
  onWeightChange: (value: string) => void
  height: string
  onHeightChange: (value: string) => void
  optional?: boolean
}

/**
 * 每次临床评估共用的测量字段。
 *
 * 旧流程要求新体重；v0.4通过optional模式与独立引用区域支持选填/沿用。身高只在尚无确认值时开放录入，
 * 一旦确认便以只读方式展示。管理员更正身高使用独立的高权限入口。
 */
export default function AssessmentMeasurementFields({
  patient,
  weight,
  onWeightChange,
  height,
  onHeightChange,
  optional = false,
}: AssessmentMeasurementFieldsProps) {
  const effectiveHeight = patient.height_cm == null ? height : String(patient.height_cm)
  const bmi = weight && effectiveHeight
    ? Number(weight) / ((Number(effectiveHeight) / 100) ** 2)
    : null

  return (
    <>
      <FieldRow
        label="本次体重"
        hint={optional ? '选填；沿用历史测量时无需重复输入。' : patient.weight_kg == null ? '必填；请输入本次实测值。' : `必填；上次记录 ${patient.weight_kg} kg，仅供参考。`}
      >
        {(fieldProps) => (
          <NumericInput
            {...fieldProps}
            required={!optional}
            value={weight}
            onChange={onWeightChange}
            unit="kg"
            min={0.1}
            max={500}
            step={0.1}
          />
        )}
      </FieldRow>
      {patient.height_cm == null ? (
        <FieldRow label="身高" hint="首次确认后锁定；如需更正须由管理员操作。">
          {(fieldProps) => (
            <NumericInput
              {...fieldProps}
              required={!optional}
              value={height}
              onChange={onHeightChange}
              unit="cm"
              min={50}
              max={250}
              step={0.1}
            />
          )}
        </FieldRow>
      ) : (
        <FieldRow label="身高" hint="已确认并锁定；管理员可在患者工作台更正。">
          {(fieldProps) => (
            <NumericInput
              {...fieldProps}
              readOnly
              value={String(patient.height_cm)}
              onChange={() => undefined}
              unit="cm"
            />
          )}
        </FieldRow>
      )}
      <FieldRow label="BMI" hint="按本次体重与已确认身高计算，仅作记录。">
        {(fieldProps) => (
          <input
            {...fieldProps}
            className="input num"
            readOnly
            value={bmi && Number.isFinite(bmi) ? bmi.toFixed(1) : ''}
          />
        )}
      </FieldRow>
    </>
  )
}
