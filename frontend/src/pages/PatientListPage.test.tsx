/**
 * 文件名称：PatientListPage.test.tsx
 * 所属层级：页面测试（pages）
 * 功能说明：验证患者列表使用后端状态表显示当前环节，而不是误用主动管理阶段字段。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  浏览器走查回归：ST40/ST50/ST60 不得显示为常规管理
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PatientListPage from './PatientListPage'

function jsonOk(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('PatientListPage 当前环节', () => {
  afterEach(() => vi.restoreAllMocks())

  it('按后端领域状态表显示缓解判定，不用空 stage 回退为常规管理', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/api/domain/states')) {
          return Promise.resolve(jsonOk([{ code: 'ST50', name: '缓解判定' }]))
        }
        if (url.includes('/api/test-context')) {
          return Promise.resolve(
            jsonOk({
              test_mode_enabled: false,
              can_use_test_tools: false,
              real_date: '2026-09-24',
              effective_date: '2026-09-24',
              simulated_date: null,
            }),
          )
        }
        if (url.endsWith('/api/patients')) {
          return Promise.resolve(
            jsonOk([
              {
                id: 3,
                name: '演示患者二',
                gender: '女',
                birth_date: '1980-01-01',
                medical_record_no: 'MRN-DEMO-002',
                owner_id: 3,
                owner_display_name: '管理员',
                can_edit: true,
                is_test_patient: true,
                current_state: 'ST50',
                stage: null,
                created_at: '2026-09-01T09:00:00',
                updated_at: '2026-09-24T09:00:00',
              },
            ]),
          )
        }
        return Promise.resolve(jsonOk({}))
      }),
    )

    render(
      <PatientListPage
        currentUser={{
          id: 3,
          username: 'admin',
          display_name: '管理员',
          role: 'doctor',
          is_test_account: true,
          simulated_date: null,
        }}
        onOpenPatient={vi.fn()}
        onLogout={vi.fn()}
      />,
    )

    expect(await screen.findByText('缓解判定')).toBeInTheDocument()
    expect(screen.queryByText('常规糖尿病综合管理')).not.toBeInTheDocument()
  })

  it('按有效今天执行默认到期顺序，并支持搜索与表头双向排序', async () => {
    const user = userEvent.setup()
    const rows = [
      ['未来患者', 'MRN-3', '2026-09-25', '2026-09-24T12:00:00'],
      ['无日期患者', 'MRN-4', null, '2026-09-24T13:00:00'],
      ['今日患者', 'MRN-2', '2026-09-24', '2026-09-24T10:00:00'],
      ['逾期患者', 'MRN-1', '2026-09-23', '2026-09-24T11:00:00'],
    ].map(([name, medicalRecordNo, nextReviewDate, updatedAt], index) => ({
      id: index + 1,
      name,
      gender: '女',
      birth_date: '1980-01-01',
      medical_record_no: medicalRecordNo,
      department: '内分泌科',
      contact_phone: null,
      created_by: 3,
      owner_id: 3,
      owner_display_name: '管理员',
      can_edit: true,
      profile_complete: true,
      is_test_patient: false,
      current_state: 'ST31',
      stage: '血糖稳定',
      next_review_date: nextReviewDate,
      created_at: '2026-09-01T09:00:00',
      updated_at: updatedAt,
    }))
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url.includes('/api/domain/states')) return Promise.resolve(jsonOk([{ code: 'ST31', name: '血糖稳定阶段' }]))
        if (url.includes('/api/test-context')) return Promise.resolve(jsonOk({ effective_date: '2026-09-24' }))
        if (url.endsWith('/api/patients')) return Promise.resolve(jsonOk(rows))
        return Promise.resolve(jsonOk({ departments: ['内分泌科'] }))
      }),
    )
    render(
      <PatientListPage
        currentUser={{ id: 3, username: 'admin', display_name: '管理员', role: 'admin', is_test_account: false, simulated_date: null }}
        onOpenPatient={vi.fn()}
        onLogout={vi.fn()}
      />,
    )

    await screen.findByText('逾期患者')
    const patientRows = screen.getAllByRole('row').slice(1)
    expect(patientRows.map((row) => row.textContent)).toEqual([
      expect.stringContaining('逾期患者'),
      expect.stringContaining('今日患者'),
      expect.stringContaining('未来患者'),
      expect.stringContaining('无日期患者'),
    ])
    expect(patientRows[0]).toHaveClass('patient-row--overdue')
    expect(patientRows[1]).toHaveClass('patient-row--today')

    await user.type(screen.getByRole('searchbox'), 'MRN-3')
    expect(screen.getAllByRole('row')).toHaveLength(2)
    expect(screen.getByText('未来患者')).toBeInTheDocument()
    await user.clear(screen.getByRole('searchbox'))

    const nameHeader = screen.getByRole('button', { name: /姓名/ })
    await user.click(nameHeader)
    const ascendingRows = screen.getAllByRole('row').slice(1)
    expect(within(ascendingRows[0]).getByText('今日患者')).toBeInTheDocument()
    await user.click(nameHeader)
    expect(nameHeader.closest('th')).toHaveAttribute('aria-sort', 'descending')
  })
})
