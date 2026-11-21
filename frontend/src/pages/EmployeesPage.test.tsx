import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getEmployees } from '../api/employeeService'
import type {
  EmployeeProfile,
  PaginatedResponse,
} from '../api/employeeService'
import { getDepartments } from '../api/departmentService'
import type { Department } from '../api/departmentService'
import { getPositions } from '../api/positionService'
import type { Position } from '../api/positionService'
import EmployeesPage from './EmployeesPage'

vi.mock('../api/employeeService', () => ({
  getEmployees: vi.fn(),
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
  { id: 2, name: 'Engineering', code: 'ENG', description: '' },
  { id: 4, name: 'Finance', code: 'FIN', description: '' },
]

const positions: Position[] = [
  { id: 3, title: 'Developer', department: 2, description: '' },
  { id: 5, title: 'Financial Analyst', department: 4, description: '' },
]

function createResponse<T>(
  results: T[],
  count = results.length,
): PaginatedResponse<T> {
  return {
    count,
    next: null,
    previous: null,
    results,
  }
}

function renderEmployeesPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <EmployeesPage />
    </QueryClientProvider>,
  )
}

describe('EmployeesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(getEmployees).mockResolvedValue(
      createResponse([employee]),
    )

    vi.mocked(getDepartments).mockResolvedValue(
      createResponse(departments),
    )

    vi.mocked(getPositions).mockResolvedValue(
      createResponse(positions),
    )
  })

  it('displays employees returned by the API', async () => {
    renderEmployeesPage()

    expect(await screen.findByText('EMP-001')).toBeInTheDocument()

    expect(screen.getByText('10')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('2025-01-15')).toBeInTheDocument()

    expect(getEmployees).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
    })

    expect(screen.queryByText('Private address')).not.toBeInTheDocument()
    expect(screen.queryByText('5551234567')).not.toBeInTheDocument()
  })

  it('displays a loading state', () => {
    vi.mocked(getEmployees).mockReturnValue(new Promise(() => {}))

    renderEmployeesPage()

    expect(screen.getByText('Loading employees...')).toBeInTheDocument()
  })

  it('displays a safe error message when the API request fails', async () => {
    const technicalError =
      'Request failed with status code 500: internal database details'

    vi.mocked(getEmployees).mockRejectedValue(
      new Error(technicalError),
    )

    renderEmployeesPage()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Unable to load employees. Please try again.',
    )

    expect(screen.queryByText(technicalError)).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Try again' }),
    ).toBeInTheDocument()
  })

  it('applies the hire date filter and resets pagination', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by hire date'), {
      target: { value: '2025-01-15' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        hire_date: '2025-01-15',
      })
    })
  })

  it('searches employees using the backend search parameter', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Search employees'), {
      target: { value: 'Engineering' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: 'Engineering',
      })
    })
  })

  it('resets pagination to page 1 when the search changes', async () => {
    const secondEmployee: EmployeeProfile = {
      ...employee,
      id: 2,
      employee_id: 'EMP-002',
    }

    vi.mocked(getEmployees)
      .mockResolvedValueOnce(createResponse([employee], 21))
      .mockResolvedValueOnce(createResponse([secondEmployee], 21))
      .mockResolvedValue(createResponse([employee]))

    renderEmployeesPage()

    expect(await screen.findByText('EMP-001')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('EMP-002')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Search employees'), {
      target: { value: 'Engineering' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: 'Engineering',
      })
    })
  })

  it('loads departments and does not load positions before a department is selected', async () => {
    renderEmployeesPage()

    expect(
      await screen.findByRole('option', { name: 'Engineering' }),
    ).toBeInTheDocument()

    expect(getDepartments).toHaveBeenCalledTimes(1)
    expect(getPositions).not.toHaveBeenCalled()

    expect(
      screen.getByLabelText('Filter by position'),
    ).toBeDisabled()
  })

  it('filters employees by department and resets pagination', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        department: 2,
      })
    })

    await waitFor(() => {
      expect(getPositions).toHaveBeenCalledWith(2)
    })
  })

  it('loads position options for the selected department', async () => {
    vi.mocked(getPositions).mockImplementation(async (department) => {
      const filtered = positions.filter(
        (item) => item.department === department,
      )
      return createResponse(filtered)
    })

    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    expect(
      await screen.findByRole('option', { name: 'Developer' }),
    ).toBeInTheDocument()

    expect(getPositions).toHaveBeenCalledWith(2)
  })

  it('filters employees by position and department together', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await screen.findByRole('option', { name: 'Developer' })

    fireEvent.change(screen.getByLabelText('Filter by position'), {
      target: { value: '3' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        department: 2,
        position: 3,
      })
    })
  })

  it('clears the selected position when the department changes', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await screen.findByRole('option', { name: 'Developer' })

    fireEvent.change(screen.getByLabelText('Filter by position'), {
      target: { value: '3' },
    })

    await waitFor(() => {
      expect(screen.getByLabelText('Filter by position')).toHaveValue('3')
    })

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '4' },
    })

    await waitFor(() => {
      expect(screen.getByLabelText('Filter by position')).toHaveValue('')
    })

    await waitFor(() => {
      expect(getPositions).toHaveBeenCalledWith(4)
    })
  })

  it('combines search, department, position and hire date filters', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Search employees'), {
      target: { value: 'Developer' },
    })

    fireEvent.change(screen.getByLabelText('Filter by hire date'), {
      target: { value: '2025-01-15' },
    })

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await screen.findByRole('option', { name: 'Developer' })

    fireEvent.change(screen.getByLabelText('Filter by position'), {
      target: { value: '3' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: 'Developer',
        hire_date: '2025-01-15',
        department: 2,
        position: 3,
      })
    })
  })

  it('clears all active filters and resets pagination', async () => {
    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Search employees'), {
      target: { value: 'Engineering' },
    })

    fireEvent.change(screen.getByLabelText('Filter by hire date'), {
      target: { value: '2025-01-15' },
    })

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await screen.findByRole('option', { name: 'Developer' })

    fireEvent.change(screen.getByLabelText('Filter by position'), {
      target: { value: '3' },
    })

    fireEvent.click(
      await screen.findByRole('button', { name: 'Clear all filters' }),
    )

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
      })
    })

    expect(screen.getByLabelText('Search employees')).toHaveValue('')
    expect(screen.getByLabelText('Filter by hire date')).toHaveValue('')
    expect(screen.getByLabelText('Filter by department')).toHaveValue('')
    expect(screen.getByLabelText('Filter by position')).toHaveValue('')

    expect(
      screen.queryByRole('button', { name: 'Clear all filters' }),
    ).not.toBeInTheDocument()
  })

  it('loads the next page when pagination is used', async () => {
    const secondEmployee: EmployeeProfile = {
      ...employee,
      id: 2,
      employee_id: 'EMP-002',
    }

    vi.mocked(getEmployees)
      .mockResolvedValueOnce(createResponse([employee], 21))
      .mockResolvedValueOnce(createResponse([secondEmployee], 21))

    renderEmployeesPage()

    expect(await screen.findByText('EMP-001')).toBeInTheDocument()
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('EMP-002')).toBeInTheDocument()

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 2,
        page_size: 20,
      })
    })
  })

  it('preserves active filters when moving to the next page', async () => {
    const secondEmployee: EmployeeProfile = {
      ...employee,
      id: 2,
      employee_id: 'EMP-002',
    }

    vi.mocked(getEmployees).mockResolvedValue(
      createResponse([employee], 21),
    )

    renderEmployeesPage()

    await screen.findByText('EMP-001')

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        department: 2,
      })
    })

    expect(await screen.findByText('Page 1 of 2')).toBeInTheDocument()

    vi.mocked(getEmployees).mockResolvedValue(
      createResponse([secondEmployee], 21),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))

    expect(await screen.findByText('EMP-002')).toBeInTheDocument()

    await waitFor(() => {
      expect(getEmployees).toHaveBeenLastCalledWith({
        page: 2,
        page_size: 20,
        department: 2,
      })
    })
  })

  it('displays a safe error and retry option when departments fail to load', async () => {
    vi.mocked(getDepartments).mockRejectedValue(
      new Error('Internal database error'),
    )

    renderEmployeesPage()

    expect(
      await screen.findByText(
        'Unable to load departments. Please try again.',
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Retry departments' }),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Internal database error'),
    ).not.toBeInTheDocument()
  })

  it('displays a safe error and retry option when positions fail to load', async () => {
    vi.mocked(getPositions).mockRejectedValue(
      new Error('Internal database error'),
    )

    renderEmployeesPage()

    // Attendre que les départements soient chargés.
    await screen.findByRole('option', { name: 'Engineering' })

    // Sélectionner Engineering.
    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    // Vérifier l'erreur publique et le bouton de nouvelle tentative.
    expect(
      await screen.findByText(
        'Unable to load positions. Please try again.',
      ),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Retry positions' }),
    ).toBeInTheDocument()

    // Le détail interne ne doit jamais être affiché.
    expect(
      screen.queryByText('Internal database error'),
    ).not.toBeInTheDocument()
  })

  it('displays an empty state when no departments are available', async () => {
    vi.mocked(getDepartments).mockResolvedValue(createResponse([]))

    renderEmployeesPage()

    expect(
      await screen.findByText('No departments available.'),
    ).toBeInTheDocument()
  })

  it('displays an empty state when no positions are available', async () => {
    vi.mocked(getPositions).mockResolvedValue(createResponse([]))

    renderEmployeesPage()

    // Attendre que les départements soient chargés.
    await screen.findByRole('option', { name: 'Engineering' })

    fireEvent.change(screen.getByLabelText('Filter by department'), {
      target: { value: '2' },
    })

    expect(
      await screen.findByText(
        'No positions available for this department.',
      ),
    ).toBeInTheDocument()
  })
})
