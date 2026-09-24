/**
 * 页面测试：第三批阶段复评测量值默认带入，清空后由后端沿用旧快照。
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Patient } from '../../types'
import PhaseReviewPage from './PhaseReviewPage'

const PATIENT: Patient = {
  id: 21,
  name: '复评测量患者',
  gender: '女',
  birth_date: '1980-01-01',
  medical_record_no: 'MRN-PHASE-MEASURE',
  department: '内分泌科',
  contact_phone: null,
  created_by: 1,
  owner_id: 1,
  owner_display_name: '张医生',
  can_edit: true,
  profile_complete: true,
  is_test_patient: false,
  height_cm: 175,
  weight_kg: 70,
  bmi: 22.9,
  current_state: 'ST31',
  stage: '血糖稳定',
  stage_goal: '安全改善明显高血糖',
  interventions: '结构化生活方式',
  next_review_date: '2026-12-20',
  last_med_stop_date: null,
  lifestyle_start_date: null,
  surgery_date: null,
  earliest_judge_date: null,
  remission_confirmed_date: null,
  has_glucose_lowering_drug: false,
  drug_purpose: null,
  created_at: '2026-09-01T09:00:00',
  updated_at: '2026-09-24T09:00:00',
}

function jsonOk(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('PhaseReviewPage 测量快照', () => {
  afterEach(() => vi.restoreAllMocks())

  it('默认带入最新身高体重，清空字段时提交 null 表示沿用旧值', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/api/domain/branches')) {
        return Promise.resolve(jsonOk([{
          priority: 4,
          key: 'routine_action',
          rule_id: 'E3-B01',
          label: '常规复评动作',
          hint: '由医生选择继续、调整、转换或结束。',
          target: 'ST31',
        }]))
      }
      if (url.includes('/api/patients/21/phase-review') && init?.method === 'POST') {
        return Promise.resolve(jsonOk({
          rule_id: 'E3-B01',
          template_id: 'OUT-E3-CONTINUE',
          output_text: '继续当前阶段。',
          target_state: 'ST31',
          stage: '血糖稳定',
          stage_goal: null,
          next_review_date: '2026-12-17',
          entered_observation: false,
          earliest_judge_date: null,
          ignored_branches: [],
        }))
      }
      return Promise.resolve(jsonOk({}))
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<PhaseReviewPage patient={PATIENT} onUpdated={vi.fn()} />)

    const weight = await screen.findByLabelText('本次体重')
    const height = screen.getByLabelText('本次身高')
    expect(weight).toHaveValue(70)
    expect(height).toHaveValue(175)
    expect(screen.getByText(/当前 BMI：22.9/)).toBeInTheDocument()

    await user.clear(weight)
    await user.click(screen.getByRole('button', { name: '记录复评结论' }))
    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) => String(input).includes('/phase-review'))
      expect(call).toBeDefined()
      const body = JSON.parse(String(call?.[1]?.body))
      expect(body.f018_weight).toBeNull()
      expect(body.f019_height).toBe(175)
    })
  })
})
