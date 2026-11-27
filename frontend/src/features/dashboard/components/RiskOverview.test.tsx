import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import RiskOverview from './RiskOverview'

import type { RiskMetrics } from '../../../api/dashboardService'

const mockData: RiskMetrics = {
  as_of: '2026-11-22',
  compliance: {
    incomplete_profiles: 12,
    employees_missing_required_documents: 8,
    expired_documents: 5,
    documents_expiring_soon: 7,
  },
  document_lifecycle: {
    pending_scan: 3,
    pending_review: 6,
    quarantined: 2,
    rejected: 4,
    verified: 45,
    archived: 10,
  },
  security: {
    brute_force: 9,
    suspicious_ip: 4,
    unauthorized_access: 3,
    privilege_escalation: 1,
  },
}

describe('RiskOverview', () => {
  it('displays risk metrics and all categories', () => {
    render(<RiskOverview data={mockData} />)

    expect(screen.getByText('Risk overview')).toBeInTheDocument()

    // Compliance
    expect(screen.getByText('Compliance risks')).toBeInTheDocument()
    expect(screen.getByText('Incomplete profiles')).toBeInTheDocument()
    expect(
      screen.getByText('Employees missing required documents'),
    ).toBeInTheDocument()
    expect(screen.getByText('Expired documents')).toBeInTheDocument()
    expect(screen.getByText('Documents expiring soon')).toBeInTheDocument()

    // Document lifecycle
    expect(screen.getByText('Document lifecycle')).toBeInTheDocument()
    expect(screen.getByText('Pending scan')).toBeInTheDocument()
    expect(screen.getByText('Pending review')).toBeInTheDocument()
    expect(screen.getByText('Quarantined')).toBeInTheDocument()
    expect(screen.getByText('Rejected')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('Archived')).toBeInTheDocument()

    // Security
    expect(screen.getByText('Security detections')).toBeInTheDocument()
    expect(screen.getByText('Brute force')).toBeInTheDocument()
    expect(screen.getByText('Suspicious IP')).toBeInTheDocument()
    expect(screen.getByText('Unauthorized access')).toBeInTheDocument()
    expect(screen.getByText('Privilege escalation')).toBeInTheDocument()
  })

  it('handles zero risk metrics', () => {
    const emptyData: RiskMetrics = {
      as_of: '2026-11-22',
      compliance: {
        incomplete_profiles: 0,
        employees_missing_required_documents: 0,
        expired_documents: 0,
        documents_expiring_soon: 0,
      },
      document_lifecycle: {
        pending_scan: 0,
        pending_review: 0,
        quarantined: 0,
        rejected: 0,
        verified: 0,
        archived: 0,
      },
      security: {
        brute_force: 0,
        suspicious_ip: 0,
        unauthorized_access: 0,
        privilege_escalation: 0,
      },
    }

    render(<RiskOverview data={emptyData} />)

    expect(screen.getByText('No compliance risks detected.')).toBeInTheDocument()
    expect(
      screen.getByText('No document lifecycle activity.'),
    ).toBeInTheDocument()
    expect(screen.getByText('No security detections.')).toBeInTheDocument()
  })
})
