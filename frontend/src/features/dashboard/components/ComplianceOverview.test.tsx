import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ComplianceMetrics } from '../../../api/dashboardService'
import ComplianceOverview from './ComplianceOverview'

const complianceData: ComplianceMetrics = {
  as_of: '2026-11-22',
  headcount: 120,
  profiles: {
    complete: 100,
    incomplete: 20,
    completion_rate: 83.33,
    incomplete_details: [],
  },
  documents: {
    compliant_employees: 90,
    employees_missing_required_documents: 30,
    compliance_rate: 75,
    missing_documents_details: [],
    expired_count: 5,
    expired_details: [],
    expiring_soon_count: 8,
    expiring_soon_details: [],
    recently_uploaded_count: 0,
    recently_uploaded_details: [],
  },
}

describe('ComplianceOverview', () => {
  it('displays compliance statistics and completion rates', () => {
    render(<ComplianceOverview data={complianceData} />)

    expect(
      screen.getByRole('heading', { name: 'Compliance overview' }),
    ).toBeInTheDocument()

    expect(screen.getByText('Incomplete Profiles')).toBeInTheDocument()
    expect(screen.getByText('Missing Documents')).toBeInTheDocument()
    expect(screen.getByText('Expired Documents')).toBeInTheDocument()
    expect(screen.getByText('Expiring Soon')).toBeInTheDocument()

    expect(screen.getByText('83.3%')).toBeInTheDocument()
    expect(screen.getByText('75.0%')).toBeInTheDocument()

    expect(
      screen.getByText('100 of 120 employee profiles complete.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('90 employees compliant with required documents.'),
    ).toBeInTheDocument()
  })

  it('displays zero values without errors', () => {
    const emptyData: ComplianceMetrics = {
      ...complianceData,
      headcount: 0,
      profiles: {
        complete: 0,
        incomplete: 0,
        completion_rate: 0,
        incomplete_details: [],
      },
      documents: {
        compliant_employees: 0,
        employees_missing_required_documents: 0,
        compliance_rate: 0,
        missing_documents_details: [],
        expired_count: 0,
        expired_details: [],
        expiring_soon_count: 0,
        expiring_soon_details: [],
        recently_uploaded_count: 0,
        recently_uploaded_details: [],
        },
      }

    render(<ComplianceOverview data={emptyData} />)

    expect(screen.getAllByText('0')).toHaveLength(4)
    expect(screen.getAllByText('0.0%')).toHaveLength(2)
    expect(
      screen.getByText('0 of 0 employee profiles complete.'),
    ).toBeInTheDocument()
  })

  it('clamps progress bars to the valid percentage range', () => {
    const outOfRangeData: ComplianceMetrics = {
      ...complianceData,
      profiles: {
        ...complianceData.profiles,
        completion_rate: 120,
      },
      documents: {
        ...complianceData.documents,
        compliance_rate: -10,
      },
    }

    render(<ComplianceOverview data={outOfRangeData} />)

    const profileProgress = screen.getByRole('progressbar', {
      name: 'Profile completion',
    })
    const documentProgress = screen.getByRole('progressbar', {
      name: 'Document compliance',
    })

    expect(profileProgress).toHaveAttribute('aria-valuenow', '100')
    expect(documentProgress).toHaveAttribute('aria-valuenow', '0')
  })

  it('displays expired document details', () => {
    const dataWithExpiredDocuments: ComplianceMetrics = {
      ...complianceData,
      documents: {
        ...complianceData.documents,
        expired_details: [
          {
            id: 'doc-001',
            employee_id: 19,
            employee__user__name: 'John Doe',
            document_type: 'IDENTITY',
            expires_at: '2026-11-15',
          },
        ],
      },
    }

    render(<ComplianceOverview data={dataWithExpiredDocuments} />)

    expect(screen.getByText('Expired document details')).toBeInTheDocument()
    expect(screen.getByText('John Doe')).toBeInTheDocument()
    expect(screen.getByText('IDENTITY')).toBeInTheDocument()
    expect(screen.getByText('2026-11-15')).toBeInTheDocument()
  })

  it('displays an empty state when there are no expired documents', () => {
    render(<ComplianceOverview data={complianceData} />)

    expect(
      screen.getByText('No expired documents.'),
    ).toBeInTheDocument()
  })
})
