/**
 * 文件名称：PatientWorkspacePage.test.tsx
 * 所属层级：页面测试（pages）
 * 功能说明：验证患者工作台的导航规则——这是对 V0.1 界面缺陷的直接回归。

 * 覆盖要点：
 *   1. 未到达的流程单元必须禁用（防止跳步）；
 *   2. 已完成单元**可点击回看**（V0.1 把它们禁用，医生无法回看历史）；
 *   3. 回看为只读，页面不出现任何会改变状态的提交按钮。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PatientWorkspacePage from './PatientWorkspacePage'

const PATIENT = {
  id: 7,
  name: '测试患者',
  gender: '女',
  birth_date: '1980-01-01',
  medical_record_no: 'MRN-UI-0001',
  department: '内分泌科',
  contact_phone: null,
  created_by: 1,
  owner_id: 1,
  owner_display_name: '张医生',
  can_edit: true,
  profile_complete: true,
  is_test_patient: false,
  // 当前处于阶段复评（第 3 个单元）：前两个单元已完成，后三个未到达
  current_state: 'ST32',
  stage: '缓解诱导',
  stage_goal: '减重',
  interventions: '结构化生活方式',
  next_review_date: '2026-12-20',
  last_med_stop_date: null,
  lifestyle_start_date: null,
  surgery_date: null,
  earliest_judge_date: null,
  remission_confirmed_date: null,
  has_glucose_lowering_drug: true,
  drug_purpose: '器官获益',
  created_at: '2026-09-01T09:00:00',
  updated_at: '2026-09-24T09:00:00',
}

const FLOW_UNITS = [
  { key: 'pre', index: 1, label: '60秒缓解预评估', states: ['ST10'] },
  { key: 'full', index: 2, label: '完整评估与计划', states: ['ST20'] },
  { key: 'review', index: 3, label: '阶段复评', states: ['ST31', 'ST32'] },
  { key: 'obs', index: 4, label: '缓解观察期', states: ['ST40'] },
  { key: 'judge', index: 5, label: '缓解判定', states: ['ST50'] },
  { key: 'post', index: 6, label: '缓解后复评', states: ['ST60'] },
]

const EVENTS = {
  total: 2,
  items: [
    {
      id: 2,
      rule_id: 'E1-B01',
      source: 'doctor',
      source_state: 'ST10',
      target_state: 'ST20',
      template_id: 'OUT-E1-ENTER',
      output_text: '当前可进入完整缓解评估。',
      operator_id: 1,
      simulated_date: null,
      created_at: '2026-09-10T10:00:00',
    },
    {
      id: 1,
      rule_id: 'REOPEN',
      source: 'doctor',
      source_state: 'ST00',
      target_state: 'ST10',
      template_id: 'SYS-ST00-REOPEN',
      output_text: '已重新发起60秒缓解预评估，请完成核心五问。',
      operator_id: 1,
      simulated_date: null,
      created_at: '2026-09-09T09:00:00',
    },
  ],
}

/** 按 URL 分发的 fetch 桩。 */
function stubFetch(
  branches: unknown = [],
  options?: {
    patient?: typeof PATIENT
    canUseTestTools?: boolean
  },
) {
  const loadedPatient = options?.patient ?? PATIENT
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/api/patients/7/events')) return Promise.resolve(jsonOk(EVENTS))
    if (url.includes('/api/patients/7/debug/jump-state')) {
      return Promise.resolve(jsonOk({ ...loadedPatient, current_state: 'ST40', stage: null }))
    }
    if (url.includes('/api/patients/7')) return Promise.resolve(jsonOk(loadedPatient))
    if (url.includes('/api/auth/assignable-doctors')) {
      return Promise.resolve(jsonOk([{ id: 2, display_name: '李医生', department: '内分泌科' }]))
    }
    if (url.includes('/api/domain/flow-units')) return Promise.resolve(jsonOk(FLOW_UNITS))
    if (url.includes('/api/domain/branches')) return Promise.resolve(jsonOk(branches))
    if (url.includes('/api/domain/states')) {
      return Promise.resolve(
        jsonOk([
          { code: 'ST32', name: '主动管理—缓解诱导阶段' },
          { code: 'ST40', name: '缓解观察期' },
        ]),
      )
    }
    if (url.includes('/api/test-context')) {
      return Promise.resolve(
        jsonOk({
          test_mode_enabled: options?.canUseTestTools ?? false,
          can_use_test_tools: options?.canUseTestTools ?? false,
          real_date: '2026-09-24',
          effective_date: '2026-09-24',
          simulated_date: null,
        }),
      )
    }
    return Promise.resolve(jsonOk({}))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function jsonOk(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('PatientWorkspacePage 导航规则', () => {
  afterEach(() => vi.restoreAllMocks())

  it('未到达的流程单元被禁用，已完成单元可点击回看', async () => {
    stubFetch()
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{
          id: 1,
          username: 'doctor',
          display_name: '张医生',
          role: 'doctor',
          is_test_account: false,
          simulated_date: null,
        }}
        onBack={() => undefined}
      />,
    )

    // 未到达：缓解观察期（第 4 单元）应禁用
    const observation = await screen.findByRole('button', { name: /缓解观察期/ })
    expect(observation).toBeDisabled()

    // 已完成：60秒缓解预评估（第 1 单元）必须可点击
    const preAssessment = screen.getByRole('button', { name: /60秒缓解预评估/ })
    expect(preAssessment).toBeEnabled()
  })

  it('点击已完成单元进入只读回看，且不出现会改变状态的提交按钮', async () => {
    stubFetch()
    const user = userEvent.setup()
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{
          id: 1,
          username: 'doctor',
          display_name: '张医生',
          role: 'doctor',
          is_test_account: false,
          simulated_date: null,
        }}
        onBack={() => undefined}
      />,
    )

    await user.click(await screen.findByRole('button', { name: /60秒缓解预评估/ }))

    // 回看视图：展示该环节的历史结论
    expect(await screen.findByText(/该环节的历史记录/)).toBeInTheDocument()
    expect(screen.getByText('当前可进入完整缓解评估。')).toBeInTheDocument()
    // 只读：没有"记录…结论"这类提交按钮
    expect(screen.queryByRole('button', { name: /记录.*结论/ })).not.toBeInTheDocument()
  })

  it('阶段复评按后端返回的分支优先级渲染选项', async () => {
    stubFetch([
      {
        priority: 1,
        key: 'uncontrolled',
        rule_id: 'E3-B08',
        label: '存在明显血糖失控（医生确认）',
        hint: '确认后阶段置为血糖稳定。',
        target: 'ST31',
      },
      {
        priority: 3,
        key: 'stop_last_med',
        rule_id: 'E3-B07',
        label: '停用最后一种具有降糖作用的药物',
        hint: '记录停药日期后系统自动进入缓解观察期。',
        target: 'ST40',
      },
    ])
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{
          id: 1,
          username: 'doctor',
          display_name: '张医生',
          role: 'doctor',
          is_test_account: false,
          simulated_date: null,
        }}
        onBack={() => undefined}
      />,
    )

    // 阶段复评为当前环节：应渲染分支单选，且顺序即优先级
    await waitFor(async () => {
      const radios = await screen.findAllByRole('radio')
      expect(radios.length).toBeGreaterThanOrEqual(2)
      expect(radios[0]).toHaveAccessibleName(/存在明显血糖失控/)
      expect(radios[1]).toHaveAccessibleName(/停用最后一种具有降糖作用的药物/)
    })
    // 未选中的分支必须显式说明"本次未生效"，不静默丢弃
    expect(screen.getByText(/本次未生效的分支/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '主动管理—缓解诱导阶段' })).toBeInTheDocument()
  })

  it('测试账号可让测试患者直接进入未来环节，并调用专用 debug 接口', async () => {
    const fetchMock = stubFetch([], {
      patient: { ...PATIENT, is_test_patient: true },
      canUseTestTools: true,
    })
    const user = userEvent.setup()
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{
          id: 1,
          username: 'admin',
          display_name: '管理员',
          role: 'doctor',
          is_test_account: true,
          simulated_date: null,
        }}
        onBack={() => undefined}
      />,
    )

    const observation = await screen.findByRole('button', { name: /缓解观察期/ })
    expect(observation).toBeEnabled()
    expect(screen.getByText('测试工具')).toBeInTheDocument()
    expect(screen.getAllByText('测试患者').length).toBeGreaterThanOrEqual(1)

    await user.click(observation)
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/patients/7/debug/jump-state',
        expect.objectContaining({ method: 'POST' }),
      )
    })
  })

  it('非责任医生工作台显示明确只读原因并禁用流程写控件', async () => {
    stubFetch([], {
      patient: { ...PATIENT, owner_id: 2, owner_display_name: '李医生', can_edit: false },
    })
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{ id: 1, username: 'doctor', display_name: '张医生', role: 'doctor', is_test_account: false, simulated_date: null }}
        onBack={() => undefined}
      />,
    )

    expect(await screen.findByText('您的账户暂无权限编辑此条记录')).toBeInTheDocument()
    expect(screen.getByText(/只读 · 责任医生：李医生/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '记录复评结论' })).toBeDisabled()
  })

  it('管理员转移责任医生前要求二次确认并调用转移接口', async () => {
    const fetchMock = stubFetch()
    const user = userEvent.setup()
    render(
      <PatientWorkspacePage
        patientId={7}
        currentUser={{ id: 9, username: 'admin', display_name: '管理员', role: 'admin', is_test_account: false, simulated_date: null }}
        onBack={() => undefined}
      />,
    )

    await user.click(await screen.findByRole('button', { name: '转移责任医生' }))
    await user.selectOptions(screen.getByLabelText('新的责任医生'), '2')
    await user.click(screen.getByRole('button', { name: '下一步：核对变更' }))
    expect(screen.getByText(/将从“张医生”转给“李医生”/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '确认转移责任医生' }))
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/patients/7/owner',
        expect.objectContaining({ method: 'PUT' }),
      )
    })
  })
})
