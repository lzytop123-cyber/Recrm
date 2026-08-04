/**
 * 收款管理 API
 */
import request from './request'

export type PaymentStatus = 'pending' | 'pending_review' | 'confirmed' | 'refunded'
export type PaymentRecordType = 'plan' | 'claim'

export interface Payment {
  id: number
  payment_no?: string | null
  contract_id: number
  record_type?: PaymentRecordType | string
  title?: string | null
  amount: number | string
  due_date?: string | null
  paid_date?: string | null
  status: PaymentStatus | string
  method?: string | null
  payer_name?: string | null
  account_tail?: string | null
  proof_filename?: string | null
  owner_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  confirmed_by?: number | null
  confirmed_at?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  contract_no?: string | null
  contract_title?: string | null
  customer_id?: number | null
  customer_name?: string | null
  owner_name?: string | null
  creator_name?: string | null
  confirmed_by_name?: string | null
  due_status?: string | null
}

export interface PaymentStats {
  total: number
  pending: number
  confirmed: number
  refunded: number
  overdue: number
  pending_amount: number | string
  confirmed_amount: number | string
  mine: number
  pending_review?: number
  pending_review_amount?: number | string
  due_soon_amount?: number | string
  month_contract_amount?: number | string
  collection_rate?: number | string
  forecast_gross_margin?: number | string
}

export const PAYMENT_STATUS_LABEL: Record<string, string> = {
  pending: '待收款',
  pending_review: '待复核',
  confirmed: '已核销',
  refunded: '已退款',
}

export const DUE_STATUS_LABEL: Record<string, string> = {
  pending: '待收款',
  not_due: '未到期',
  due_soon: '即将到期',
  due: '已到期',
  overdue: '逾期',
  settled: '已结清',
  refunded: '已退款',
  pending_review: '待复核',
}

export const PAYMENT_METHOD_OPTIONS = [
  { value: 'bank', label: '银行转账' },
  { value: 'alipay', label: '支付宝' },
  { value: 'wechat', label: '微信' },
  { value: 'cash', label: '现金' },
  { value: 'other', label: '其他' },
]

export function fetchPaymentStats() {
  return request.get<PaymentStats>('/payments/stats')
}

export function fetchPayments(params: {
  status?: string
  due_status?: string
  contract_id?: number
  record_type?: string
  keyword?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Payment[] }>('/payments', { params })
}

export function fetchPaymentDetail(id: number) {
  return request.get<Payment>(`/payments/${id}`)
}

export function createPayment(data: {
  contract_id: number
  title?: string
  amount: number
  due_date?: string
  method?: string
  remark?: string
}) {
  return request.post<Payment>('/payments', data)
}

export function createPaymentClaim(data: {
  contract_id: number
  amount: number
  paid_date: string
  payer_name: string
  account_tail?: string
  proof_filename: string
  remark?: string
}) {
  return request.post<Payment>('/payments/claims', data)
}

export function updatePayment(id: number, data: Partial<Payment>) {
  return request.patch<Payment>(`/payments/${id}`, data)
}

export function confirmPayment(
  id: number,
  data?: { paid_date?: string; method?: string; remark?: string },
) {
  return request.post<Payment>(`/payments/${id}/confirm`, data || {})
}

export function refundPayment(id: number, reason?: string) {
  return request.post<Payment>(`/payments/${id}/refund`, null, { params: { reason } })
}
