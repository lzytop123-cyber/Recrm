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
