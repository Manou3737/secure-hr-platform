
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import AuditOverview from './AuditOverview'

import type { AuditMetrics } from '../../../api/dashboardService'

const mockData: AuditMetrics = {
  as_of: '2026-11-22',
  period_days: 7,
  overview: {
    total_entries: 150,
    general_audit_entries: 80,
    document_access_entries: 40,
    workflow_entries: 30,
  },
  general_audit: {
    distribution: [
      { action: 'CREATE', count: 35 },
      { action: 'UPDATE', count: 30 },
      { action: 'DELETE', count: 15 },
    ],
  },
  document_access: {
    distribution: [
      { action: 'DOWNLOAD', count: 25 },
      { action: 'VIEW', count: 15 },
    ],
    access_denied: 4,
  },
  workflows: {
    distribution: [
      { event_type: 'APPROVED', count: 20 },
      { event_type: 'REJECTED', count: 10 },
    ],
    outcomes: {
      SUCCESS: 25,
      FAILURE: 3,
      DENIED: 2,
    },
  },
  daily_activity: {
    general_audit: [
      { created_at__date: '2026-11-20', count: 20 },
      { created_at__date: '2026-11-21', count: 30 },
    ],
    document_access: [
      { created_at__date: '2026-11-20', count: 10 },
      { created_at__date: '2026-11-21', count: 15 },
    ],
    workflow: [
      { created_at__date: '2026-11-20', count: 5 },
      { created_at__date: '2026-11-21', count: 10 },
    ],
  },
  recent_events: {
    general_audit: [
      {
        id: 1,
        action: 'EMPLOYEE_UPDATED',
        user_id: 101,
        created_at: '2026-11-22T10:00:00Z',
      },
    ],
    document_access: [
      {
        id: 2,
        action: 'DOCUMENT_DOWNLOADED',
        user_id: 102,
        document_id: 'doc-sensitive-123',
        created_at: '2026-11-22T10:30:00Z',
      },
    ],
    workflow: [
      {
        id: 3,
        event_type: 'APPLICATION_APPROVED',
        outcome: 'SUCCESS',
        actor_id: 103,
        created_at: '2026-11-22T11:00:00Z',
      },
    ],
  },
}

describe('AuditOverview', () => {
  it('displays audit statistics and sections', () => {
    render(<AuditOverview data={mockData} />)

    expect(screen.getByText('Audit overview')).toBeInTheDocument()
    expect(screen.getByText('Total audit entries')).toBeInTheDocument()
    expect(screen.getByText('General audit entries')).toBeInTheDocument()
    expect(screen.getByText('Document access entries')).toBeInTheDocument()
    expect(screen.getByText('Workflow entries')).toBeInTheDocument()

    expect(screen.getByText('General audit actions')).toBeInTheDocument()
    expect(screen.getByText('Document access activity')).toBeInTheDocument()
    expect(screen.getByText('Access denied')).toBeInTheDocument()
    expect(screen.getByText('Workflow event distribution')).toBeInTheDocument()
    expect(screen.getByText('Workflow outcomes')).toBeInTheDocument()
    expect(screen.getByText('Daily audit activity')).toBeInTheDocument()
    expect(screen.getByText('Recent audit events')).toBeInTheDocument()

    expect(screen.getByText('EMPLOYEE_UPDATED')).toBeInTheDocument()
    expect(screen.getByText('DOCUMENT_DOWNLOADED')).toBeInTheDocument()
    expect(screen.getByText('APPLICATION_APPROVED')).toBeInTheDocument()

    expect(screen.queryByText('101')).not.toBeInTheDocument()
    expect(screen.queryByText('102')).not.toBeInTheDocument()
    expect(screen.queryByText('103')).not.toBeInTheDocument()
    expect(screen.queryByText('doc-sensitive-123')).not.toBeInTheDocument()
  })

  it('handles empty audit data', () => {
    const emptyData: AuditMetrics = {
      ...mockData,
      overview: {
        total_entries: 0,
        general_audit_entries: 0,
        document_access_entries: 0,
        workflow_entries: 0,
      },
      general_audit: { distribution: [] },
      document_access: { distribution: [], access_denied: 0 },
      workflows: { distribution: [], outcomes: {} },
      daily_activity: {
        general_audit: [],
        document_access: [],
        workflow: [],
      },
      recent_events: {
        general_audit: [],
        document_access: [],
        workflow: [],
      },
    }

    render(<AuditOverview data={emptyData} />)

    expect(screen.getByText('No general audit actions available.')).toBeInTheDocument()
    expect(screen.getByText('No document access activity available.')).toBeInTheDocument()
    expect(screen.getByText('No workflow events available.')).toBeInTheDocument()
    expect(screen.getByText('No daily audit activity available.')).toBeInTheDocument()
    expect(screen.getByText('No recent audit events.')).toBeInTheDocument()
  })

  it('displays the configured reporting period', () => {
    render(<AuditOverview data={mockData} />)

    expect(
      screen.getByText('Audit activity over the last 7 days.'),
    ).toBeInTheDocument()
  })
})
