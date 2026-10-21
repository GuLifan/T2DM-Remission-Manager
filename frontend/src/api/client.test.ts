import { afterEach, expect, it, vi } from 'vitest'
import { api, session } from './client'

afterEach(() => {session.clear(); session.bind(null); vi.restoreAllMocks()})

it('存储变更事件尚未到达也不能以新token提交旧页请求', async () => {
  session.token = 'old-session'; session.bind('old-session')
  window.localStorage.setItem('etmms.token','new-session')
  const fetcher = vi.spyOn(window,'fetch')
  await expect(api.post('/api/patients/1/reset',{})).rejects.toThrow('登录账号已变化')
  expect(fetcher).not.toHaveBeenCalled()
})

it('旧会话迟到401不能清除后来登录的凭据', async () => {
  session.token = 'old-session'; session.bind('old-session')
  let finish!: (response: Response) => void
  vi.spyOn(window,'fetch').mockImplementation(() => new Promise(resolve => {finish=resolve}))
  const result = api.get('/api/patients')
  session.token = 'new-session'; session.bind('new-session')
  finish(new Response(JSON.stringify({detail:'expired'}),{status:401}))
  await expect(result).rejects.toThrow('已忽略原会话响应')
  expect(session.token).toBe('new-session')
})

it('独立有效身份请求使用自己的凭据并正常返回', async () => {
  session.token = 'verified-session'; session.bind('verified-session')
  const fetcher = vi.spyOn(window,'fetch').mockResolvedValue(new Response('[]',{status:200}))
  expect(await api.get('/api/patients')).toEqual([])
  expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({Authorization:'Bearer verified-session'})
})
