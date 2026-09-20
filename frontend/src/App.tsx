/**
 * 组件名称：App.tsx
 * 所属层级：根组件（src）
 * 功能说明：路由装配与会话引导。
 *   - 已登录：`/` 患者列表，`/patients/:id` 患者工作台；
 *   - 未登录：显示登录页（首次运行时同页完成账号创建）；
 *   - 启动时若本地有令牌，先向后端确认会话是否仍然有效。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现（替换 M1 的组件库自检页；自检页保留在 /dev/kitchen-sink）
 */

import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'

import { session } from './api/client'
import { authApi } from './api/endpoints'
import { LoadingBlock } from './components'
import KitchenSink from './pages/KitchenSink'
import LoginPage from './pages/LoginPage'
import PatientListPage from './pages/PatientListPage'
import PatientWorkspacePage from './pages/PatientWorkspacePage'
import type { UserOut } from './types'

/** 患者工作台路由包装（从 URL 取患者主键）。 */
function WorkspaceRoute({ currentUser, onBack }: { currentUser: UserOut; onBack: () => void }) {
  const params = useParams()
  const patientId = Number(params.id)
  if (!Number.isFinite(patientId)) return <Navigate to="/" replace />
  return <PatientWorkspacePage patientId={patientId} currentUser={currentUser} onBack={onBack} />
}

/** 根组件：负责会话状态与路由。 */
export default function App() {
  const navigate = useNavigate()
  const [currentUser, setCurrentUser] = useState<UserOut | null>(null)
  const [checking, setChecking] = useState(true)

  // 启动时确认本地令牌是否仍然有效（避免"看起来已登录、一点就 401"）
  useEffect(() => {
    if (!session.token) {
      setChecking(false)
      return
    }
    authApi
      .me()
      .then(setCurrentUser)
      .catch(() => {
        session.clear()
        setCurrentUser(null)
      })
      .finally(() => setChecking(false))
  }, [])

  if (checking) return <LoadingBlock message="正在确认登录状态…" />

  if (!currentUser) {
    return (
      <Routes>
        <Route path="/dev/kitchen-sink" element={<KitchenSink />} />
        <Route path="*" element={<LoginPage onLoggedIn={setCurrentUser} />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route path="/dev/kitchen-sink" element={<KitchenSink />} />
      <Route
        path="/"
        element={
          <PatientListPage
            currentUser={currentUser}
            onOpenPatient={(patientId) => navigate(`/patients/${patientId}`)}
            onLogout={() => {
              void authApi.logout().catch(() => undefined)
              session.clear()
              setCurrentUser(null)
            }}
          />
        }
      />
      <Route
        path="/patients/:id"
        element={<WorkspaceRoute currentUser={currentUser} onBack={() => navigate('/')} />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
