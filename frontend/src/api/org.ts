/**
 * 员工管理 / 组织 API
 */
import request from './request'

export interface Department {
  id: number
  name: string
  code?: string | null
  parent_id?: number | null
  description?: string | null
  created_at: string
  updated_at: string
  user_count?: number
  children?: Department[]
}

export interface RoleBrief {
  id: number
  name: string
  code: string
  data_scope: string
}

export interface EmployeeTodo {
  key: string
  label: string
  status: string
  detail?: string | null
}

export interface Employee {
  id: number
  username: string
  real_name?: string | null
  email?: string | null
  phone?: string | null
  job_title?: string | null
  employee_no?: string | null
  department_id?: number | null
  is_active: boolean
  feishu_open_id?: string | null
  feishu_user_id?: string | null
  hire_date?: string | null
  employment_status?: string | null
  manager_id?: number | null
  contract_type?: string | null
  contract_start?: string | null
  contract_end?: string | null
  contract_status?: string | null
  archive_status?: string | null
  created_at: string
  updated_at: string
  department_name?: string | null
  manager_name?: string | null
  feishu_bound?: boolean
  identity_sync?: string
  today_status?: string | null
  todos?: EmployeeTodo[]
  roles: RoleBrief[]
}

export interface OrgStats {
  departments: number
  employees: number
  active_employees: number
  inactive_employees: number
  pending_onboard?: number
  contract_expiring_30d?: number
  today_attendance_ok?: number
  today_attendance_total?: number
}

export interface EmployeeHistory {
  id: number
  event_type: string
  title: string
  detail?: string | null
  occurred_at: string
  created_at: string
}

export interface AttendanceDay {
  work_date: string
  status: string
  first_punch?: string | null
  last_punch?: string | null
  source: string
}

export interface AttendanceSummary {
  month: string
  expected_days: number
  actual_days: number
  leave_days: number
  out_days: number
  exception_pending: number
  today_status?: string | null
  days: AttendanceDay[]
}

export interface FeishuSyncStatus {
  overall_status: string
  overall_label: string
  last_sync_at?: string | null
  items: Array<{
    key: string
    status: string
    last_success_at?: string | null
    last_error?: string | null
  }>
}

export function fetchOrgStats() {
  return request.get<OrgStats>('/org/stats')
}

export function fetchDepartments() {
  return request.get<Department[]>('/org/departments')
}

export function createDepartment(data: {
  name: string
  code?: string
  parent_id?: number
  description?: string
}) {
  return request.post<Department>('/org/departments', data)
}

export function updateDepartment(
  id: number,
  data: Partial<{ name: string; code: string; parent_id: number | null; description: string }>,
) {
  return request.patch<Department>(`/org/departments/${id}`, data)
}

export function deleteDepartment(id: number) {
  return request.delete(`/org/departments/${id}`)
}

export function fetchOrgRoles() {
  return request.get<RoleBrief[]>('/org/roles')
}

export function fetchEmployees(params: {
  keyword?: string
  department_id?: number
  is_active?: boolean
  employment_status?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Employee[] }>('/org/employees', { params })
}

export function fetchEmployee(id: number) {
  return request.get<Employee>(`/org/employees/${id}`)
}

export function fetchEmployeeHistory(id: number) {
  return request.get<EmployeeHistory[]>(`/org/employees/${id}/history`)
}

export function fetchEmployeeAttendance(
  id: number,
  params?: { month?: string; refresh?: boolean },
) {
  return request.get<AttendanceSummary>(`/org/employees/${id}/attendance`, {
    params,
    timeout: 120000,
  })
}

export function createEmployee(data: Record<string, unknown>) {
  return request.post<Employee>('/org/employees', data)
}

export function updateEmployee(id: number, data: Record<string, unknown>) {
  return request.patch<Employee>(`/org/employees/${id}`, data)
}

export function resetEmployeePassword(id: number, password: string) {
  return request.post<Employee>(`/org/employees/${id}/reset-password`, { password })
}

export interface FeishuContactSyncResult {
  departments_created: number
  departments_updated: number
  employees_created: number
  employees_updated: number
  employees_bound: number
  employees_matched?: number
  skipped: number
  warnings: string[]
}

export function syncFeishuContactsApi() {
  return request.post<FeishuContactSyncResult>('/org/feishu/sync', null, { timeout: 180000 })
}

export function syncFeishuAttendanceApi(data?: { user_id?: number; month?: string }) {
  return request.post<{ users_synced: number; days_upserted: number; warnings: string[] }>(
    '/org/feishu/attendance/sync',
    data || {},
    { timeout: 180000 },
  )
}

export function fetchFeishuSyncStatus() {
  return request.get<FeishuSyncStatus>('/org/feishu/sync-status')
}
