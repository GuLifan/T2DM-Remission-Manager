import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Patient } from '../../types'
import ClinicalPage from './ClinicalPage'
import MedicationEditor from './MedicationEditor'
import type { ClinicalContext } from './types'

const patient = (state: string): Patient => ({
  id: 303, name: 'v0.3虚构患者', gender: '女', birth_date: '1980-01-01', medical_record_no: 'V03-UI',
  department: '内分泌科', contact_phone: null, created_by: 1, owner_id: 1, owner_display_name: '测试医生',
  can_edit: true, profile_complete: true, is_test_patient: true, height_cm: 165, weight_kg: 70, bmi: 25.7,
  current_state: state, stage: state === 'ST32' ? '缓解诱导' : null, stage_goal: null, interventions: null,
  next_review_date: null, last_med_stop_date: state === 'ST40' ? '2026-05-01' : null,
  lifestyle_start_date: null, surgery_date: null, earliest_judge_date: state === 'ST40' ? '2026-08-01' : null,
  remission_confirmed_date: null, has_glucose_lowering_drug: false, drug_purpose: null,
  clinical_contract_version: 'v0.3', clinical_revision: 4, observation_status: state === 'ST40' ? 'active' : 'none',
  observation_cycle: state === 'ST40' ? 1 : 0, applicable_interventions: ['其他'], actual_stop_confirmed: true,
  current_remission_evaluation: null, objective_assessment_event_id: null,
  created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00',
})

