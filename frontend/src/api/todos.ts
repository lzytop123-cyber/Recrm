/**
 * 我的待办聚合 API
 */
import request from './request'

export type TodoCategory =
  | 'approval'
  | 'ticket'
  | 'lead'
  | 'task'
  | 'schedule'
  | 'resource'

export interface TodoItem {
  id: string
  category: TodoCategory | string
  category_label: string
  title: string
  subtitle?: string
  status_label?: string
  urgency?: 'high' | 'normal' | 'low' | string
  path: string
  due_at?: string | null
}

export interface TodoCounts {
  approval: number
  ticket: number
  lead: number
  task: number
  schedule: number
  resource: number
}

export interface TodoList {
  total: number
  counts: TodoCounts
  items: TodoItem[]
  partial_errors?: string[]
}

export function fetchMyTodos() {
  return request.get<TodoList>('/todos')
}
