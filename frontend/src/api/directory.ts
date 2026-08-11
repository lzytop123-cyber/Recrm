/**
 * 公共目录：业务选人/选部门/挂接项目（登录即可）
 * 不要求 org:view / project:view，不会打开员工管理或项目管理侧栏
 */
import request from './request'

export interface DirectoryDepartment {
  id: number
  name: string
  code?: string | null
  parent_id?: number | null
  children?: DirectoryDepartment[]
}

export interface DirectoryPerson {
  id: number
  username: string
  real_name?: string | null
  job_title?: string | null
  department_id?: number | null
  department_name?: string | null
  is_active: boolean
}

export interface DirectoryProject {
  id: number
  name: string
  project_no: string
  status: string
}

export interface DirectoryProjectTask {
  id: number
  project_id: number
  title: string
  status: string
}

export interface DirectoryCustomer {
  id: number
  name: string
}

export interface DirectoryContract {
  id: number
  contract_no: string
  title: string
  status: string
  customer_name?: string | null
}

export function fetchDirectoryDepartments() {
  return request.get<DirectoryDepartment[]>('/directory/departments')
}

export function fetchDirectoryPeople(params?: {
  keyword?: string
  department_id?: number
  is_active?: boolean
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: DirectoryPerson[] }>('/directory/people', {
    params,
  })
}

export function fetchDirectoryProjects(params?: {
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: DirectoryProject[] }>('/directory/projects', {
    params,
  })
}

export function fetchDirectoryProjectTasks(params: {
  project_id: number
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: DirectoryProjectTask[] }>(
    '/directory/project-tasks',
    { params },
  )
}

export function fetchDirectoryCustomers(params?: {
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: DirectoryCustomer[] }>('/directory/customers', {
    params,
  })
}

export function fetchDirectoryContracts(params?: {
  keyword?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: DirectoryContract[] }>('/directory/contracts', {
    params,
  })
}
