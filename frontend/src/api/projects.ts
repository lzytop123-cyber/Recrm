/**
 * 项目交付 API
 */
import request from './request'

export type ProjectStatus =
  | 'initiating'
  | 'planning'
  | 'executing'
  | 'accepting'
  | 'accepted'
  | 'completed'
  | 'terminated'

export interface ProjectMilestone {
  id: number
  project_id: number
  name: string
  start_date?: string | null
  deadline?: string | null
  actual_date?: string | null
  role?: string | null
  deliverable?: string | null
  evidence?: string | null
  evidence_link?: string | null
  evidence_attachment?: string | null
  evidence_attachment_path?: string | null
  evidence_status?: string | null
  evidence_confirmed_by?: number | null
  evidence_confirmed_at?: string | null
  evidence_reject_reason?: string | null
  evidence_confirmed_by_name?: string | null
  status: string
  sort_order: number
  remark?: string | null
  created_at: string
  updated_at: string
  task_total?: number
  task_done?: number
  can_complete?: boolean
  next_action?: string | null
}

export interface Project {
  id: number
  project_no: string
  name: string
  contract_id?: number | null
  customer_id?: number | null
  project_type: string
  status: ProjectStatus | string
  progress: number
  manager_id?: number | null
  creator_id?: number | null
  department_id?: number | null
  start_date?: string | null
  end_date?: string | null
  actual_end_date?: string | null
  scope_desc?: string | null
  terminate_reason?: string | null
  remark?: string | null
  payment_verified?: boolean
  payment_deferred?: boolean
  payment_deferred_reason?: string | null
  payment_defer_status?: 'none' | 'pending' | 'approved' | 'rejected' | string
  payment_defer_submitted_by?: number | null
  payment_defer_submitted_at?: string | null
  payment_defer_approved_by?: number | null
  payment_defer_approved_at?: string | null
  payment_defer_reject_reason?: string | null
  handoff_complete?: boolean
  contact_confirmed?: boolean
  business_owner_id?: number | null
  baseline_version?: string | null
  acceptance_result?: string | null
  accepted_at?: string | null
  acceptance_method?: string | null
  acceptance_owner_id?: number | null
  acceptance_conclusion?: string | null
  leftover_summary?: string | null
  acceptance_approval_status?: string | null
  acceptance_submitted_by?: number | null
  acceptance_submitted_at?: string | null
  acceptance_approved_by?: number | null
  acceptance_approved_at?: string | null
  acceptance_reject_reason?: string | null
  acceptance_attachment?: string | null
  acceptance_attachment_path?: string | null
  finance_check_passed?: boolean
  finance_check_status?: string | null
  finance_check_submitted_by?: number | null
  finance_check_submitted_at?: string | null
  finance_check_approved_by?: number | null
  finance_check_approved_at?: string | null
  finance_check_reject_reason?: string | null
  contract_amount?: number | string
  contract_paid_amount?: number | string
  contract_collection_complete?: boolean
  leftover_closed?: boolean
  created_at: string
  updated_at: string
  contract_no?: string | null
  contract_title?: string | null
  customer_name?: string | null
  manager_name?: string | null
  creator_name?: string | null
  business_owner_name?: string | null
  acceptance_owner_name?: string | null
  acceptance_submitted_by_name?: string | null
  acceptance_approved_by_name?: string | null
  contract_active_ok?: boolean
  payment_received_ok?: boolean
  health?: string | null
  next_node?: string | null
  milestone_done?: number
  milestone_total?: number
}

export interface ProjectDetail extends Project {
  milestones: ProjectMilestone[]
}

export interface ProjectStats {
  total: number
  initiating: number
  planning: number
  executing: number
  accepting: number
  accepted: number
  completed: number
  terminated: number
  mine: number
  high_risk?: number
  leftover?: number
}

export interface ProjectTask {
  id: number
  task_no: string
  project_id: number
  milestone_id?: number | null
  title: string
  criteria?: string | null
  assignee_id?: number | null
  department_id?: number | null
  start_date?: string | null
  due_date?: string | null
  planned_hours?: number | string | null
  actual_hours?: number | string | null
  status: string
  ticket_id?: number | null
  remark?: string | null
  creator_id?: number | null
  created_at: string
  updated_at: string
  project_no?: string | null
  project_name?: string | null
  milestone_name?: string | null
  assignee_name?: string | null
  department_name?: string | null
  ticket_no?: string | null
  due_status?: string | null
  schedule_booked?: number
  schedule_completed?: number
}

