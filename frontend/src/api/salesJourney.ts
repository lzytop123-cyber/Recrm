import request from './request'

export type JourneyMilestoneStatus = 'done' | 'current' | 'pending' | 'skipped'

export interface SalesJourneyMilestone {
  key: string
  label: string
  status: JourneyMilestoneStatus | string
  at?: string | null
  actor?: string | null
  entity?: 'lead' | 'customer' | 'opportunity' | 'contract' | string | null
  entity_id?: number | null
}

export interface SalesJourneyLinks {
  lead_id?: number | null
  customer_id?: number | null
  opportunity_id?: number | null
  contract_id?: number | null
  lead_label?: string | null
  customer_name?: string | null
  opportunity_no?: string | null
  contract_no?: string | null
}

export interface SalesJourney {
  milestones: SalesJourneyMilestone[]
  links: SalesJourneyLinks
  current_key?: string | null
}

export function fetchLeadJourney(leadId: number) {
  return request.get<SalesJourney>(`/leads/${leadId}/journey`)
}

export function fetchOpportunityJourney(opportunityId: number) {
  return request.get<SalesJourney>(`/opportunities/${opportunityId}/journey`)
}
