/**
 * 组件名称：App.tsx
 * 所属层级：根组件（src）
 * 功能说明：路由装配。
 *   M1 阶段仅有组件库预览页（用于验证 Token 与组件规范落地）；
 *   M5 阶段将替换为登录页 / 患者列表 / 患者工作台。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { BrowserRouter, Route, Routes } from 'react-router-dom'

import KitchenSink from './pages/KitchenSink'

/** 根组件。 */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<KitchenSink />} />
      </Routes>
    </BrowserRouter>
  )
}
