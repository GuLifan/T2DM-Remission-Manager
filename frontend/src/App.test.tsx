import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from './App'
import { session } from './api/client'
import { authApi } from './api/endpoints'
import type { UserOut } from './types'

vi.mock('./components/FooterBar',()=>({default:()=>null}))
vi.mock('./api/endpoints',()=>({authApi:{me:vi.fn()}}))
vi.mock('./pages/PatientListPage',()=>({default:({currentUser}:{currentUser:UserOut})=><div>工作台身份：{currentUser.username}</div>}))
vi.mock('./pages/PatientWorkspacePage',()=>({default:({currentUser}:{currentUser:UserOut})=><div>病例身份：{currentUser.username}</div>}))
const doctor = {id:1,username:'doctor',display_name:'医生',role:'doctor'} as UserOut
const admin = {id:2,username:'admin',display_name:'管理员',role:'admin'} as UserOut
afterEach(()=>{cleanup(); session.clear();session.bind(null);vi.mocked(authApi.me).mockReset()})

it('直接进入病例不被启动身份核验误跳回列表',async()=>{
  session.token='first';vi.mocked(authApi.me).mockResolvedValue(doctor)
  render(<MemoryRouter initialEntries={['/patients/42']}><App /></MemoryRouter>)
  expect(await screen.findByText('病例身份：doctor')).toBeInTheDocument()
})

it('其他标签切换身份立即撤下旧页，核实后加载新身份工作台',async()=>{
  session.token='first';vi.mocked(authApi.me).mockResolvedValueOnce(doctor)
  render(<MemoryRouter><App /></MemoryRouter>)
  await screen.findByText('工作台身份：doctor')
  let finish!: (user:UserOut)=>void
  vi.mocked(authApi.me).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve}))
  act(()=>{window.localStorage.setItem('etmms.token','second');window.dispatchEvent(new StorageEvent('storage',{key:'etmms.token',newValue:'second'}))})
  expect(screen.queryByText('工作台身份：doctor')).not.toBeInTheDocument()
  expect(screen.getByText('正在确认登录状态…')).toBeInTheDocument()
  await act(async()=>{finish(admin)})
  expect(await screen.findByText('工作台身份：admin')).toBeInTheDocument()
})
