/**
 * 合同管理 API
 */
import request from './request'

export type ContractStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'signed'
  | 'active'
  | 'completed'
  | 'terminated'

export interface Contract {
  id: number
  contract_no: string
  title: string
  customer_id: number
  contract_type: string
  amount: number | string
  currency: string
  payment_method?: string | null
  status: ContractStatus | string
  signed_date?: string | null
  effective_date?: string | null
  expire_date?: string | null
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  approved_by?: number | null
  approved_at?: string | null
  terminate_reason?: string | null
  remark?: string | null
  proof_filename?: string | null
  proof_path?: string | null
  proof_url?: string | null
  created_at: string
  updated_at: string
  customer_name?: string | null
  owner_name?: string | null
  creator_name?: string | null
  approved_by_name?: string | null
  paid_amount?: number | string | null
  next_due_date?: string | null
  collection_status?: string | null
}

export interface ContractStats {
  total: number
  draft: number
  pending_approval: number
  approved: number
  signed: number
  active: number
  completed: number
  terminated: number
  mine: number
}

export const CONTRACT_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  pending_approval: '待审批',
  approved: '已审批',
  signed: '已签署',
  active: '执行中',
  completed: '已完成',
  terminated: '已终止',
}

export const CONTRACT_TYPE_OPTIONS = [
  { value: 'ai_product', label: 'AI产品销售' },
  { value: 'ai_custom', label: 'AI定制开发' },
  { value: 'media_ops', label: '自媒体代运营' },
  { value: 'other', label: '其他' },
]

export const PAYMENT_METHOD_OPTIONS = [
  { value: 'once', label: '一次性' },
  { value: 'installment', label: '分期' },
  { value: 'milestone', label: '按里程碑' },
]

export function fetchContractStats() {
  return request.get<ContractStats>('/contracts/stats')
}

export function fetchContracts(params: {
  status?: string
  keyword?: string
  customer_id?: number
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Contract[] }>('/contracts', { params })
}

export function fetchContractDetail(id: number) {
  return request.get<Contract>(`/contracts/${id}`)
}

export function createContract(data: Partial<Contract> & { customer_id: number; title: string }) {
  return request.post<Contract>('/contracts', data)
}

export function updateContract(id: number, data: Partial<Contract>) {
  return request.patch<Contract>(`/contracts/${id}`, data)
}

export function submitContract(id: number) {
  return request.post<Contract>(`/contracts/${id}/submit`)
}

export function withdrawContract(id: number) {
  return request.post<Contract>(`/contracts/${id}/withdraw`)
}

export function approveContract(id: number) {
  return request.post<Contract>(`/contracts/${id}/approve`)
}

export function rejectContract(id: number, reason?: string) {
  return request.post<Contract>(`/contracts/${id}/reject`, null, { params: { reason } })
}

export function signContract(
  id: number,
  data?: { signed_date?: string; effective_date?: string; expire_date?: string },
) {
  return request.post<Contract>(`/contracts/${id}/sign`, data || {})
}

export function activateContract(id: number) {
  return request.post<Contract>(`/contracts/${id}/activate`)
}

export function completeContract(id: number) {
  return request.post<Contract>(`/contracts/${id}/complete`, {})
}

export function terminateContract(id: number, reason: string) {
  return request.post<Contract>(`/contracts/${id}/terminate`, { reason })
}
