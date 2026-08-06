/**
 * 审批中心 API
 */
import request from './request'

export interface ApprovalFact {
  label: string
  value: string
}

export interface ApprovalItem {
  id: string
  type: string
  category: string
  source: string
  source_id: string
  title: string
  applicant_name: string
  department_name: string
  submitted_at?: string | null
  status: string
  status_label: string
  node: string
  summary: string
  facts: ApprovalFact[]
  deep_link: string
  can_act: boolean
  actions: string[]
  meta: Record<string, unknown>
}

export interface ApprovalDetail extends ApprovalItem {
  timeline?: Array<{
    name: string
    status: string
    actor_name?: string | null
    acted_at?: string | null
    comment?: string | null
  }>
  nodes?: ApprovalDetail['timeline']
  rule_version?: number | null
}

export interface ApprovalStats {
  pending: number
  initiated: number
  processed: number
  cc: number
}

export function fetchApprovalStats() {
  return request.get<ApprovalStats>('/approvals/stats')
}

export function fetchApprovals(params: {
  tab?: string
  category?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: ApprovalItem[] }>('/approvals', { params })
}

export function fetchApprovalDetail(approvalId: string) {
  return request.get<ApprovalDetail>(`/approvals/${encodeURIComponent(approvalId)}`)
}

export function approveApproval(approvalId: string, payload?: { comment?: string }) {
  return request.post(`/approvals/${encodeURIComponent(approvalId)}/approve`, payload || {})
}

export function rejectApproval(
  approvalId: string,
  payload: { reason?: string; comment?: string },
) {
  return request.post(`/approvals/${encodeURIComponent(approvalId)}/reject`, payload)
}
