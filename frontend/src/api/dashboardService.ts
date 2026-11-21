import api from './client'

export interface DashboardResponse {
  workforce: {
    headcount: {
      total: number
      active_accounts: number
      inactive_accounts: number
    }
  }
  recruitment: {
    job_postings: {
      total: number
      by_status: Array<{
        status: string
        count: number
      }>
    }
  }
  risk: {
    document_lifecycle: {
      pending_scan: number
      pending_review: number
      quarantined: number
      rejected: number
      verified: number
      archived: number
    }
  }
}

export async function getDashboard(): Promise<DashboardResponse> {
  const response = await api.get<DashboardResponse>(
    '/employees/dashboard/',
  )

  return response.data
}
