
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getEmployeeById } from '../api/employeeService'
import type { EmployeeProfile } from '../api/employeeService'
import { getDepartments } from '../api/departmentService'
import type { Department } from '../api/departmentService'
import { getPositions } from '../api/positionService'
import type { Position } from '../api/positionService'

import EmployeeDetailPage from './EmployeeDetailPage'

vi.mock('../api/employeeService', () => ({
  getEmployeeById: vi.fn(),
}))

vi.mock('../api/departmentService', () => ({
  getDepartments: vi.fn(),
}))

vi.mock('../api/positionService', () => ({
  getPositions: vi.fn(),
}))

const employee: EmployeeProfile = {
  id: 1,
  user: 10,
  employee_id: 'EMP-001',
  department: 2,
  position: 3,
  phone: '5551234567',
  hire_date: '2025-01-15',
  date_of_birth: null,
  address: 'Private address',
  created_at: '2025-01-15T10:00:00Z',
  updated_at: '2025-01-15T10:00:00Z',
}

const departments: Department[] = [
  {
    id: 2,
    name: 'Engineering',
    code: 'ENG',
    description: '',
  },
]

const positions: Position[] = [
  {
    id: 3,
    title: 'Developer',
    department: 2,
    description: '',
  },
]

function createResponse<T>(results: T[]) {
  return {
    count: results.length,
    next: null,
    previous: null,
    results,
  }
}

function renderEmployeeDetailPage(path = '/employees/1') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/employees/:id"
            element={<EmployeeDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('EmployeeDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(getEmployeeById).mockResolvedValue(employee)
    vi.mocked(getDepartments).mockResolvedValue(
      createResponse(departments),
    )
    vi.mocked(getPositions).mockResolvedValue(
      createResponse(positions),
    )
  })

  it('displays employee professional information', async () => {
    renderEmployeeDetailPage()

    expect(
      await screen.findByText('Employee details'),
    ).toBeInTheDocument()

    expect(screen.getByText('EMP-001')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('Developer')).toBeInTheDocument()
    expect(screen.getByText('2025-01-15')).toBeInTheDocument()

    expect(getEmployeeById).toHaveBeenCalledWith(1)
    expect(getPositions).toHaveBeenCalledWith(2)

    expect(
      screen.getByRole('link', { name: /back to employees/i }),
    ).toHaveAttribute('href', '/employees')
  })

  it('does not display private employee information', async () => {
    renderEmployeeDetailPage()

    expect(
      await screen.findByText('Employee details'),
    ).toBeInTheDocument()

    expect(screen.queryByText('Private address')).not.toBeInTheDocument()
    expect(screen.queryByText('5551234567')).not.toBeInTheDocument()
  })

  it('displays an invalid ID message without calling the API', () => {
    renderEmployeeDetailPage('/employees/invalid')

    expect(screen.getByText('Invalid employee ID.')).toBeInTheDocument()
    expect(getEmployeeById).not.toHaveBeenCalled()
  })

  it('displays an error when employee loading fails', async () => {
    vi.mocked(getEmployeeById).mockRejectedValue(
      new Error('Request failed'),
    )

    renderEmployeeDetailPage()

    expect(
      await screen.findByText(
        'Unable to load this employee record.',
      ),
    ).toBeInTheDocument()
  })

  it('displays a loading state while employee data is pending', () => {
    vi.mocked(getEmployeeById).mockReturnValue(
      new Promise(() => {}),
    )

    renderEmployeeDetailPage()

    expect(
      screen.getByText('Loading employee details...'),
    ).toBeInTheDocument()
  })

  it('falls back to department and position IDs when lookup fails', async () => {
    vi.mocked(getDepartments).mockRejectedValue(
      new Error('Departments unavailable'),
    )
    vi.mocked(getPositions).mockRejectedValue(
      new Error('Positions unavailable'),
    )

    renderEmployeeDetailPage()

    expect(
      await screen.findByText('Professional information'),
    ).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Department #2')).toBeInTheDocument()
      expect(screen.getByText('Position #3')).toBeInTheDocument()
    })
  })
})
