import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import OperationsOverview from './OperationsOverview'

import type { OperationsMetrics } from '../../../api/dashboardService'

const mockData: OperationsMetrics = {
  as_of: '2026-11-22',
  period_days: 7,
  workflows: {
    total: 30,
    success: 25,
    failure: 2,
    denied: 3,
  },
  notifications: {
    failed: 2,
    by_type: [
      {
        details__notification_type: 'DOCUMENT_EXPIRY',
        count: 5,
      },
      {
        details__notification_type: 'ONBOARDING_REMINDER',
        count: 3,
      },
    ],
  },
  events: {
    distribution: [
      { event_type: 'DOCUMENT_CREATED', count: 12 },
      { event_type: 'WORKFLOW_COMPLETED', count: 8 },
    ],
  },
  daily_activity: [
    { created_at__date: '2026-11-20', count: 10 },
    { created_at__date: '2026-11-21', count: 15 },
  ],
}

describe('OperationsOverview', () => {
  it('displays operational statistics', () => {
    render(<OperationsOverview data={mockData} />)

    expect(screen.getByText('Operations overview')).toBeInTheDocument()
    expect(screen.getByText('Total workflows')).toBeInTheDocument()
    expect(screen.getByText('Successful workflows')).toBeInTheDocument()
    expect(screen.getByText('Failed workflows')).toBeInTheDocument()
    expect(screen.getByText('Failed notifications')).toBeInTheDocument()

    expect(screen.getByText('Workflow outcomes')).toBeInTheDocument()
    expect(screen.getByText('Notifications by type')).toBeInTheDocument()
    expect(screen.getByText('Event distribution')).toBeInTheDocument()
    expect(screen.getByText('Daily operational activity')).toBeInTheDocument()

    expect(screen.getByText('DOCUMENT_EXPIRY')).toBeInTheDocument()
    expect(screen.getByText('ONBOARDING_REMINDER')).toBeInTheDocument()
    expect(screen.getByText('DOCUMENT_CREATED')).toBeInTheDocument()
    expect(screen.getByText('WORKFLOW_COMPLETED')).toBeInTheDocument()

    expect(screen.getByText('2026-11-20')).toBeInTheDocument()
    expect(screen.getByText('2026-11-21')).toBeInTheDocument()
  })

  it('displays empty states when distributions are empty', () => {
    const emptyData: OperationsMetrics = {
      ...mockData,
      workflows: {
        total: 0,
        success: 0,
        failure: 0,
        denied: 0,
      },
      notifications: {
        failed: 0,
        by_type: [],
      },
      events: {
        distribution: [],
      },
      daily_activity: [],
    }

    render(<OperationsOverview data={emptyData} />)

    expect(
      screen.getByText('No notification breakdown available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No operational events available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No daily activity available.'),
    ).toBeInTheDocument()

    expect(
      screen.getAllByRole('progressbar').every(
        (bar) => bar.getAttribute('aria-valuenow') === '0',
      ),
    ).toBe(true)
  })

  it('displays the configured reporting period', () => {
    render(<OperationsOverview data={mockData} />)

    expect(
      screen.getByText(
        'Workflow execution and operational activity over the last 7 days.',
      ),
    ).toBeInTheDocument()
  })
})