const context: ClinicalContext = {
  patient_revision: 4, measurement: {id: 10, kind: 'measurement', clinical_date: '2026-01-01', source_event_id: 1, supersedes_id: null, created_at: '2026-01-01', data: {weight_kg: 70, height_cm: 165, bmi: 25.7, measured_on: '2026-01-01'}},
  measurements: [], weight_reduction_percent: null, regimen: null, duration: null, examinations: [], carried: {},
}
const catalog = {version: 'test', categories: [{id: 'insulin', name: '胰岛素类', medications: [{id: 'insulin-1', name: '门冬胰岛素', aliases: []}]}, {id: 'metformin', name: '二甲双胍', medications: [{id: 'met-1', name: '二甲双胍', aliases: []}, {id: 'met-2', name: '二甲双胍缓释片', aliases: []}]}]}
function response(data: unknown) {return new Response(JSON.stringify(data), {status: 200, headers: {'Content-Type': 'application/json'}})}
function mockFetch() {
  const fetcher = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/context')) return Promise.resolve(response(context))
    if (url.endsWith('/test-context')) return Promise.resolve(response({effective_date: '2026-10-19'}))
    if (url.endsWith('/reference')) return Promise.resolve(response({medication_catalog: catalog}))
    return Promise.resolve(response({clinical_contract_version: 'v0.3', transition_ids: ['T01'], target_state: 'ST20', output_text: '已保存', tasks: [], objective_met: false, patient_revision: 5, assessment_event_id: 1, method: init?.method}))
  })
  vi.stubGlobal('fetch', fetcher); return fetcher
}
describe('v0.4临床交互', () => {
  afterEach(() => {vi.restoreAllMocks(); vi.unstubAllGlobals()})
  it('沿用原测量引用，A04留空，由本次医生选择后保存', async () => {
    const fetcher = mockFetch(); const updated = vi.fn(); const user = userEvent.setup()
    render(<ClinicalPage patient={patient('ST10')} onUpdated={updated} />)
    expect(await screen.findByText('沿用体重 70 kg')).toBeInTheDocument()
    const contextGroup = screen.getByRole('group', {name: '治疗背景充分'})
    expect(within(contextGroup).getAllByRole('radio').every(r => !(r as HTMLInputElement).checked)).toBe(true)
    await user.click(within(contextGroup).getByLabelText('是'))
    await user.type(screen.getByLabelText('病程月'), '18')
    await user.click(screen.getByRole('button', {name: '保存预评估结论'}))
    const dialog = await screen.findByRole('dialog', {name: '保存预评估结论'})
    await user.click(within(dialog).getByRole('button', {name: '保存预评估结论'}))
    await waitFor(() => expect(updated).toHaveBeenCalled())
    const call = fetcher.mock.calls.find(([url]) => String(url).endsWith('/pre-assessment'))!
    const body = JSON.parse(String(call[1]?.body))
    expect(body.measurement_id).toBe(10); expect(body.f018_weight).toBeNull()
    expect(body.duration_years).toBeNull(); expect(body.duration_months).toBe(18)
    expect(body.expected_revision).toBe(4); expect(body.input_schema_version).toBe('v0.4')
  })
  it('外部资料更新保留草稿并阻断旧版本覆盖', async () => {
    mockFetch(); const user = userEvent.setup(); const original = patient('ST10')
    const view = render(<ClinicalPage patient={original} onUpdated={vi.fn()} />)
    await screen.findByText('沿用体重 70 kg')
    await user.type(screen.getByLabelText('病程月'), '18')
    view.rerender(<ClinicalPage patient={{...original, clinical_revision: 5}} onUpdated={vi.fn()} />)
    expect(await screen.findByText('病例资料已更新，当前未保存内容仍保留；请载入最新资料后重新核对。')).toBeInTheDocument()
    expect(screen.getByLabelText('病程月')).toHaveValue(18)
    expect(screen.getByRole('button', {name: '保存预评估结论'})).toBeDisabled()
  })
  it('观察页显式POST刷新，内部状态不显示', async () => {
    const fetcher = mockFetch()
    render(<ClinicalPage patient={patient('ST40')} onUpdated={vi.fn()} />)
    await waitFor(() => expect(fetcher.mock.calls.some(([url, init]) => String(url).endsWith('/refresh') && init?.method === 'POST')).toBe(true))
    expect(screen.queryByText('ST40')).not.toBeInTheDocument()
  })
  it('跨类别批量生成多张卡并保留已有方案，不猜药效或剂量', async () => {
    mockFetch(); const changed = vi.fn(); const user = userEvent.setup()
    HTMLDialogElement.prototype.showModal = function () {this.setAttribute('open', '')}
    HTMLDialogElement.prototype.close = function () {this.removeAttribute('open')}
    render(<MedicationEditor value={[{medication_id: 'saved', name: '自填药物', dose: '原方案', status: '已停用', has_glucose_lowering_effect: true, purpose: '高血糖治疗', started_on: null, stopped_on: '2026-01-01'}]} onChange={changed} />)
    await user.click(screen.getByRole('button', {name: '选择常用药物'}))
    await user.click(await screen.findByRole('checkbox', {name: '门冬胰岛素'}))
    await user.click(screen.getByRole('button', {name: '二甲双胍'}))
    await user.click(screen.getByRole('checkbox', {name: '二甲双胍缓释片'}))
    expect(changed).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', {name: '添加所选药物'}))
    const next = changed.mock.calls[0][0]
    expect(next).toHaveLength(3); expect(next[0].status).toBe('已停用')
    expect(next[1]).toMatchObject({name: '门冬胰岛素', dose: '', status: '使用中', has_glucose_lowering_effect: null, start_precision: 'unknown', purposes: []})
    expect(next[2].name).toBe('二甲双胍缓释片')
  })
  it('历史药物矛盾须本次明确核对，改药后撤销确认且不发送旧事实', async () => {
    const previous = context.regimen
    context.regimen = {id:20,kind:'medication_regimen',clinical_date:'2026-10-19',source_event_id:1,supersedes_id:null,created_at:'2026-10-19',data:{medications:[],complete:true}}
    try {
      // jsdom不实现滚动；实际浏览器另验字段定位，此处检查未核对不发请求。
      HTMLElement.prototype.scrollIntoView=vi.fn()
      const fetcher=mockFetch(),user=userEvent.setup()
      render(<ClinicalPage patient={{...patient('ST31'),has_glucose_lowering_drug:true}} onUpdated={vi.fn()} />)
      const flag=await screen.findByLabelText('已核对历史药物不一致，本次以当前方案为准')
      expect(flag).not.toBeChecked()
      await user.click(flag);expect(flag).toBeChecked()
      await user.click(screen.getByRole('button',{name:'手动添加药物'}))
      expect(flag).not.toBeChecked()
      await user.click(screen.getByRole('button',{name:'保存本次复评'}))
      expect(await screen.findByText('请先明确核对历史药物不一致，再确认本次当前方案。')).toBeInTheDocument()
      expect(fetcher.mock.calls.some(([url,init])=>String(url).endsWith('/phase-review')&&init?.method==='POST')).toBe(false)
    } finally {context.regimen=previous}
  })

})
