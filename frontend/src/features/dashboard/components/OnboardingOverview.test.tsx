import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { OnboardingMetrics } from '../../../api/dashboardService'
import OnboardingOverview from './OnboardingOverview'

const onboardingData: OnboardingMetrics = {
  journeys: {
    total: 10,
    pending: 2,
    in_progress: 3,
    suspended: 1,
    completed: 3,
    cancelled: 1,
  },
  tasks: {
    total: 50,
    pending: 10,
    in_progress: 8,
    blocked: 2,
    completed: 25,
    cancelled: 1,
    overdue: 4,
    overdue_details: [],
    low_priority: 10,
    medium_priority: 20,
    high_priority: 15,
    urgent_priority: 5,
  },
  progress: {
    total_eligible_tasks: 45,
    completed_tasks: 25,
    percentage: 55.56,
  },
  as_of: '2026-11-22',
}

describe('OnboardingOverview', () => {
  it('displays journey and task statistics', () => {
    render(<OnboardingOverview data={onboardingData} />)

    expect(
      screen.getByRole('heading', { name: 'Onboarding overview' }),
    ).toBeInTheDocument()

    expect(screen.getByText('Total Journeys')).toBeInTheDocument()
    expect(screen.getByText('Completed Journeys')).toBeInTheDocument()
    expect(screen.getByText('Total Tasks')).toBeInTheDocument()
    expect(screen.getByText('Overdue Tasks')).toBeInTheDocument()

    expect(screen.getByText('Journey status')).toBeInTheDocument()
    expect(screen.getByText('Task status')).toBeInTheDocument()

    expect(screen.getByText('55.6%')).toBeInTheDocument()
    expect(
      screen.getByText('25 of 45 eligible tasks completed.'),
    ).toBeInTheDocument()
  })

  it('displays task priorities', () => {
    render(<OnboardingOverview data={onboardingData} />)

    expect(screen.getByText('Low priority')).toBeInTheDocument()
    expect(screen.getByText('Medium priority')).toBeInTheDocument()
    expect(screen.getByText('High priority')).toBeInTheDocument()
    expect(screen.getByText('Urgent priority')).toBeInTheDocument()
  })

  it('handles empty onboarding data', () => {
    const emptyData: OnboardingMetrics = {
      journeys: {
        total: 0,
        pending: 0,
        in_progress: 0,
        suspended: 0,
        completed: 0,
        cancelled: 0,
      },
      tasks: {
        total: 0,
        pending: 0,
        in_progress: 0,
        blocked: 0,
        completed: 0,
        cancelled: 0,
        overdue: 0,
        overdue_details: [],
        low_priority: 0,
        medium_priority: 0,
        high_priority: 0,
        urgent_priority: 0,
      },
      progress: {
        total_eligible_tasks: 0,
        completed_tasks: 0,
        percentage: 0,
      },
      as_of: '2026-11-22',
    }

    render(<OnboardingOverview data={emptyData} />)

    expect(screen.getByText('0.0%')).toBeInTheDocument()

    expect(
      screen.getByText('0 of 0 eligible tasks completed.'),
    ).toBeInTheDocument()

    expect(screen.getByText('Journey status')).toBeInTheDocument()
    expect(screen.getByText('Task status')).toBeInTheDocument()

    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '0',
    )
  })

  it('clamps progress to the valid percentage range', () => {
    const outOfRangeData: OnboardingMetrics = {
      ...onboardingData,
      progress: {
        ...onboardingData.progress,
        percentage: 150,
      },
    }

    render(<OnboardingOverview data={outOfRangeData} />)

    expect(screen.getByText('100.0%')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute(
      'aria-valuenow',
      '100',
    )
  })

  it('displays overdue task details', () => {
    const dataWithOverdueTasks: OnboardingMetrics = {
      ...onboardingData,
      tasks: {
        ...onboardingData.tasks,
        overdue_details: [
          {
            id: 'task-001',
            title: 'Complete identity verification',
            due_date: '2026-11-15',
            priority: 'URGENT',
            status: 'BLOCKED',
            employee_name: 'John Doe',
          },
        ],
      },
    }

    render(
      <MemoryRouter>
        <OnboardingOverview data={dataWithOverdueTasks} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Overdue task details')).toBeInTheDocument()
    expect(
      screen.getByText('Complete identity verification'),
    ).toBeInTheDocument()
    expect(screen.getByText('John Doe')).toBeInTheDocument()
    expect(screen.getByText('2026-11-15')).toBeInTheDocument()
    expect(screen.getByText('Priority: URGENT')).toBeInTheDocument()
    expect(screen.getByText('Status: BLOCKED')).toBeInTheDocument()
    expect(
      screen.getByRole('link', {
        name: 'Complete identity verification',
      }),
    ).toHaveAttribute('href', '/tasks/task-001')
  })

  it('displays an empty state when there are no overdue tasks', () => {
    render(<OnboardingOverview data={onboardingData} />)

    expect(
      screen.getByText('No overdue tasks.'),
    ).toBeInTheDocument()
  })
})
