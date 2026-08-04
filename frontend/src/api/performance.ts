/**
 * 目标绩效（考核 / 校准 / 工资批次）API
 */
import request from './request'

export interface PerformanceCycle {
  id: number
  period_label: string
  rule_version: string
  status: string
  calibration_started: boolean
  locked: boolean
  locked_at?: string | null
  payroll_batch_no?: string | null
  payroll_created: boolean
  payroll_reviewed: boolean
  payroll_published: boolean
  remark?: string | null
  created_at: string
  updated_at: string
  pending_manager: number
  pending_self?: number
  pending_appeals: number
  completed_count: number
  total_assessments: number
}

export interface Assessment {
  id: number
  cycle_id: number
  user_id: number
  department_id?: number | null
  self_score?: number | null
  okr_score?: number | null
  kpi_score?: number | null
  behavior_score?: number | null
  manager_score?: number | null
  final_score?: number | null
  grade?: string | null
  coefficient?: number | string | null
  evidence_status: string
  status: string
  manager_comment?: string | null
  bonus_amount?: number | string | null
  created_at: string
  updated_at: string
  user_name?: string | null
  department_name?: string | null
  suggested_okr_score?: number | null
  suggested_okr_count?: number
  suggested_okr_period?: string | null
}

export interface Appeal {
  id: number
  assessment_id: number
  reason: string
  request_score: number
  status: string
  resolution?: string | null
  resolved_by?: number | null
  resolved_at?: string | null
  created_at: string
  updated_at: string
  user_name?: string | null
  department_name?: string | null
  current_score?: number | null
}

export interface PerformanceWorkbench {
  cycle: PerformanceCycle
  assessments: Assessment[]
  appeals: Appeal[]
  grade_distribution: {
    'A+_A': number
    B: number
    C_D: number
  }
}

export const ASSESS_STATUS_LABEL: Record<string, string> = {
  pending_self: '待自评',
  pending_manager: '待主管评价',
  pending_calibration: '待校准',
  appealing: '申诉中',
  completed: '已完成',
}

export const APPEAL_STATUS_LABEL: Record<string, string> = {
  pending: '待处理',
  approved: '已通过',
  rejected: '已驳回',
}

export function fetchPerformanceWorkbench(period_label = '2026-07') {
  return request.get<PerformanceWorkbench>('/performance/workbench', {
    params: { period_label },
  })
}

export function rateManager(
  assessmentId: number,
  data: {
    okr_score: number
    kpi_score: number
    behavior_score: number
    comment: string
  },
) {
  return request.post<Assessment>(`/performance/assessments/${assessmentId}/manager-rate`, data)
}

export function rateSelf(assessmentId: number, data: { self_score: number }) {
  return request.post<Assessment>(`/performance/assessments/${assessmentId}/self-rate`, data)
}

export function createAppeal(
  assessmentId: number,
  data: { reason: string; request_score: number },
) {
  return request.post<Appeal>(`/performance/assessments/${assessmentId}/appeals`, data)
}

export function resolveAppeal(
  appealId: number,
  data: { approve: boolean; resolution: string; final_score?: number },
) {
  return request.post<Appeal>(`/performance/appeals/${appealId}/resolve`, data)
}

export function startCalibration(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/calibrate', null, {
    params: { period_label },
  })
}

export function lockCycle(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/lock', null, {
    params: { period_label },
  })
}

export function resetCycle(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/reset', null, {
    params: { period_label },
  })
}

export function generatePayroll(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/payroll/generate', null, {
    params: { period_label },
  })
}

export function reviewPayroll(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/payroll/review', null, {
    params: { period_label },
  })
}

export function publishPayroll(period_label = '2026-07') {
  return request.post<PerformanceCycle>('/performance/cycles/payroll/publish', null, {
    params: { period_label },
  })
}
