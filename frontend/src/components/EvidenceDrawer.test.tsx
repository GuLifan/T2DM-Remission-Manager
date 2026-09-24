/** M6-C 医学依据抽屉的状态、检索、取消旧请求与焦点管理测试。 */

import { useState } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import EvidenceDrawer from './EvidenceDrawer'

const READY_STATUS = {
  expected_count: 4,
  indexed_count: 4,
  searchable: true,
  last_imported_at: '2026-09-24T10:00:00',
  materials: [],
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** 提供真实打开/关闭流程，以验证关闭后焦点回到触发按钮。 */
function DrawerHarness() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>查阅医学依据</button>
      <EvidenceDrawer open={open} onClose={() => setOpen(false)} />
    </>
  )
}

describe('EvidenceDrawer 医学依据抽屉', () => {
  afterEach(() => vi.restoreAllMocks())

  it('打开后读取材料状态、聚焦检索框并固定显示免责声明', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(READY_STATUS))))
    const user = userEvent.setup()
    render(<DrawerHarness />)

    await user.click(screen.getByRole('button', { name: '查阅医学依据' }))
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await waitFor(() => expect(input).toHaveFocus())
    expect(await screen.findByText('已载入 4 份医学依据。')).toBeInTheDocument()
    expect(screen.getByText('以下内容仅供查阅原始依据，不替代医生判断。')).toBeInTheDocument()
  })

  it('材料未完整导入时显示明确状态而不是无结果', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({ ...READY_STATUS, indexed_count: 2, searchable: false }),
        ),
      ),
    )
    render(<EvidenceDrawer open onClose={() => undefined} />)

    expect(
      await screen.findByText('医学依据尚未完整导入，请联系系统维护人员完成本地导入。'),
    ).toBeInTheDocument()
    expect(screen.getByText('当前已就绪 2 / 4 份材料。')).toBeInTheDocument()
  })

  it('不足 2 个字符时不发检索请求，达到条件后延迟检索并显示 PDF 与章节出处', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/evidence/status') return Promise.resolve(jsonResponse(READY_STATUS))
      return Promise.resolve(
        jsonResponse({
          query: '缓解',
          search_mode: 'like',
          materials_indexed: 4,
          total: 2,
          returned: 2,
          items: [
            {
              evidence_id: 1,
              source_key: 'consensus',
              title: '2 型糖尿病缓解中国专家共识',
              source_type: 'pdf',
              page_no: 4,
              section: null,
              snippet: '<mark>缓解</mark>原文不会被当成 HTML。',
            },
            {
              evidence_id: 2,
              source_key: 'locked',
              title: '临床流程锁定稿 v1.0',
              source_type: 'markdown',
              page_no: null,
              section: '九、事件4｜缓解判定',
              snippet: '锁定稿中的缓解判定原文。',
            },
          ],
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    const { container } = render(<EvidenceDrawer open onClose={() => undefined} />)
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await screen.findByText('已载入 4 份医学依据。')

    await user.type(input, '缓')
    expect(screen.getByText('请输入至少 2 个字符。')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)

    await user.type(input, '解')
    expect(await screen.findByText('找到 2 条，当前显示 2 条。')).toBeInTheDocument()
    expect(screen.getByText('出处：2 型糖尿病缓解中国专家共识 · PDF 第 4 页')).toBeInTheDocument()
    expect(screen.getByText('出处：临床流程锁定稿 v1.0 · 九、事件4｜缓解判定')).toBeInTheDocument()
    expect(screen.getByText('<mark>缓解</mark>原文不会被当成 HTML。')).toBeInTheDocument()
    expect(container.querySelector('mark')).toBeNull()
  })

  it('快速连续输入时只发送最后一个已稳定查询', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/evidence/status') return Promise.resolve(jsonResponse(READY_STATUS))
      const query = new URL(url, 'http://localhost').searchParams.get('q') ?? ''
      return Promise.resolve(
        jsonResponse({
          query,
          search_mode: 'fts5_trigram',
          materials_indexed: 4,
          total: 1,
          returned: 1,
          items: [{
            evidence_id: 3,
            source_key: 'english',
            title: '英文共识',
            source_type: 'pdf',
            page_no: 8,
            section: null,
            snippet: `最终结果：${query}`,
          }],
        }),
      )
    })
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<EvidenceDrawer open onClose={() => undefined} />)
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await screen.findByText('已载入 4 份医学依据。')

    await user.type(input, '停药时间')
    await user.clear(input)
    await user.type(input, 'HbA1c')

    expect(await screen.findByText('最终结果：HbA1c')).toBeInTheDocument()
    const searchUrls = fetchMock.mock.calls
      .map(([input]) => String(input))
      .filter((url) => url.startsWith('/api/evidence/search'))
    expect(searchUrls).toHaveLength(1)
    expect(searchUrls[0]).toContain('q=HbA1c')
  })

  it('查询无命中时显示无结果且不误报为材料未导入', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input) === '/api/evidence/status') return Promise.resolve(jsonResponse(READY_STATUS))
        return Promise.resolve(
          jsonResponse({
            query: '不存在词',
            search_mode: 'fts5_trigram',
            materials_indexed: 4,
            total: 0,
            returned: 0,
            items: [],
          }),
        )
      }),
    )
    const user = userEvent.setup()
    render(<EvidenceDrawer open onClose={() => undefined} />)
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await screen.findByText('已载入 4 份医学依据。')
    await user.type(input, '不存在词')

    expect(await screen.findByText('未找到与“不存在词”匹配的原文。')).toBeInTheDocument()
    expect(screen.getByText(/这不表示医学依据尚未导入/)).toBeInTheDocument()
  })

  it('同一材料同一页的多条命中均稳定渲染且不产生重复键警告', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input) === '/api/evidence/status') return Promise.resolve(jsonResponse(READY_STATUS))
        return Promise.resolve(
          jsonResponse({
            query: 'HbA1c',
            search_mode: 'fts5_trigram',
            materials_indexed: 4,
            total: 2,
            returned: 2,
            items: [
              {
                evidence_id: 2,
                source_key: 'guideline',
                title: '中国糖尿病防治指南（2024 版）',
                source_type: 'pdf',
                page_no: 14,
                section: null,
                snippet: '同页第一条 HbA1c 原文。',
              },
              {
                evidence_id: 2,
                source_key: 'guideline',
                title: '中国糖尿病防治指南（2024 版）',
                source_type: 'pdf',
                page_no: 14,
                section: null,
                snippet: '同页第二条 HbA1c 原文。',
              },
            ],
          }),
        )
      }),
    )
    const user = userEvent.setup()
    render(<EvidenceDrawer open onClose={() => undefined} />)
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await screen.findByText('已载入 4 份医学依据。')
    await user.type(input, 'HbA1c')

    expect(await screen.findByText('同页第一条 HbA1c 原文。')).toBeInTheDocument()
    expect(screen.getByText('同页第二条 HbA1c 原文。')).toBeInTheDocument()
    expect(consoleError.mock.calls.flat().join(' ')).not.toContain(
      'Encountered two children with the same key',
    )
  })

  it('状态失败可重新读取，检索失败可重新检索', async () => {
    let statusCalls = 0
    let searchCalls = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        if (String(input) === '/api/evidence/status') {
          statusCalls += 1
          return Promise.resolve(
            statusCalls === 1
              ? jsonResponse({ detail: '暂时无法读取依据状态。' }, 503)
              : jsonResponse(READY_STATUS),
          )
        }
        searchCalls += 1
        return Promise.resolve(
          searchCalls === 1
            ? jsonResponse({ detail: '暂时无法检索依据。' }, 503)
            : jsonResponse({
                query: '缓解',
                search_mode: 'like',
                materials_indexed: 4,
                total: 0,
                returned: 0,
                items: [],
              }),
        )
      }),
    )
    const user = userEvent.setup()
    render(<EvidenceDrawer open onClose={() => undefined} />)

    expect(await screen.findByText('暂时无法读取依据状态。')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新读取' }))
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    await screen.findByText('已载入 4 份医学依据。')
    await user.type(input, '缓解')
    expect(await screen.findByText('暂时无法检索依据。')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '重新检索' }))
    expect(await screen.findByText('未找到与“缓解”匹配的原文。')).toBeInTheDocument()
  })

  it('Tab 焦点不离开抽屉，Esc 关闭后焦点回到原触发按钮', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(jsonResponse(READY_STATUS))))
    const user = userEvent.setup()
    render(<DrawerHarness />)
    const trigger = screen.getByRole('button', { name: '查阅医学依据' })
    await user.click(trigger)
    const input = await screen.findByRole('searchbox', { name: '检索原始依据' })
    const close = screen.getByRole('button', { name: '关闭依据面板' })
    await waitFor(() => expect(input).toHaveFocus())

    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(input).toHaveFocus()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '医学依据' })).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })
})
