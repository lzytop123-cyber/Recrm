/**
 * 客户管理 API
 */
import request from './request'

export type CustomerStatus = 'potential' | 'active' | 'paused' | 'terminated'

export interface Customer {
  id: number
  name: string
  short_name?: string | null
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  industry?: string | null
  company_size?: string | null
  address?: string | null
  source?: string | null
  status: CustomerStatus | string
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  source_lead_id?: number | null
  last_followed_at?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  owner_name?: string | null
  creator_name?: string | null
}

export interface CustomerFollowUp {
  id: number
  customer_id: number
  user_id: number
  follow_at: string
  method: string
  content: string
  next_follow_at?: string | null
  created_at: string
  user_name?: string | null
}

export interface CustomerOpportunityBrief {
  id: number
  opportunity_no: string
  title: string
  stage: string
  expected_amount: number
  owner_name?: string | null
  next_action_at?: string | null
  updated_at: string
}

export type CustomerTimelineSource = 'lead' | 'opportunity' | 'customer'

export interface CustomerTimelineItem {
  key: string
  source: CustomerTimelineSource | string
  occurred_at: string
  title: string
  content: string
  user_name?: string | null
  method?: string | null
  lead_id?: number | null
  opportunity_id?: number | null
  opportunity_title?: string | null
  activity_type?: string | null
  evidence?: string | null
  next_action_at?: string | null
}

export interface CustomerDetail extends Customer {
  follow_ups: CustomerFollowUp[]
  opportunities: CustomerOpportunityBrief[]
  timeline: CustomerTimelineItem[]
  last_activity_at?: string | null
}

export interface CustomerStats {
  total: number
  potential: number
  active: number
  paused: number
  terminated: number
  mine: number
}

export const CUSTOMER_STATUS_LABEL: Record<string, string> = {
  potential: '潜在',
  active: '合作中',
  paused: '暂停',
  terminated: '终止',
}

export const CUSTOMER_SOURCE_OPTIONS = [
  { value: 'manual', label: '手动录入' },
  { value: 'lead_convert', label: '线索转化' },
  { value: 'website', label: '官网' },
  { value: 'referral', label: '转介绍' },
  { value: 'event', label: '展会' },
  { value: 'ad', label: '线上广告' },
  { value: 'other', label: '其他' },
]

export const COMPANY_SIZE_OPTIONS = [
  { value: 'startup', label: '初创' },
  { value: 'sme', label: '中小' },
  { value: 'large', label: '大型' },
  { value: 'group', label: '集团' },
]

export const CUSTOMER_FOLLOW_METHOD_LABEL: Record<string, string> = {
  phone: '电话',
  wechat: '微信',
  email: '邮件',
  meeting: '面谈',
  visit: '拜访',
}

export function fetchCustomerStats() {
  return request.get<CustomerStats>('/customers/stats')
}

export function fetchCustomers(params: {
  status?: string
  keyword?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Customer[] }>('/customers', { params })
}

export function fetchCustomerDetail(id: number) {
  return request.get<CustomerDetail>(`/customers/${id}`)
}

export function createCustomer(data: Partial<Customer>) {
  return request.post<Customer>('/customers', data)
}

export function updateCustomer(id: number, data: Partial<Customer>) {
  return request.patch<Customer>(`/customers/${id}`, data)
}

export function createCustomerFollowUp(
  id: number,
  data: {
    method?: string
    content: string
    next_follow_at?: string
  },
) {
  return request.post<CustomerFollowUp>(`/customers/${id}/follow-ups`, data)
}
