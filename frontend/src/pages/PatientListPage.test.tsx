/**
 * 文件名称：PatientListPage.test.tsx
 * 所属层级：页面测试（pages）
 * 功能说明：验证患者列表使用后端状态表显示当前环节，而不是误用主动管理阶段字段。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  浏览器走查回归：ST40/ST50/ST60 不得显示为常规管理
 */

import { render, screen } from '@testing-library/react'
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
                is_test_patient: true,
                current_state: 'ST50',
                stage: null,
                created_at: '2026-09-01T09:00:00',
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
})
