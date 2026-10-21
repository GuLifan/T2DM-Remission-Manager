/** 验收界面权限与历史原值兼容；不以文案清洗修改临床资料。 */
import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { DateControl } from '../components'
import { patientNumber } from '../presentation'
import GuidePage from './GuidePage'
import ExaminationEditor, { blankExamination } from './clinical/ExaminationEditor'
import { PayloadView } from './clinical/HistoryDetail'

afterEach(() => vi.restoreAllMocks())

it('普通账号即使有通用隔离能力也没有日期编辑入口', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    can_use_test_tools: true, can_manage_date: false, effective_date: '2026-10-20', real_date: '2026-10-20', simulated_date: null,
  }), {status: 200}))))
  render(<DateControl editable />)
  expect(await screen.findByText('当前日期：2026/10/20')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

it('管理员在患者工作台默认仍只读，编辑需管理区显式开启', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(JSON.stringify({
    can_use_test_tools: true, can_manage_date: true, effective_date: '2027-01-01', real_date: '2026-10-20', simulated_date: '2027-01-01',
  }), {status: 200}))))
  render(<DateControl />)
  expect(await screen.findByText('当前日期：2027/01/01')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
})

it('新检查没有旧来源候选，已有来源按兼容名称显示而不改数据', () => {
  const old = {...blankExamination(), source: '测试数据'}
  const changed = vi.fn()
  const {unmount} = render(<ExaminationEditor value={[blankExamination()]} onChange={changed} saved={[]} selectedIds={[]} onSelect={vi.fn()} />)
  expect(screen.queryByRole('option', {name: '测试数据'})).not.toBeInTheDocument()
  expect(screen.queryByRole('option', {name: '历史录入来源'})).not.toBeInTheDocument()
  unmount()
  render(<ExaminationEditor value={[old]} onChange={changed} saved={[]} selectedIds={[]} onSelect={vi.fn()} />)
  expect(screen.getByRole('option', {name: '历史录入来源'})).toHaveValue('测试数据')
  expect(old.source).toBe('测试数据')
  expect(changed).not.toHaveBeenCalled()
})

it('历史来源显示映射不清洗医生自由文本，编号由患者ID稳定推导', () => {
  const value = {source: '测试数据', note: '测试数据'}
  render(<PayloadView value={value} />)
  expect(screen.getByText('历史录入来源')).toBeInTheDocument()
  expect(screen.getByText('测试数据')).toBeInTheDocument()
  expect(value).toEqual({source: '测试数据', note: '测试数据'})
  expect(patientNumber({id: 7})).toBe('ETMMS-000007')
  expect(patientNumber({id: 1000001})).toBe('ETMMS-1000001')
})

it('公开使用指南保留临床确认与归档说明，采用完整业务文案', () => {
  const {container} = render(<GuidePage />)
  expect(screen.getByRole('heading', {name: 'ETMMS 使用指南'})).toBeInTheDocument()
  expect(screen.getByRole('heading', {name: '归档并新建'})).toBeInTheDocument()
  expect(container.textContent).not.toMatch(/虚拟|虚构|模拟|测试|demo/i)
  expect(container.textContent).toContain('客观符合后仍须医生独立确认缓解')
})
