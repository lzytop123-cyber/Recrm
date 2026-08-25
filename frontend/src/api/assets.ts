/**
 * 固定资产 API
 */
import request from './request'

export type AssetStatus =
  | 'available'
  | 'reserved'
  | 'borrowed'
  | 'pending_return'
  | 'maintenance'
  | 'disposed'

export type BorrowStatus =
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'in_use'
  | 'pending_return'
  | 'returned'

export interface FixedAsset {
  id: number
  asset_no: string
  name: string
  category: string
  model?: string | null
  serial_no?: string | null
  status: AssetStatus | string
  holder_id?: number | null
  department_id?: number | null
  location?: string | null
  original_value: number | string
  purchase_date?: string | null
  next_maintenance?: string | null
  qr_code: string
  current_use?: string | null
  schedule_ref?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  holder_name?: string | null
  department_name?: string | null
  monthly_depreciation?: number | string | null
  accumulated_depreciation?: number | string | null
  net_value?: number | string | null
}

export interface BorrowItem {
  asset_id: number
  asset_no: string
  name: string
  category: string
  status: string
}

export interface BorrowRequest {
  id: number
  request_no: string
  purpose: string
  applicant_id: number
  start_time: string
  end_time: string
  schedule_ref?: string | null
  status: BorrowStatus | string
  reject_reason?: string | null
  approved_by?: number | null
  approved_at?: string | null
  returned_at?: string | null
  remark?: string | null
  created_at: string
  updated_at: string
  applicant_name?: string | null
  assets: BorrowItem[]
  asset_count: number
  approval_in_center?: boolean
  open_approval_id?: string | null
}

export interface InventorySession {
  id: number
  period_label: string
  title: string
  target_count: number
  scanned_count: number
  matched_count: number
  anomaly_count: number
  status: string
}

export interface AssetStats {
  total: number
  available: number
  available_rate: number
  borrowed_or_reserved: number
  due_today: number
  alerts: number
  maintenance: number
  overdue: number
  original_value_sum: number | string
  net_value_sum: number | string
  utilization_rate: number
  on_time_return_rate: number
  maintenance_cost: number | string
}

export interface AssetWorkbench {
  stats: AssetStats
  assets: FixedAsset[]
  borrows: BorrowRequest[]
  inventory?: InventorySession | null
  category_usage: Array<{ category: string; count: number; utilization: number }>
  alerts: Array<{
    kind: string
    title: string
    detail: string
    tag: string
    asset_id?: number | null
    request_id?: number | null
  }>
  top_borrows: Array<{ asset_id: number; name: string; count: number; score: number }>
  can_manage: boolean
}

export const ASSET_STATUS_LABEL: Record<string, string> = {
  available: '在库可用',
  reserved: '已预占',
  borrowed: '借出中',
  pending_return: '待归还验收',
  maintenance: '维修中',
  disposed: '已处置',
}

export const BORROW_STATUS_LABEL: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  rejected: '已驳回',
  in_use: '使用中',
  pending_return: '待归还验收',
  returned: '已归还',
}

export const ASSET_CATEGORY_OPTIONS = ['相机', '镜头', '灯具', '收音', '稳定器', '其他']

export function fetchAssetWorkbench() {
  return request.get<AssetWorkbench>('/assets/workbench')
}

export function createAsset(data: {
  name: string
  category: string
  model?: string
  serial_no?: string
  location?: string
  original_value?: number
  purchase_date?: string
  next_maintenance?: string
  department_id?: number
  remark?: string
  quantity?: number
}) {
  return request.post<FixedAsset>('/assets', data)
}

export function updateAsset(
  id: number,
  data: {
    name?: string
    category?: string
    model?: string | null
    serial_no?: string | null
    location?: string | null
    original_value?: number
    purchase_date?: string | null
    next_maintenance?: string | null
    department_id?: number | null
    remark?: string | null
    apply_to_same_model?: boolean
    quantity?: number
  },
) {
  return request.patch<FixedAsset>(`/assets/${id}`, data)
}

export function createBorrow(data: {
  purpose: string
  asset_ids: number[]
  start_time: string
  end_time: string
  schedule_ref?: string
  remark?: string
}) {
  return request.post<BorrowRequest>('/assets/borrows', data)
}

export function approveBorrow(id: number) {
  return request.post<BorrowRequest>(`/assets/borrows/${id}/approve`)
}

export function rejectBorrow(id: number, reason: string) {
  return request.post<BorrowRequest>(`/assets/borrows/${id}/reject`, { reason })
}

export function checkoutBorrow(id: number) {
  return request.post<BorrowRequest>(`/assets/borrows/${id}/checkout`)
}

export function returnBorrow(id: number) {
  return request.post<BorrowRequest>(`/assets/borrows/${id}/return`)
}

export function scanAsset(data: { qr_code?: string; asset_id?: number; mode?: string }) {
  return request.post<{
    ok: boolean
    message: string
    asset?: FixedAsset
    inventory?: InventorySession
  }>('/assets/scan', data)
}

/** 同型号合并：分类 + 名称 + 型号 */
export function assetSkuKey(a: { name: string; category: string; model?: string | null }) {
  return `${a.category.trim()}\u0001${a.name.trim()}\u0001${(a.model || '').trim()}`
}

const OCCUPIED_STATUS = new Set(['borrowed', 'reserved', 'pending_return'])

export interface AssetSkuGroup {
  key: string
  name: string
  category: string
  model: string
  location: string
  original_value: number
  original_value_sum: number
  qty: number
  available: number
  occupied: number
  maintenance: number
  other: number
  units: FixedAsset[]
}

export function groupAssetsBySku(list: FixedAsset[]): AssetSkuGroup[] {
  const map = new Map<string, AssetSkuGroup>()
  for (const a of list) {
    const key = assetSkuKey(a)
    let g = map.get(key)
    if (!g) {
      g = {
        key,
        name: a.name,
        category: a.category,
        model: (a.model || '').trim(),
        location: a.location || '',
        original_value: Number(a.original_value || 0),
        original_value_sum: 0,
        qty: 0,
        available: 0,
        occupied: 0,
        maintenance: 0,
        other: 0,
        units: [],
      }
      map.set(key, g)
    }
    g.units.push(a)
    g.qty += 1
    g.original_value_sum += Number(a.original_value || 0)
    if (a.status === 'available') g.available += 1
    else if (a.status === 'maintenance') g.maintenance += 1
    else if (OCCUPIED_STATUS.has(String(a.status))) g.occupied += 1
    else g.other += 1
  }
  for (const g of map.values()) {
    const locs = new Set(g.units.map((u) => (u.location || '').trim()))
    g.location = locs.size === 1 ? g.units[0].location || '' : '多位置'
  }
  return [...map.values()]
}

export function groupBorrowItems(items: BorrowItem[]) {
  const map = new Map<string, { name: string; category: string; items: BorrowItem[] }>()
  for (const a of items) {
    const key = `${a.category}\u0001${a.name}`
    let g = map.get(key)
    if (!g) {
      g = { name: a.name, category: a.category, items: [] }
      map.set(key, g)
    }
    g.items.push(a)
  }
  return [...map.values()]
}
