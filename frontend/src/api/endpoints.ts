/**
 * 文件名称：endpoints.ts
 * 所属层级：接口调用层（api）
 * 功能说明：按业务流程分组的类型化接口函数，页面只调用本文件，不直接拼路径。
 *
 * 修改历史：
 *   - 2026-09-20  v1.0  M5 初始实现
 */

import { api, newRequestId } from './client'
import type {
  AssignableDoctor,
  AuthStatusOut,
  BranchOut,
  EventPage,
  EvidenceSearchResult,
  EvidenceStatus,
  FlowUnitOut,
  FullAssessmentResult,
  LoginOut,
  MedicationRestartResult,
  ObservationStatus,
  Patient,
  PatientCreateIn,
  PatientImportOut,
  PhaseReviewResult,
  PostRemissionResult,
  PreAssessmentResult,
  RemissionJudgeResult,
  StateOut,
  TestContextOut,
  UserOut,
  ReferenceData,
} from '../types'

/** 账号相关接口。 */
export const authApi = {
  status: (signal?: AbortSignal) => api.get<AuthStatusOut>('/api/auth/status', signal),
  bootstrap: (payload: { username: string; display_name: string; password: string }) =>
    api.post<LoginOut>('/api/auth/bootstrap', payload),
  login: (payload: { username: string; password: string }) =>
    api.post<LoginOut>('/api/auth/login', payload),
  register: (payload: {
    username: string
    display_name: string
    department: string | null
    password: string
    password_confirm: string
  }) => api.post<{ message: string }>('/api/auth/register', payload),
  logout: () => api.post<void>('/api/auth/logout'),
  me: (signal?: AbortSignal) => api.get<UserOut>('/api/auth/me', signal),
  assignableDoctors: (signal?: AbortSignal) =>
    api.get<AssignableDoctor[]>('/api/auth/assignable-doctors', signal),
}

/** 患者档案相关接口。 */
export const patientApi = {
  list: (signal?: AbortSignal) => api.get<Patient[]>('/api/patients', signal),
  create: (payload: PatientCreateIn) => api.post<Patient>('/api/patients', payload),
  updateProfile: (id: number, payload: PatientCreateIn) =>
    api.put<Patient>(`/api/patients/${id}/profile`, payload),
  importFile: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return api.post<PatientImportOut>('/api/patients/import', body)
  },
  get: (id: number, signal?: AbortSignal) => api.get<Patient>(`/api/patients/${id}`, signal),
  events: (id: number, signal?: AbortSignal) =>
    api.get<EventPage>(`/api/patients/${id}/events?limit=20`, signal),
  reopen: (id: number) => api.post<Patient>(`/api/patients/${id}/reopen`),
  transferOwner: (id: number, ownerId: number) =>
    api.put<Patient>(`/api/patients/${id}/owner`, { owner_id: ownerId }),
}

/** 登录前后均可读取的非敏感参考字典。 */
export const referenceApi = {
  get: (signal?: AbortSignal) => api.get<ReferenceData>('/api/reference', signal),
}

/** 页脚显示实际运行版本，不在前端写死。 */
export const systemApi = {
  health: (signal?: AbortSignal) => api.get<{ status: string; version: string }>('/api/health', signal),
}

/** 领域数据（由后端导出，前端只渲染不硬编码）。 */
export const domainApi = {
  states: (signal?: AbortSignal) => api.get<StateOut[]>('/api/domain/states', signal),
  flowUnits: (signal?: AbortSignal) => api.get<FlowUnitOut[]>('/api/domain/flow-units', signal),
  branches: (signal?: AbortSignal) => api.get<BranchOut[]>('/api/domain/branches', signal),
}

/** 全局只读医学依据；不依赖患者归属，但后端仍要求有效登录。 */
export const evidenceApi = {
  status: (signal?: AbortSignal) => api.get<EvidenceStatus>('/api/evidence/status', signal),
  search: (query: string, limit = 20, signal?: AbortSignal) => {
    const params = new URLSearchParams({ q: query, limit: String(limit) })
    return api.get<EvidenceSearchResult>(`/api/evidence/search?${params.toString()}`, signal)
  },
}

/** 测试支持接口。后端仍会执行测试模式、账号、患者三重守卫。 */
export const testSupportApi = {
  context: (signal?: AbortSignal) => api.get<TestContextOut>('/api/test-context', signal),
  setSimulatedDate: (simulatedDate: string | null) =>
    api.post<TestContextOut>('/api/test-context/simulated-date', {
      simulated_date: simulatedDate,
    }),
  jumpState: (patientId: number, targetState: string) =>
    api.post<Patient>(`/api/patients/${patientId}/debug/jump-state`, {
      target_state: targetState,
      request_id: newRequestId('debug'),
    }),
}

/** 临床流程接口（单元 1–6）。写操作一律带 request_id 以支持幂等。 */
export const flowApi = {
  preAssessment: (patientId: number, payload: Record<string, unknown>) =>
    api.post<PreAssessmentResult>(`/api/patients/${patientId}/pre-assessment`, {
      ...payload,
      request_id: newRequestId('pre'),
    }),
  acuteStabilized: (
    patientId: number,
    payload: { stage_goal: string; interventions: string[] },
  ) =>
    api.post<FullAssessmentResult>(`/api/patients/${patientId}/pre-assessment/acute-stabilized`, {
      ...payload,
      request_id: newRequestId('acute'),
    }),
  closePath: (patientId: number) =>
    api.post<PreAssessmentResult>(`/api/patients/${patientId}/pre-assessment/close-path`),
  fullAssessment: (patientId: number, payload: Record<string, unknown>) =>
    api.post<FullAssessmentResult>(`/api/patients/${patientId}/full-assessment`, {
      ...payload,
      request_id: newRequestId('full'),
    }),
  phaseReview: (patientId: number, payload: Record<string, unknown>) =>
    api.post<PhaseReviewResult>(`/api/patients/${patientId}/phase-review`, {
      ...payload,
      request_id: newRequestId('review'),
    }),
  observation: (patientId: number, signal?: AbortSignal) =>
    api.get<ObservationStatus>(`/api/patients/${patientId}/observation`, signal),
  enterJudge: (patientId: number) =>
    api.post<ObservationStatus>(`/api/patients/${patientId}/observation/enter-judge`),
  medicationRestart: (
    patientId: number,
    payload: { f037_reason: string; target_stage: string },
  ) =>
    api.post<MedicationRestartResult>(`/api/patients/${patientId}/observation/medication-restart`, {
      ...payload,
      request_id: newRequestId('restart'),
    }),
  judgeCheck: (patientId: number, payload: Record<string, unknown>) =>
    api.post<RemissionJudgeResult>(`/api/patients/${patientId}/remission-judge/check`, payload),
  judgeRoute: (patientId: number, payload: Record<string, unknown>) =>
    api.post<RemissionJudgeResult>(`/api/patients/${patientId}/remission-judge/route`, {
      ...payload,
      request_id: newRequestId('judge'),
    }),
  judgeConfirm: (
    patientId: number,
    payload: { f048_confirm: string; f012_pre_tasks?: string | null },
  ) =>
    api.post<RemissionJudgeResult>(`/api/patients/${patientId}/remission-judge/confirm`, {
      ...payload,
      request_id: newRequestId('confirm'),
    }),
  postRemission: (patientId: number, payload: Record<string, unknown>) =>
    api.post<PostRemissionResult>(`/api/patients/${patientId}/post-remission-review`, {
      ...payload,
      request_id: newRequestId('post'),
    }),
}
