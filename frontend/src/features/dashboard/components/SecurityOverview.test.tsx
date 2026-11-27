import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import SecurityOverview from './SecurityOverview'

import type { SecurityMetrics } from '../../../api/dashboardService'

const mockData: SecurityMetrics = {
  as_of: '2026-11-22',
  period_days: 7,
  overview: {
    total_events: 120,
    login_success: 90,
    login_failed: 30,
  },
  detections: {
    brute_force: 5,
    suspicious_ip: 3,
    unauthorized_access: 2,
    privilege_escalation: 1,
  },
  sources: {
    distinct_ips: 14,
    distinct_users: 8,
  },
  events: {
    distribution: [
      { event_type: 'LOGIN_SUCCESS', count: 90 },
      { event_type: 'LOGIN_FAILED', count: 30 },
    ],
  },
  daily_activity: [
    { created_at__date: '2026-11-20', count: 15 },
    { created_at__date: '2026-11-21', count: 25 },
  ],
  recent_events: [
    {
      id: 1,
      event_type: 'LOGIN_FAILED',
      ip_address: '192.168.1.100',
      request_path: '/api/auth/login/',
      created_at: '2026-11-22T10:00:00Z',
    },
    {
      id: 2,
      event_type: 'LOGIN_SUCCESS',
      ip_address: null,
      request_path: null,
      created_at: '2026-11-22T11:00:00Z',
    },
  ],
}

describe('SecurityOverview', () => {
  it('displays security statistics and sections', () => {
    render(<SecurityOverview data={mockData} />)

    expect(screen.getByText('Security overview')).toBeInTheDocument()
    expect(screen.getByText('Total events')).toBeInTheDocument()
    expect(screen.getByText('Successful logins')).toBeInTheDocument()
    expect(screen.getByText('Failed logins')).toBeInTheDocument()

    expect(screen.getByText('Security detections')).toBeInTheDocument()
    expect(screen.getByText('Brute force')).toBeInTheDocument()
    expect(screen.getByText('Suspicious IP')).toBeInTheDocument()
    expect(screen.getByText('Unauthorized access')).toBeInTheDocument()
    expect(screen.getByText('Privilege escalation')).toBeInTheDocument()

    expect(screen.getByText('Security sources')).toBeInTheDocument()
    expect(screen.getByText('Event distribution')).toBeInTheDocument()
    expect(screen.getByText('Daily security activity')).toBeInTheDocument()
    expect(screen.getByText('Recent security events')).toBeInTheDocument()

    expect(screen.getAllByText('LOGIN_SUCCESS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('LOGIN_FAILED').length).toBeGreaterThan(0)
    expect(screen.queryByText('192.168.1.100')).not.toBeInTheDocument()
    expect(screen.queryByText('/api/auth/login/')).not.toBeInTheDocument()
  })

  it('handles empty distributions and recent events', () => {
    const emptyData: SecurityMetrics = {
      ...mockData,
      overview: {
        total_events: 0,
        login_success: 0,
        login_failed: 0,
      },
      detections: {
        brute_force: 0,
        suspicious_ip: 0,
        unauthorized_access: 0,
        privilege_escalation: 0,
      },
      sources: {
        distinct_ips: 0,
        distinct_users: 0,
      },
      events: {
        distribution: [],
      },
      daily_activity: [],
      recent_events: [],
    }

    render(<SecurityOverview data={emptyData} />)

    expect(
      screen.getByText('No security events available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No daily security activity available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No recent security events.'),
    ).toBeInTheDocument()
  })

  it('displays the configured reporting period', () => {
    render(<SecurityOverview data={mockData} />)

    expect(
      screen.getByText(
        'Security activity and detections over the last 7 days.',
      ),
    ).toBeInTheDocument()
  })
})
