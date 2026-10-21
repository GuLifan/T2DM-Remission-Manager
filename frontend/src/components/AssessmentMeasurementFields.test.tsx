import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Patient } from '../types'
import AssessmentMeasurementFields from './AssessmentMeasurementFields'

const patient = {
  id: 1,
  name: '测试患者',
  gender: '女',
  birth_date: '1980-01-01',
  medical_record_no: 'TEST-001',
  department: '内分泌科',
  current_state: 'ST31',
  height_cm: 165,
  weight_kg: 70,
  bmi: 25.7,
} as Patient

describe('AssessmentMeasurementFields', () => {
  it('不预填本次体重，并把已确认身高设为只读', () => {
    render(
      <AssessmentMeasurementFields
        patient={patient}
        weight=""
        onWeightChange={vi.fn()}
        height="165"
        onHeightChange={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('本次体重')).toHaveValue(null)
    expect(screen.getByLabelText('本次体重')).toBeRequired()
    expect(screen.getByLabelText('身高')).toHaveAttribute('readonly')
    expect(screen.getByText(/上次记录 70 kg/)).toBeInTheDocument()
  })
})
