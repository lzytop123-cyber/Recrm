/**
 * 经营总览 API
 */
import request from './request'

export interface OverviewKpi {
  key: string
  label: string
  value: number
  display: string
  icon: string
  note: string
  delta: string
  delta_tone: string
  accent: boolean
  path?: string | null
}

export interface RevenueTrendPoint {
  month: string
  label: string
  income: number
  cash: number
}

export interface FunnelStep {
  label: string
  value: number
}

export interface AlertItem {
  key: string
  symbol: string
  title: string
  detail: string
  tone: string
  path: string
  action: string
}

export interface ProjectHealth {
  score: number
  healthy: number
  watch: number
  risk: number
}

export interface TodayScheduleItem {
  id: number
  time: string
  title: string
  subtitle: string
  external: boolean
  path: string
}

export interface OrgScoreItem {
  name: string
  score: number
}

export interface DashboardData {
  data_scope: string
  display_name: string
  as_of: string
  kpis: OverviewKpi[]
  revenue_trend: RevenueTrendPoint[]
  funnel: FunnelStep[]
  alerts: AlertItem[]
  project_health: ProjectHealth
  today_schedules: TodayScheduleItem[]
  org_execution: OrgScoreItem[]
}

export function fetchDashboard() {
  return request.get<DashboardData>('/dashboard')
}
