/**
 * 系统管理 API
 */
import request from './request'

export interface PermissionItem {
  id: number
  name: string
  code: string
  module?: string | null
  description?: string | null
}

export interface SystemRole {
  id: number
  name: string
  code: string
  description?: string | null
  data_scope: string
  created_at: string
  updated_at: string
  permission_ids: number[]
  permission_codes: string[]
  user_count: number
}

export interface AuditLog {
  id: number
  user_id?: number | null
  username?: string | null
  action: string
  module?: string | null
  target_type?: string | null
  target_id?: string | null
  ip?: string | null
  detail?: string | null
  created_at: string
}

export interface SystemStats {
  roles: number
  permissions: number
  audit_logs: number
  users: number
}

export const DATA_SCOPE_LABEL: Record<string, string> = {
  company: '公司',
  department: '部门',
  personal: '个人',
}

export function fetchSystemStats() {
  return request.get<SystemStats>('/system/stats')
}

export function fetchPermissions() {
  return request.get<PermissionItem[]>('/system/permissions')
}

export function fetchSystemRoles() {
  return request.get<SystemRole[]>('/system/roles')
}

export function createSystemRole(data: {
  name: string
  code: string
  description?: string
  data_scope?: string
  permission_ids?: number[]
}) {
  return request.post<SystemRole>('/system/roles', data)
}

export function updateSystemRole(
  id: number,
  data: Partial<{
    name: string
    description: string
    data_scope: string
    permission_ids: number[]
  }>,
) {
  return request.patch<SystemRole>(`/system/roles/${id}`, data)
}

export function deleteSystemRole(id: number) {
  return request.delete(`/system/roles/${id}`)
}

export function fetchAuditLogs(params: {
  module?: string
  action?: string
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: AuditLog[] }>('/system/audit-logs', { params })
}
