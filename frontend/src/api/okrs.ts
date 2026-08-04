/**
 * OKR API
 */
import request from './request'

export type OkrStatus = 'pending' | 'active' | 'completed' | 'adjusted' | 'terminated'
export type OkrLevel = 'company' | 'department' | 'personal'

export interface KeyResult {
  id: number
  okr_id: number
  title: string
  target_value: number | string
  current_value: number | string
  unit?: string | null
  weight: number
  sort_order: number
  remark?: string | null
  created_at: string
  updated_at: string
  progress?: number
}

export interface Okr {
  id: number
  title: string
  level: OkrLevel | string
  period_type: string
  period_label: string
  status: OkrStatus | string
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  parent_id?: number | null
  progress: number
  description?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  owner_name?: string | null
  creator_name?: string | null
  parent_title?: string | null
  kr_count?: number
}

export interface OkrDetail extends Okr {
  key_results: KeyResult[]
}

export interface OkrStats {
  total: number
  pending: number
  active: number
  completed: number
  terminated: number
  mine: number
  avg_progress?: number
  unaligned?: number
  company_count?: number
  department_count?: number
  personal_count?: number
  risk_count?: number
}

export const OKR_STATUS_LABEL: Record<string, string> = {
  pending: '待确认',
  active: '进行中',
  completed: '已完成',
  adjusted: '已调整',
  terminated: '已终止',
}

export const OKR_LEVEL_OPTIONS = [
  { value: 'company', label: '公司级' },
  { value: 'department', label: '部门级' },
  { value: 'personal', label: '个人级' },
]

export const OKR_PERIOD_OPTIONS = [
  { value: 'yearly', label: '年度' },
  { value: 'quarterly', label: '季度' },
  { value: 'monthly', label: '月度' },
]

export function fetchOkrStats(period_label?: string) {
  return request.get<OkrStats>('/okrs/stats', {
    params: period_label ? { period_label } : undefined,
  })
}

export function fetchOkrs(params: {
  status?: string
  level?: string
  period_label?: string
  keyword?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Okr[] }>('/okrs', { params })
}

export function fetchOkrDetail(id: number) {
  return request.get<OkrDetail>(`/okrs/${id}`)
}

export function createOkr(data: {
  title: string
  level?: string
  period_type?: string
  period_label: string
  description?: string
  parent_id?: number
  remark?: string
  key_results?: Array<{
    title: string
    target_value?: number
    current_value?: number
    unit?: string
    weight?: number
  }>
}) {
  return request.post<Okr>('/okrs', data)
}

export function updateOkr(id: number, data: Partial<Okr>) {
  return request.patch<Okr>(`/okrs/${id}`, data)
}

export function confirmOkr(id: number) {
  return request.post<Okr>(`/okrs/${id}/confirm`)
}

export function completeOkr(id: number) {
  return request.post<Okr>(`/okrs/${id}/complete`)
}

export function terminateOkr(id: number, reason?: string) {
  return request.post<Okr>(`/okrs/${id}/terminate`, null, { params: { reason } })
}

export function addKeyResult(
  okrId: number,
  data: {
    title: string
    target_value?: number
    current_value?: number
    unit?: string
    weight?: number
  },
) {
  return request.post<KeyResult>(`/okrs/${okrId}/key-results`, data)
}

export function updateKeyResult(okrId: number, krId: number, data: Partial<KeyResult>) {
  return request.patch<KeyResult>(`/okrs/${okrId}/key-results/${krId}`, data)
}
