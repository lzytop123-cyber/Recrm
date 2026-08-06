/**
 * 协作工单 API
 */
import request from './request'

export type TicketStatus =
  | 'pending_assign'
  | 'pending_accept'
  | 'processing'
  | 'pending_confirm'
  | 'completed'
  | 'closed'

export type TicketType = 'collaboration' | 'feedback' | 'service' | 'urgent'
export type TicketPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface TicketRecord {
  id: number
  ticket_id: number
  user_id: number
  action: string
  content?: string | null
  created_at: string
  user_name?: string | null
}

export interface Ticket {
  id: number
  ticket_no: string
  title: string
  ticket_type: TicketType | string
  priority: TicketPriority | string
  status: TicketStatus | string
  content: string
  creator_id: number
  assignee_id?: number | null
  department_id?: number | null
  project_id?: number | null
  task_id?: number | null
  due_at?: string | null
  accepted_at?: string | null
  completed_at?: string | null
  closed_at?: string | null
  result?: string | null
  remark?: string | null
  satisfaction?: number | null
  satisfaction_comment?: string | null
  sla_remind_level?: number
  escalated_level?: number
  sla_paused_at?: string | null
  created_at: string
  updated_at: string
  creator_name?: string | null
  assignee_name?: string | null
  department_name?: string | null
  project_name?: string | null
  task_no?: string | null
  task_title?: string | null
  is_overdue?: boolean
  is_near_sla?: boolean
  sla_used_ratio?: number | null
  can_reopen?: boolean
  can_assign?: boolean
  can_accept?: boolean
  can_transfer?: boolean
  can_complete?: boolean
  can_confirm?: boolean
  can_return?: boolean
  next_actor_hint?: string | null
  records?: TicketRecord[]
}

export interface TicketStats {
  total: number
  pending_assign: number
  pending_accept: number
  processing: number
  pending_confirm: number
  completed: number
  closed: number
  overdue: number
  near_sla: number
  mine_created: number
  mine_assigned: number
  satisfaction_avg?: number | null
  escalated?: number
}

export interface AssigneeOption {
  id: number
  name: string
}

export const TICKET_STATUS_LABEL: Record<string, string> = {
  pending_assign: '待分派',
  pending_accept: '待接收',
  processing: '处理中',
  pending_confirm: '待确认',
  completed: '已完成',
  closed: '已关闭',
}

export const TICKET_TYPE_OPTIONS = [
  { value: 'service', label: '交付协作工单' },
  { value: 'collaboration', label: '普通跨部门协作' },
  { value: 'urgent', label: '紧急客户或生产问题' },
  { value: 'feedback', label: '反馈工单' },
]

export const TICKET_PRIORITY_OPTIONS = [
  { value: 'low', label: '低' },
  { value: 'normal', label: '中' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' },
]

export const TICKET_ACTION_LABEL: Record<string, string> = {
  create: '创建',
  assign: '分派',
  accept: '受理',
  transfer: '转派',
  comment: '评论',
  complete: '完成',
  confirm: '确认',
  close: '关闭',
  rate: '评价',
  return: '退回',
  reopen: '重开',
  update: '更新',
  link_task: '关联任务',
  remind_50: 'SLA 50%提醒',
  remind_80: 'SLA 80%提醒',
  escalate_l1: '超时升级L1',
  escalate_l2: '超时升级L2',
}

export function fetchTicketStats() {
  return request.get<TicketStats>('/tickets/stats')
}

export function scanTicketSla() {
  return request.post<{
    scanned: number
    reminded_50: number
    reminded_80: number
    escalated_l1: number
    escalated_l2: number
  }>('/tickets/sla/scan')
}

export function fetchAssigneeOptions() {
  return request.get<AssigneeOption[]>('/tickets/options/assignees')
}

export function fetchTickets(params: {
  status?: string
  ticket_type?: string
  priority?: string
  keyword?: string
  project_id?: number
  department_id?: number
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Ticket[] }>('/tickets', { params })
}

export function fetchTicketDetail(id: number) {
  return request.get<Ticket>(`/tickets/${id}`)
}

export function createTicket(data: {
  title: string
  ticket_type?: string
  priority?: string
  content: string
  assignee_id?: number
  department_id?: number
  project_id?: number
  task_id?: number
  remark?: string
}) {
  return request.post<Ticket>('/tickets', data)
}

export function updateTicket(id: number, data: Partial<Ticket>) {
  return request.patch<Ticket>(`/tickets/${id}`, data)
}

export function assignTicket(id: number, assignee_id: number, remark?: string) {
  return request.post<Ticket>(`/tickets/${id}/assign`, { assignee_id, remark })
}

export function acceptTicket(id: number) {
  return request.post<Ticket>(`/tickets/${id}/accept`)
}

export function transferTicket(id: number, assignee_id: number, reason?: string) {
  return request.post<Ticket>(`/tickets/${id}/transfer`, { assignee_id, reason })
}

export function completeTicket(id: number, result: string) {
  return request.post<Ticket>(`/tickets/${id}/complete`, { result })
}

export function returnTicket(id: number, reason: string) {
  return request.post<Ticket>(`/tickets/${id}/return`, { reason })
}

export function confirmTicket(
  id: number,
  data: { satisfaction: number; comment?: string; close?: boolean },
) {
  return request.post<Ticket>(`/tickets/${id}/confirm`, data)
}

export function closeTicket(
  id: number,
  data: { satisfaction?: number; comment?: string },
) {
  return request.post<Ticket>(`/tickets/${id}/close`, data)
}

export function reopenTicket(id: number, reason: string) {
  return request.post<Ticket>(`/tickets/${id}/reopen`, { reason })
}

export function commentTicket(id: number, content: string) {
  return request.post<Ticket>(`/tickets/${id}/comments`, { content })
}
