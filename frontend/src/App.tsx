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

import AdminPage from './pages/AdminPage'
import GuidePage from './pages/GuidePage'
import { lazy, Suspense, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'

import { session, SESSION_CHANGED, DATE_CHANGED } from './api/client'
import { authApi } from './api/endpoints'
import { FooterBar, LoadingBlock } from './components'
const KitchenSink = import.meta.env.DEV ? lazy(() => import('./pages/KitchenSink')) : null
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
  const [identityGeneration, setIdentityGeneration] = useState(0)
  const [dateChanged, setDateChanged] = useState(false)

  // 启动时确认本地令牌是否仍然有效（避免"看起来已登录、一点就 401"）
  useEffect(() => {
    let sequence = 0
    let active = true
    const verify = (event?: Event) => {
      const generation = ++sequence
      const token = session.token
      setChecking(true)
      setCurrentUser(null)
      setDateChanged(false)
      setIdentityGeneration(value => value + 1)
      if (!token) {session.bind(null); setChecking(false); return}
      void authApi.me().then(user => {
        if (!active || generation !== sequence || session.token !== token) return
        session.bind(token)
        setCurrentUser(user)
        if (event) navigate('/', {replace: true})
      }).catch(() => {
        if (active && generation === sequence && session.token === token) session.clear()
      }).finally(() => {
        if (active && generation === sequence) setChecking(false)
      })
    }
    // 日期变化先阻断旧草稿，待医生明确重新加载，避免静默套用新的业务日。
    const dates = () => setDateChanged(true)
    verify()
    window.addEventListener(SESSION_CHANGED, verify)
    window.addEventListener(DATE_CHANGED, dates)
    return () => {active = false; ++sequence; window.removeEventListener(SESSION_CHANGED, verify); window.removeEventListener(DATE_CHANGED, dates)}
  }, [])

  if (checking) return <LoadingBlock message="正在确认登录状态…" />
  if (dateChanged && currentUser) return <div role="alert" className="section"><p>业务日期已变化。为避免旧日期草稿误提交，请载入最新日期后重新核对本次资料。</p><button className="btn btn--primary" onClick={() => {setDateChanged(false); setIdentityGeneration(value => value + 1)}}>载入最新日期（放弃旧草稿）</button></div>

  if (!currentUser) {
    return (
      <div className="app-root">
        <Routes>
          {KitchenSink ? <Route path="/dev/kitchen-sink" element={<Suspense fallback={<LoadingBlock message="正在加载…" />}><KitchenSink /></Suspense>} /> : null}
          <Route path="/guide" element={<GuidePage />} />
          <Route path="*" element={<LoginPage onLoggedIn={() => undefined} />} />
        </Routes>
        <FooterBar />
      </div>
    )
  }

  return (
    <div className="app-root" key={identityGeneration}>
      <Routes>
        {KitchenSink ? <Route path="/dev/kitchen-sink" element={<Suspense fallback={<LoadingBlock message="正在加载…" />}><KitchenSink /></Suspense>} /> : null}
        <Route path="/guide" element={<GuidePage />} />
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
        <Route path="/admin" element={currentUser.role === "admin" ? <AdminPage onBack={() => navigate("/")} /> : <Navigate to="/" replace />} />
        <Route
          path="/patients/:id"
          element={<WorkspaceRoute currentUser={currentUser} onBack={() => navigate('/')} />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <FooterBar />
    </div>
  )
}
