/**
 * 文件名称：ResultBanner.test.tsx
 * 所属层级：组件测试（components）
 * 功能说明：验证结论提示区按语义着色，且空文案不渲染（避免出现空白提示块）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import ResultBanner from './ResultBanner'

describe('ResultBanner', () => {
  it('按语义输出对应色调的提示区', () => {
    const { container } = render(<ResultBanner tone="warning" text="暂缓进入完整评估。" />)
    expect(screen.getByRole('status')).toHaveTextContent('暂缓进入完整评估。')
    expect(container.querySelector('.result-banner--warning')).not.toBeNull()
  })

  it('文案为空时不渲染', () => {
    const { container } = render(<ResultBanner text="" />)
    expect(container).toBeEmptyDOMElement()
  })
})
