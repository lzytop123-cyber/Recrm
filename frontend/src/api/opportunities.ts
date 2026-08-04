import request from './request'

export type OpportunityStage =
  | 'contact'
  | 'need_confirm'
  | 'proposal'
  | 'negotiation'
  | 'won'
  | 'lost'
  | 'paused'

export interface Opportunity {
  id: number
  opportunity_no: string
  title: string
  customer_id: number
  source_lead_id?: number | null
  business_type: string
  stage: OpportunityStage | string
  expected_amount: number | string
  currency: string
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  requirement_summary?: string | null
  next_action_at?: string | null
  next_action_note?: string | null
  lost_reason?: string | null
  won_at?: string | null
  lost_at?: string | null
  closed_at?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  owner_name?: string | null
  creator_name?: string | null
  customer_name?: string | null
}

export interface OpportunityActivity {
  id: number
  opportunity_id: number
  user_id?: number | null
  activity_type: string
  content?: string | null
  evidence?: string | null
  from_stage?: string | null
  to_stage?: string | null
  next_action_at?: string | null
  created_at: string
  user_name?: string | null
}

export interface OpportunityDetail extends Opportunity {
  activities: OpportunityActivity[]
  linked_contract_id?: number | null
  linked_contract_no?: string | null
  linked_contract_status?: string | null
}

export interface OpportunityStats {
  total: number
  open_count: number
  open_amount?: number | string
  won: number
  lost: number
  negotiation: number
  overdue_actions?: number
  pending_contract?: number
  customer_count?: number
  won_amount?: number | string
}

export const OPP_STAGE_LABEL: Record<string, string> = {
  contact: '初步接触',
  need_confirm: '需求确认',
  proposal: '方案报价',
  negotiation: '商务谈判',
  won: '赢单',
  lost: '输单',
  paused: '暂停',
}

export const BUSINESS_TYPE_OPTIONS = [
  { value: 'ai_product', label: 'AI产品销售' },
  { value: 'ai_custom', label: 'AI定制开发' },
  { value: 'media_ops', label: '自媒体代运营' },
  { value: 'other', label: '其他' },
]

export function fetchOpportunityStats() {
  return request.get<OpportunityStats>('/opportunities/stats')
}

export function fetchOpportunities(params: {
  stage?: string
  keyword?: string
  customer_id?: number
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Opportunity[] }>('/opportunities', { params })
}

export function fetchOpportunityDetail(id: number) {
  return request.get<OpportunityDetail>(`/opportunities/${id}`)
}

export function createOpportunity(data: {
  title: string
  customer_id: number
  business_type?: string
  stage?: string
  expected_amount?: number
  requirement_summary: string
  remark?: string
  source_lead_id?: number
}) {
  return request.post<Opportunity>('/opportunities', data)
}

export function updateOpportunity(
  id: number,
  data: Partial<{
    title: string
    business_type: string
    expected_amount: number
    requirement_summary: string
    next_action_note: string
    remark: string
  }>,
) {
  return request.patch<Opportunity>(`/opportunities/${id}`, data)
}

export function changeOpportunityStage(
  id: number,
  data: { stage: string; evidence: string; lost_reason?: string },
) {
  return request.post<Opportunity>(`/opportunities/${id}/stage`, data)
}

export function createOpportunityActivity(
  id: number,
  data: {
    content: string
    evidence?: string
    next_action_at?: string
    next_action_note?: string
  },
) {
  return request.post<OpportunityActivity>(`/opportunities/${id}/activities`, data)
}

export function draftContractFromOpportunity(id: number) {
  return request.post(`/opportunities/${id}/draft-contract`)
}