export interface ProjectTaskStats {
  mine: number
  overdue: number
  planned_hours: number | string
  actual_hours: number | string
  linked_tickets: number
}

export interface DepartmentMonitorMember {
  user_id: number
  name: string
  planned_tasks: number
  done_tasks: number
  overdue_tasks: number
  planned_hours: number | string
  actual_hours: number | string
  hours_complete_rate: number | string
  open_tickets: number
}

export interface DepartmentMonitor {
  department_id?: number | null
  department_name?: string | null
  health_score: number
  on_time_rate: number | string
  hours_complete_rate: number | string
  overdue_tasks: number
  missing_hours: number
  members: DepartmentMonitorMember[]
}

export const PROJECT_STATUS_LABEL: Record<string, string> = {
  initiating: '立项',
  planning: '计划中',
  executing: '执行中',
  accepting: '验收中',
  accepted: '已验收',
  completed: '已完成',
  terminated: '已终止',
}

export const PROJECT_TYPE_OPTIONS = [
  { value: 'ai_product', label: 'AI产品销售' },
  { value: 'ai_custom', label: 'AI定制开发' },
  { value: 'media_ops', label: '自媒体代运营' },
  { value: 'other', label: '其他' },
]

// 兼容旧引用：优先使用 @/api/dictionaries 的 useBusinessTypes
export { DEFAULT_BUSINESS_TYPE_OPTIONS, useBusinessTypes, businessTypeLabel } from './dictionaries'

export const MILESTONE_STATUS_LABEL: Record<string, string> = {
  pending: '未开始',
  doing: '进行中',
  done: '已完成',
}

export const TASK_STATUS_LABEL: Record<string, string> = {
  pending: '待排期',
  doing: '进行中',
  done: '已完成',
}

export const HEALTH_LABEL: Record<string, string> = {
  normal: '正常',
  attention: '需关注',
  risk: '高风险',
}

export const ACCEPTANCE_RESULT_LABEL: Record<string, string> = {
  pass: '通过',
  conditional: '有条件通过',
  fail: '不通过',
}

export function fetchProjectStats() {
  return request.get<ProjectStats>('/projects/stats')
}

export function fetchProjects(params: {
  status?: string
  keyword?: string
  contract_id?: number
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: Project[] }>('/projects', { params })
}

export function fetchProjectDetail(id: number) {
  return request.get<ProjectDetail>(`/projects/${id}`)
}

export function createProject(data: Record<string, unknown> & { name: string }) {
  return request.post<Project>('/projects', data)
}

export function updateProject(id: number, data: Partial<Project>) {
  return request.patch<Project>(`/projects/${id}`, data)
}

export function startProjectPlanning(id: number) {
  return request.post<Project>(`/projects/${id}/plan`)
}

export function startProjectExecuting(id: number) {
  return request.post<Project>(`/projects/${id}/execute`)
}

export function startProjectAccepting(id: number) {
  return request.post<Project>(`/projects/${id}/accepting`)
}

export function acceptProject(
  id: number,
  data: {
    result: string
    accepted_at?: string
    method: string
    owner_id?: number
    conclusion: string
    leftover_summary?: string
    attachment: string
    attachment_path?: string
  },
) {
  return request.post<Project>(`/projects/${id}/accept`, data)
}

export function reviewProjectAcceptance(id: number, approve: boolean, remark?: string) {
  return request.post<Project>(
    `/projects/${id}/acceptance/${approve ? 'confirm' : 'reject'}`,
    { remark },
  )
}

export function setProjectFinanceCheck(id: number, remark?: string) {
  return request.post<Project>(`/projects/${id}/finance-check`, { remark })
}

export function reviewProjectFinanceCheck(id: number, approve: boolean, remark?: string) {
  return request.post<Project>(
    `/projects/${id}/finance-check/${approve ? 'confirm' : 'reject'}`,
    { remark },
  )
}

export function setProjectLeftoverClosed(id: number, closed = true) {
  return request.post<Project>(`/projects/${id}/leftover-close`, { closed })
}

export function completeProject(id: number) {
  return request.post<Project>(`/projects/${id}/complete`)
}

export function terminateProject(id: number, reason: string) {
  return request.post<Project>(`/projects/${id}/terminate`, { reason })
}

