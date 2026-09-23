/**
 * 组件名称：TestToolsPanel.tsx
 * 所属层级：通用组件（components）
 * 功能说明：只为测试账号与测试患者显示的流程跳转面板。
 *
 * 安全说明：选择项只显示自然语言；后端仍执行测试模式、账号、患者三重守卫，
 * 并把每次跳转记录为 debug 事件。
 *
 * 修改历史：
 *   - 2026-09-24  v1.0  第一批测试流程跳转
 */

import { useEffect, useState } from 'react'

import type { StateOut } from '../types'

interface TestToolsPanelProps {
  states: StateOut[]
  currentState: string
  jumping: boolean
  error?: string
  onJump: (targetState: string) => void
}

/** 测试流程跳转面板。 */
export default function TestToolsPanel({
  states,
  currentState,
  jumping,
  error,
  onJump,
}: TestToolsPanelProps) {
  const [targetState, setTargetState] = useState(currentState)

  useEffect(() => setTargetState(currentState), [currentState])

  return (
    <section className="test-tools-panel" aria-label="测试流程跳转">
      <div>
        <h3 className="test-tools-panel__title">测试工具</h3>
        <p className="test-tools-panel__description">
          仅用于演示患者。跳转会写入测试事件，不属于正式临床流程。
        </p>
      </div>
      <div className="test-tools-panel__actions">
        <label htmlFor="debug-target-state">查看环节</label>
        <select
          className="select"
          id="debug-target-state"
          value={targetState}
          onChange={(event) => setTargetState(event.target.value)}
        >
          {states.map((state) => (
            <option key={state.code} value={state.code}>
              {state.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn btn--outlined"
          disabled={jumping || targetState === currentState}
          onClick={() => onJump(targetState)}
        >
          {jumping ? '正在切换…' : '切换测试环节'}
        </button>
      </div>
      {error ? <span className="test-tools-panel__error" role="alert">{error}</span> : null}
    </section>
  )
}
