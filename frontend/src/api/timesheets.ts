/**
 * 工时 API
 */
import request from './request'

export type TimesheetStatus = 'draft' | 'submitted' | 'approved' | 'rejected'
export type TimesheetWorkType = 'project' | 'daily' | 'training' | 'leave'

export interface Timesheet {
  id: number
  user_id: number
  work_date: string
  hours: number | string
  work_type: TimesheetWorkType | string
  project_id?: number | null
  content: string
  status: TimesheetStatus | string
  department_id?: number | null
  approver_id?: number | null
  approved_at?: string | null
  reject_reason?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  user_name?: string | null
  project_no?: string | null
  project_name?: string | null
  approver_name?: string | null
  approval_in_center?: boolean
}

export interface TimesheetStats {
  total: number
  draft: number
  submitted: number
  approved: number
  rejected: number
  mine: number
  my_hours: number | string
  approved_hours: number | string
}

export const TIMESHEET_STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  submitted: '待审批',
  approved: '已通过',
  rejected: '已驳回',
}

export const TIMESHEET_TYPE_OPTIONS = [
  { value: 'project', label: '项目工时' },
  { value: 'daily', label: '日常工时' },
  { value: 'training', label: '培训工时' },
  { value: 'leave', label: '请假工时' },
]

export function fetchTimesheetStats() {
  return request.get<TimesheetStats>('/timesheets/stats')
}

export function fetchTimesheets(params: {
  status?: string
  work_type?: string
  project_id?: number
  date_from?: string
  date_to?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Timesheet[] }>('/timesheets', { params })
}

export function fetchTimesheetDetail(id: number) {
  return request.get<Timesheet>(`/timesheets/${id}`)
}

export function createTimesheet(data: {
  work_date: string
  hours: number
  work_type?: string
  project_id?: number
  content: string
  remark?: string
}) {
  return request.post<Timesheet>('/timesheets', data)
}

export function updateTimesheet(id: number, data: Partial<Timesheet>) {
  return request.patch<Timesheet>(`/timesheets/${id}`, data)
}

export function submitTimesheet(id: number) {
  return request.post<Timesheet>(`/timesheets/${id}/submit`)
}

export function approveTimesheet(id: number) {
  return request.post<Timesheet>(`/timesheets/${id}/approve`)
}

export function rejectTimesheet(id: number, reason: string) {
  return request.post<Timesheet>(`/timesheets/${id}/reject`, { reason })
}
