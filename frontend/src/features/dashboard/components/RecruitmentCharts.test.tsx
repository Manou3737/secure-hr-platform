import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { RecruitmentMetrics } from '../../../api/dashboardService'
import RecruitmentCharts from './RecruitmentCharts'

const recruitmentData: RecruitmentMetrics = {
  as_of: '2026-11-22',
  period_days: 7,
  job_postings: {
    total: 8,
    by_status: [
      { status: 'OPEN', count: 5 },
      { status: 'CLOSED', count: 2 },
      { status: 'DRAFT', count: 1 },
    ],
  },
  applications: {
    total: 40,
    by_status: [
      { status: 'SUBMITTED', count: 20 },
      { status: 'UNDER_REVIEW', count: 15 },
      { status: 'HIRED', count: 5 },
    ],
    received_in_period: 12,
    hired_in_period: 2,
  },
  daily_activity: [
    { applied_at__date: '2026-11-20', count: 4 },
    { applied_at__date: '2026-11-21', count: 8 },
  ],
}

describe('RecruitmentCharts', () => {
  it('displays recruitment statistics and the hiring rate', () => {
    render(<RecruitmentCharts data={recruitmentData} />)

    expect(
      screen.getByRole('heading', { name: 'Recruitment overview' }),
    ).toBeInTheDocument()

    expect(screen.getByText('Total Job Postings')).toBeInTheDocument()
    expect(screen.getByText('Applications Received')).toBeInTheDocument()

    const openPostingsCard = screen
      .getByText('Open Postings')
      .closest('article')

    expect(openPostingsCard).not.toBeNull()
    expect(within(openPostingsCard as HTMLElement).getByText('5')).toBeInTheDocument()

    const hiredCard = screen.getByText('Hired').closest('article')

    expect(hiredCard).not.toBeNull()
    expect(within(hiredCard as HTMLElement).getByText('2')).toBeInTheDocument()
    expect(within(hiredCard as HTMLElement).getByText('5.0% of total applications')).toBeInTheDocument()

    expect(
      screen.getByText('Recruitment activity over the last 7 days.'),
    ).toBeInTheDocument()
  })

  it('displays empty states when chart data is unavailable', () => {
    const emptyData: RecruitmentMetrics = {
      ...recruitmentData,
      job_postings: {
        ...recruitmentData.job_postings,
        by_status: [],
      },
      applications: {
        ...recruitmentData.applications,
        by_status: [],
      },
      daily_activity: [],
    }

    render(<RecruitmentCharts data={emptyData} />)

    expect(
      screen.getByText('No job posting status data available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No application status data available.'),
    ).toBeInTheDocument()

    expect(
      screen.getByText('No daily application activity available.'),
    ).toBeInTheDocument()
  })

  it('handles zero applications without producing an invalid hiring rate', () => {
    const zeroData: RecruitmentMetrics = {
      ...recruitmentData,
      job_postings: {
        ...recruitmentData.job_postings,
        by_status: [],
      },
      applications: {
        total: 0,
        by_status: [],
        received_in_period: 0,
        hired_in_period: 0,
      },
      daily_activity: [],
    }

    render(<RecruitmentCharts data={zeroData} />)

    const openPostingsCard = screen
      .getByText('Open Postings')
      .closest('article')

    expect(openPostingsCard).not.toBeNull()
    expect(within(openPostingsCard as HTMLElement).getByText('0')).toBeInTheDocument()

    const hiredCard = screen.getByText('Hired').closest('article')

    expect(hiredCard).not.toBeNull()
    expect(within(hiredCard as HTMLElement).getByText('0')).toBeInTheDocument()
    expect(within(hiredCard as HTMLElement).getByText('0% of total applications')).toBeInTheDocument()
  })
})
