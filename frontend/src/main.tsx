/**
 * 文件名称：main.tsx
 * 所属层级：入口（src）
 * 功能说明：挂载 React 应用并引入全局样式。
 *   样式引入顺序：Token → 基础样式 → 组件样式（后者依赖前者）。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M1 初始实现
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import './styles/tokens.css'
import './styles/base.css'
import './styles/components.css'
import './styles/pages.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {/* BrowserRouter 放在根组件之外：App 内部使用 useNavigate/Routes 需要路由上下文 */}
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
