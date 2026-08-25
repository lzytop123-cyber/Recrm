import request from './request'

export interface ApprovalRule {
  id: number
  code: string
  name: string
  biz_type: string
  nodes_json: string
  conditions_json?: string | null
  timeout_hours: number
  version: number
  status: string
  remark?: string | null
  created_at: string
  updated_at: string
  published_at?: string | null
}

export interface ApprovalRuleList {
  total: number
  items: ApprovalRule[]
}

export function listApprovalRules(params?: {
  biz_type?: string
  status?: string
  page?: number
  page_size?: number
}) {
  return request.get<ApprovalRuleList>('/approval-rules', { params })
}

export function getApprovalRule(id: number) {
  return request.get<ApprovalRule>(`/approval-rules/${id}`)
}

export function createApprovalRule(data: Partial<ApprovalRule>) {
  return request.post<ApprovalRule>('/approval-rules', data)
}

export function updateApprovalRule(id: number, data: Partial<ApprovalRule>) {
  return request.patch<ApprovalRule>(`/approval-rules/${id}`, data)
}

export function deleteApprovalRule(id: number) {
  return request.delete(`/approval-rules/${id}`)
}

export function publishApprovalRule(id: number) {
  return request.post<ApprovalRule>(`/approval-rules/${id}/publish`)
}

export function disableApprovalRule(id: number) {
  return request.post<ApprovalRule>(`/approval-rules/${id}/disable`)
}
