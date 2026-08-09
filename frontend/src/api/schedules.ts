/**
 * 排期会议 API
 */
import request from './request'

export type ScheduleStatus =
  | 'pending'
  | 'confirmed'
  | 'in_progress'
  | 'completed'
  | 'cancelled'

export type ScheduleResourceType = 'instructor' | 'streamer' | 'shooting_edit' | 'other'
export type ScheduleType = 'internal_training' | 'external_salon' | 'project_live' | 'other'

export interface ScheduleConflict {
  id: number
  title: string
  start_time: string
  end_time: string
  status: string
}

export interface Schedule {
  id: number
  title: string
  schedule_type?: ScheduleType | string
  resource_type: ScheduleResourceType | string
  employee_id: number
  project_id?: number | null
  project_task_id?: number | null
  ticket_id?: number | null
  start_time: string
  end_time: string
  status: ScheduleStatus | string
  creator_id: number
  department_id?: number | null
  confirmed_by?: number | null
  confirmed_at?: string | null
  location?: string | null
  content?: string | null
  coordination_note?: string | null
  result?: string | null
  actual_hours?: number | string | null
  timesheet_id?: number | null
  feishu_sync_status?: string
  cancel_reason?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  employee_name?: string | null
  creator_name?: string | null
  confirmed_by_name?: string | null
  project_name?: string | null
  project_no?: string | null
  task_no?: string | null
  task_title?: string | null
  ticket_no?: string | null
  has_conflict?: boolean
  conflicts?: ScheduleConflict[]
  planned_hours?: number | null
}

export interface ScheduleStats {
  total: number
  pending: number
  confirmed: number
  in_progress: number
  completed: number
  cancelled: number
  conflict_count: number
  mine: number
}

export interface ResourceOption {
  id: number
  name: string
  department_name?: string | null
  job_title?: string | null
  role_names?: string[]
}

export interface PersonTreeNode {
  value: number | string
  label: string
  disabled?: boolean
  is_person?: boolean
  children?: PersonTreeNode[]
}

export interface ResourceLoad {
  employee_id: number
  employee_name: string
  resource_type: string
  planned_hours: number
  load_percent: number
  item_count: number
}

export const SCHEDULE_STATUS_LABEL: Record<string, string> = {
  pending: '待确认',
  confirmed: '已确认',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

export const SCHEDULE_RESOURCE_OPTIONS = [
  { value: 'instructor', label: '讲师' },
  { value: 'streamer', label: '主播' },
  { value: 'shooting_edit', label: '拍摄剪辑' },
  { value: 'other', label: '其他' },
]

export const SCHEDULE_TYPE_OPTIONS = [
  { value: 'internal_training', label: '内部培训' },
  { value: 'external_salon', label: '外部沙龙' },
  { value: 'project_live', label: '项目直播/活动' },
  { value: 'other', label: '其他排期' },
]

export const FEISHU_SYNC_LABEL: Record<string, string> = {
  none: '未同步',
  pending: '待同步',
  synced: '已同步',
  failed: '同步失败',
}

export function fetchScheduleStats() {
  return request.get<ScheduleStats>('/schedules/stats')
}

export function fetchResourceOptions(params?: { resource_type?: string }) {
  return request.get<ResourceOption[]>('/schedules/options/resources', { params })
}

export function fetchPersonTree() {
  return request.get<PersonTreeNode[]>('/schedules/options/person-tree')
}

export function fetchResourceLoad(params: {
  resource_type: string
  date_from: string
  date_to: string
}) {
  return request.get<{ items: ResourceLoad[] }>('/schedules/resource-load', { params })
}

export function fetchSchedules(params: {
  status?: string
  resource_type?: string
  employee_id?: number
  project_id?: number
  project_task_id?: number
  date_from?: string
  date_to?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Schedule[] }>('/schedules', { params })
}

export function fetchScheduleDetail(id: number) {
  return request.get<Schedule>(`/schedules/${id}`)
}

export function createSchedule(data: {
  title: string
  schedule_type?: string
  resource_type?: string
  employee_id: number
  project_id?: number
  project_task_id?: number
  ticket_id?: number
  start_time: string
  end_time: string
  location?: string
  content?: string
  remark?: string
}) {
  return request.post<Schedule>('/schedules', data)
}

export function updateSchedule(id: number, data: Partial<Schedule>) {
  return request.patch<Schedule>(`/schedules/${id}`, data)
}

export function confirmSchedule(id: number) {
  return request.post<Schedule>(`/schedules/${id}/confirm`)
}

export function coordinateSchedule(id: number, note: string) {
  return request.post<Schedule>(`/schedules/${id}/coordinate`, { note })
}

export function startSchedule(id: number) {
  return request.post<Schedule>(`/schedules/${id}/start`)
}

export function completeSchedule(
  id: number,
  data: { result: string; actual_hours: number; create_timesheet?: boolean },
) {
  return request.post<Schedule>(`/schedules/${id}/complete`, data)
}

export function cancelSchedule(id: number, reason?: string) {
  return request.post<Schedule>(`/schedules/${id}/cancel`, { reason })
}
