/** 合同应收、收款、核销和退款闭环 API。 */
import request from './request'

export interface Receivable {
  id: number
  contract_id: number
  sequence_no: number
  title: string
  amount: number | string
  due_date: string
  currency: string
  status: string
  allocated_amount: number | string
  outstanding_amount: number | string
  effective_status: string
  contract_no?: string | null
  contract_title?: string | null
  customer_name?: string | null
  owner_name?: string | null
  version: number
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface Receipt {
  id: number
  receipt_no: string
  contract_id: number
  amount: number | string
  paid_date: string
  payer_name: string
  payment_method?: string | null
  bank_reference?: string | null
  proof_filename?: string | null
  status: string
  submitted_by?: number | null
  confirmed_by?: number | null
  confirmed_at?: string | null
  allocated_amount: number | string
  pending_allocation_amount?: number | string
  refunded_amount: number | string
  available_amount: number | string
  contract_no?: string | null
  contract_title?: string | null
  customer_name?: string | null
  submitted_by_name?: string | null
  confirmed_by_name?: string | null
  version: number
  remark?: string | null
  created_at: string
  updated_at: string
}

export interface ReceiptAllocation {
  id: number
  receipt_id: number
  receivable_plan_id: number
  amount: number | string
  status: 'pending' | 'active' | 'rejected' | 'reversed'
  allocated_by?: number | null
  allocated_at: string
  approved_by?: number | null
  approved_at?: string | null
  review_remark?: string | null
  reversed_by?: number | null
  reversed_at?: string | null
  reverse_reason?: string | null
  idempotency_key?: string | null
  version: number
}

export interface Refund {
  id: number
  refund_no: string
  receipt_id: number
  amount: number | string
  reason: string
  review_remark?: string | null
  status: 'pending' | 'confirmed' | 'rejected' | 'cancelled'
  version: number
  created_at: string
  updated_at: string
}

export interface ContractFinancialSummary {
  contract_id: number
  contract_amount: number | string
  receivable_total: number | string
  confirmed_receipt_total: number | string
  refunded_total: number | string
  allocated_total: number | string
  outstanding_receivable: number | string
  unallocated_receipt_balance: number | string
  overdue_receivable: number | string
}

export interface FinanceStats {
  month_contract_amount: number | string
  confirmed_receipt_amount: number | string
  receivable_total: number | string
  outstanding_receivable_amount: number | string
  allocated_amount: number | string
  unallocated_receipt_amount: number | string
  pending_review_count: number
  pending_review_amount: number | string
  overdue_count: number
  overdue_amount: number | string
  collection_rate: number | string
  forecast_gross_margin: number | string
}

export interface FinanceList<T> {
  total: number
  items: T[]
}

export function fetchReceivables(contractId: number) {
  return request.get<Receivable[]>(`/contracts/${contractId}/receivables`)
}

export function fetchReceivableWorkbench(params: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<FinanceList<Receivable>>('/receivables', { params })
}

export function createReceivable(
  contractId: number,
  data: {
    title: string
    amount: number
    due_date: string
    sequence_no?: number
    remark?: string
  },
) {
  return request.post<Receivable>(`/contracts/${contractId}/receivables`, data)
}

export function updateReceivable(
  id: number,
  data: {
    title?: string
    amount?: number
    due_date?: string
    remark?: string
    version: number
  },
) {
  return request.patch<Receivable>(`/receivables/${id}`, data)
}

export function cancelReceivable(id: number, version: number, reason: string) {
  return request.post<Receivable>(`/receivables/${id}/cancel`, { version, reason })
}

export function fetchReceipts(contractId: number) {
  return request.get<FinanceList<Receipt>>('/receipts', {
    params: { contract_id: contractId, page: 1, page_size: 100 },
  })
}

export function fetchReceiptWorkbench(params: {
  status?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<FinanceList<Receipt>>('/receipts', { params })
}

export function createReceipt(data: {
  contract_id: number
  amount: number
  paid_date: string
  payer_name: string
  payment_method?: string
  bank_reference?: string
  proof_filename?: string
  idempotency_key?: string
  remark?: string
}) {
  return request.post<Receipt>('/receipts', data)
}

export function reviewReceipt(id: number, approve: boolean, version: number, remark?: string) {
  return request.post<Receipt>(`/receipts/${id}/${approve ? 'confirm' : 'reject'}`, {
    version,
    remark,
  })
}

export function fetchAllocations(receiptId: number) {
  return request.get<ReceiptAllocation[]>(`/receipts/${receiptId}/allocations`)
}

export function createAllocation(
  receiptId: number,
  data: { receivable_plan_id: number; amount: number; idempotency_key?: string },
) {
  return request.post<ReceiptAllocation>(`/receipts/${receiptId}/allocations`, data)
}

export function reviewAllocation(id: number, approve: boolean, version: number, remark?: string) {
  return request.post<ReceiptAllocation>(`/allocations/${id}/${approve ? 'confirm' : 'reject'}`, {
    version,
    remark,
  })
}

export function reverseAllocation(id: number, version: number, reason: string) {
  return request.post<ReceiptAllocation>(`/allocations/${id}/reverse`, { version, reason })
}

export function fetchRefunds(receiptId: number) {
  return request.get<Refund[]>(`/receipts/${receiptId}/refunds`)
}

export function createRefund(
  receiptId: number,
  data: { amount: number; reason: string; idempotency_key?: string },
) {
  return request.post<Refund>(`/receipts/${receiptId}/refunds`, data)
}

export function reviewRefund(id: number, approve: boolean, version: number, remark?: string) {
  return request.post<Refund>(`/refunds/${id}/${approve ? 'confirm' : 'reject'}`, {
    version,
    remark,
  })
}

export function fetchContractFinancialSummary(contractId: number) {
  return request.get<ContractFinancialSummary>(
    `/contracts/${contractId}/financial-summary`,
  )
}

export function fetchFinanceStats() {
  return request.get<FinanceStats>('/finance/stats')
}
