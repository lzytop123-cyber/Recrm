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
    candidate_names?: string[]
    candidate_count?: number
    role_label?: string | null
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

/** 业务实体 → 进行中审批单 id */
export function resolveOpenApproval(bizType: string, bizId: number) {
  return request.get<{ id: string; biz_type: string }>('/approvals/resolve', {
    params: { biz_type: bizType, biz_id: bizId },
  })
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

export function withdrawApproval(approvalId: string) {
  return request.post(`/approvals/${encodeURIComponent(approvalId)}/withdraw`, {})
}

/** 业务实体维度的审批操作日志（合同/工单/项目/排期详情页嵌用） */
export interface FlowActivityItem {
  id: number
  instance_id: number
  instance_code?: string | null
  rule_code?: string | null
  action: string
  action_label: string
  actor_id?: number | null
  actor_name?: string | null
  detail?: string | null
  created_at: string
}

export function fetchFlowActivity(bizType: string | string[], bizId: number) {
  // 后端接受逗号分隔；避免 axios 默认给数组加 `[]` 后缀（FastAPI 不认）
  const joined = Array.isArray(bizType) ? bizType.join(',') : bizType
  return request.get<{ biz_type: string; biz_id: number; items: FlowActivityItem[] }>(
    '/approvals/flow/activity',
    { params: { biz_type: joined, biz_id: bizId } },
  )
}
