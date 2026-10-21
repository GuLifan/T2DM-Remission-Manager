import { api, newRequestId } from '../../api/client'
import type { ClinicalContext, DataRecord } from './types'

export const clinicalDataApi = {
  context: (pid: number, signal?: AbortSignal) => api.get<ClinicalContext>(`/api/patients/${pid}/clinical-v04/context`, signal),
  detail: (pid: number, eid: number, signal?: AbortSignal) => api.get<{payload: Record<string, unknown>; operator_display_name: string; created_at: string; corrections: DataRecord<Record<string, unknown>>[]}>(`/api/patients/${pid}/clinical-v04/events/${eid}`, signal),
  records: (pid: number, signal?: AbortSignal) => api.get<DataRecord<Record<string, unknown>>[]>(`/api/patients/${pid}/clinical-v04/records`, signal),
  correct: (pid: number, revision: number, record: DataRecord<unknown>, replacement: unknown, reason: string) => api.post(`/api/patients/${pid}/clinical-v04/corrections`, {
    request_id: newRequestId('correction'), expected_revision: revision, input_schema_version: 'v0.4',
    record_id: record.id, kind: record.kind, replacement, reason,
  }),
}
