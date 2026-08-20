/**
 * 线索池 API
 */
import request from './request'

export type LeadStatus =
  | 'pending_assign'
  | 'assigned'
  | 'following'
  | 'converted'
  | 'returned'
  | 'lost'

export interface Lead {
  id: number
  name: string
  company_name?: string | null
  credit_code?: string | null
  company_domain?: string | null
  phone?: string | null
  email?: string | null
  region?: string | null
  source: string
  source_detail?: string | null
  need_desc?: string | null
  budget?: number | null
  expected_deal_at?: string | null
  business_type?: string | null
  status: LeadStatus | string
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  protect_until?: string | null
  assigned_at?: string | null
  last_followed_at?: string | null
  converted_customer_id?: number | null
  converted_opportunity_id?: number | null
  converted_at?: string | null
  lost_reason?: string | null
  lost_at?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  owner_name?: string | null
  creator_name?: string | null
  is_protected?: boolean
}

export interface LeadFollowUp {
  id: number
  lead_id: number
  user_id: number
  follow_at: string
  method: string
  content: string
  customer_feedback?: string | null
  result: string
  next_follow_at?: string | null
  created_at: string
}

export interface LeadLog {
  id: number
  lead_id: number
  user_id?: number | null
  username?: string | null
  action: string
  detail?: string | null
  created_at: string
}

export interface LeadDetail extends Lead {
  follow_ups: LeadFollowUp[]
  logs: LeadLog[]
}

export interface LeadStats {
  total: number
  pending_assign: number
  assigned: number
  following: number
  converted: number
  returned: number
  lost: number
  public_pool: number
  today_created?: number
  today_assigned?: number
  following_mine?: number
  protect_expiring?: number
  converted_month?: number
  mine?: number
  created?: number
  created_pending_assign?: number
  created_assigned?: number
  created_following?: number
  created_converted?: number
}

export interface LeadQuota {
  daily_claimed: number
  daily_limit: number
  protected_count: number
  protect_limit: number
  protect_days: number
  cooldown_hours: number
  can_claim: boolean
  block_reason?: string | null
}

export const LEAD_STATUS_LABEL: Record<string, string> = {
  pending_assign: '待分配',
  assigned: '已分配',
  following: '跟进中',
  converted: '已转化',
  returned: '已退回',
  lost: '已流失',
}

export const LEAD_SOURCE_OPTIONS = [
  { value: 'manual', label: '手动录入' },
  { value: 'import', label: '批量导入' },
  { value: 'external', label: '外部筛选' },
  { value: 'website', label: '官网' },
  { value: 'ad', label: '广告投放' },
  { value: 'event', label: '展会/活动' },
  { value: 'referral', label: '转介绍' },
  { value: 'im', label: '飞书/企微' },
  { value: 'other', label: '其他' },
]

export const LEAD_RETURN_REASON_OPTIONS = [
  { value: 'no_need', label: '客户无需求' },
  { value: 'unreachable', label: '联系不上' },
  { value: 'competitor', label: '竞品已签约' },
  { value: 'budget', label: '预算不足' },
  { value: 'other', label: '其他' },
]

export function fetchLeadStats() {
  return request.get<LeadStats>('/leads/stats')
}

export function fetchLeadQuota() {
  return request.get<LeadQuota>('/leads/quota')
}

export function checkLeadDuplicates(params: {
  phone?: string
  company_name?: string
  credit_code?: string
  company_domain?: string
}) {
  return request.get<{
    has_duplicate: boolean
    is_hard_duplicate: boolean
    by_phone: Lead[]
    by_company: Lead[]
    by_credit: Lead[]
    by_domain: Lead[]
  }>('/leads/duplicates', { params })
}

export function fetchLeads(params: {
  status?: string
  keyword?: string
  pool?: string
  business_type?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Lead[] }>('/leads', { params })
}

export function fetchLeadDetail(id: number) {
  return request.get<LeadDetail>(`/leads/${id}`)
}

export function createLead(data: Partial<Lead>, force = false) {
  return request.post<Lead>('/leads', data, { params: { force } })
}

export function updateLead(id: number, data: Partial<Lead>) {
  return request.patch<Lead>(`/leads/${id}`, data)
}

export function claimLead(id: number) {
  return request.post<Lead>(`/leads/${id}/claim`)
}

export function assignLead(id: number, owner_id: number, remark?: string) {
  return request.post<Lead>(`/leads/${id}/assign`, { owner_id, remark })
}

export function batchAssignLeads(data: {
  lead_ids: number[]
  owner_ids?: number[]
  method?: 'average' | 'manual'
  assignments?: { lead_id: number; owner_id: number }[]
  reason?: string
}) {
  return request.post<{
    success_count: number
    failed_count: number
    success: { lead_id: number; owner_id?: number; owner_name?: string }[]
    failed: { lead_id: number; reason?: string }[]
  }>('/leads/batch-assign', data)
}

export function transferLead(id: number, owner_id: number, reason?: string) {
  return request.post<Lead>(`/leads/${id}/transfer`, { owner_id, reason })
}

export function returnLead(
  id: number,
  payload?: { reason_type?: string; reason?: string } | string,
) {
  if (typeof payload === 'string' || payload === undefined) {
    return request.post<Lead>(`/leads/${id}/return`, null, {
      params: payload ? { reason: payload } : undefined,
    })
  }
  return request.post<Lead>(`/leads/${id}/return`, payload)
}

export function convertLead(
  id: number,
  data?: {
    customer_name?: string
    remark?: string
    opportunity_title?: string
    opportunity_stage?: string
    expected_amount?: number
    business_type?: string
    requirement_summary?: string
  },
) {
  return request.post<{
    lead: Lead
    customer_id: number
    opportunity_id: number
  }>(`/leads/${id}/convert`, data || {})
}

export function markLeadLost(id: number, reason: string) {
  return request.post<Lead>(`/leads/${id}/lost`, { reason })
}

export function createFollowUp(
  id: number,
  data: {
    method?: string
    content: string
    customer_feedback?: string
    result?: string
    next_follow_at?: string
  },
) {
  return request.post<LeadFollowUp>(`/leads/${id}/follow-ups`, data)
}

export interface LeadImportPreviewRow {
  row_no: number
  company_name: string
  phone: string
  name?: string | null
  credit_code?: string | null
  company_domain?: string | null
  business_type: string
  business_type_label: string
  need_desc?: string | null
  remark?: string | null
  status: 'ok' | 'soft' | 'hard' | 'error' | string
  message: string
  can_import: boolean
  force_required: boolean
}

export interface LeadImportPreview {
  total: number
  ok_count: number
  soft_count: number
  hard_count: number
  error_count: number
  rows: LeadImportPreviewRow[]
}

export interface LeadImportConfirmItem {
  row_no: number
  ok: boolean
  lead_id?: number | null
  message: string
}

export function downloadLeadImportTemplate() {
  return request.get<Blob>('/leads/import/template', { responseType: 'blob' })
}

export function previewLeadImport(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<LeadImportPreview>('/leads/import/preview', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export function confirmLeadImport(data: {
  rows: Array<{
    row_no: number
    company_name: string
    phone: string
    name?: string | null
    credit_code?: string | null
    company_domain?: string | null
    business_type: string
    need_desc?: string | null
    remark?: string | null
    source?: string | null
    force?: boolean
  }>
  self_follow?: boolean | null
}) {
  return request.post<{
    success_count: number
    failed_count: number
    skipped_count: number
    items: LeadImportConfirmItem[]
  }>('/leads/import/confirm', data, { timeout: 120000 })
}