export function addMilestone(
  projectId: number,
  data: {
    name: string
    start_date?: string
    deadline?: string
    actual_date?: string
    role?: string
    deliverable?: string
    evidence?: string
    sort_order?: number
    remark?: string
  },
) {
  return request.post<ProjectMilestone>(`/projects/${projectId}/milestones`, data)
}

export function updateMilestone(
  projectId: number,
  milestoneId: number,
  data: Partial<ProjectMilestone>,
) {
  return request.patch<ProjectMilestone>(`/projects/${projectId}/milestones/${milestoneId}`, data)
}

export function deleteMilestone(projectId: number, milestoneId: number) {
  return request.delete<void>(`/projects/${projectId}/milestones/${milestoneId}`)
}

export function reviewMilestoneEvidence(
  projectId: number,
  milestoneId: number,
  data: { action: 'confirm' | 'reject'; reason?: string },
) {
  return request.post<ProjectMilestone>(
    `/projects/${projectId}/milestones/${milestoneId}/evidence-review`,
    data,
  )
}

export function fetchProjectTasks(params: {
  project_id?: number
  status?: string
  keyword?: string
  scope?: string
  page?: number
  page_size?: number
}) {
  return request.get<{ total: number; items: ProjectTask[] }>('/projects/tasks', { params })
}

export function fetchProjectTaskStats() {
  return request.get<ProjectTaskStats>('/projects/tasks/stats')
}

export function fetchDepartmentMonitor() {
  return request.get<DepartmentMonitor>('/projects/department-monitor')
}

export type ResourceNeedStatus = 'pending' | 'accepted' | 'rejected'
export type ScheduleCheckStatus = 'pending' | 'clear' | 'conflict'

export interface ProjectResourceNeed {
  id: number
  project_id: number
  project_no?: string | null
  project_name?: string | null
  role_name: string
  department_name: string
  department_id?: number | null
  suggested_user_id?: number | null
  suggested_user_name?: string | null
  confirmed_user_id?: number | null
  confirmed_user_name?: string | null
  planned_hours: number | string
  status: ResourceNeedStatus | string
  schedule_status: ScheduleCheckStatus | string
  note?: string | null
  handler_role?: string | null
  confirmed_by?: number | null
  confirmed_by_name?: string | null
  confirmed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ResourceRoleMember {
  id: number
  name: string
  department_name?: string | null
  job_title?: string | null
}

export interface ResourceRoleOption {
  role_name: string
  department_id?: number | null
  member_count: number
  members: ResourceRoleMember[]
}

export interface ResourceRoleOptions {
  roles: ResourceRoleOption[]
  employees: ResourceRoleMember[]
  source: string
  hint?: string | null
}

export interface ResourceRoleAssignment {
  role_name: string
  suggested_user_id?: number | null
  planned_hours?: number | null
}

export interface ProjectHoursBudget {
  project_id: number
  resource_budget_hours: number | string
  resource_accepted_hours: number | string
  task_planned_hours: number | string
  task_actual_hours: number | string
  remaining_hours: number | string
  over_budget: boolean
}

export function fetchResourceRoleOptions() {
  return request.get<ResourceRoleOptions>('/projects/resource-role-options')
}

export function fetchProjectResourceNeeds(params?: { only_pending?: boolean }) {
  return request.get<{ items: ProjectResourceNeed[]; total: number; pending_count: number }>(
    '/projects/resource-needs',
    { params },
  )
}

export function confirmProjectResource(
  id: number,
  data: {
    action: 'accept' | 'adjust' | 'reject'
    confirmed_user_id?: number
    planned_hours?: number
    note?: string
  },
) {
  return request.post<ProjectResourceNeed>(`/projects/resource-needs/${id}/confirm`, data)
}

export function fetchProjectHoursBudget(projectId: number) {
  return request.get<ProjectHoursBudget>(`/projects/${projectId}/hours-budget`)
}

export function createProjectTask(data: {
  project_id: number
  title: string
  criteria?: string
  milestone_id?: number
  assignee_id?: number
  start_date?: string
  due_date?: string
  planned_hours?: number
  remark?: string
}) {
  return request.post<ProjectTask>('/projects/tasks', data)
}

export function updateProjectTask(id: number, data: Partial<ProjectTask>) {
  return request.patch<ProjectTask>(`/projects/tasks/${id}`, data)
}
