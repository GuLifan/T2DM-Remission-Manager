/**
 * 文件名称：tone.ts
 * 所属层级：通用组件（components）
 * 功能说明：语义色调类型。与 UI.md 3.4 的四种语义一一对应：
 *   neutral（进行中/中性）/ success（达标）/ warning（暂缓/需注意）/ error（风险/阻断）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

export type Tone = 'neutral' | 'success' | 'warning' | 'error'
