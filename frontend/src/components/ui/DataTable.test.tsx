import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import DataTable from './DataTable'
import type { TableColumn } from './DataTable'

interface Employee {
  id: number
  name: string
  department: string
  position?: string | null
}

const employees: Employee[] = [
  { id: 1, name: 'Alice Martin', department: 'HR' },
  { id: 2, name: 'Bob Smith', department: 'Finance' },
  { id: 3, name: 'Charlie Brown', department: 'IT' },
]

const columns: TableColumn<Employee>[] = [
  { key: 'name', header: 'Name' },
  { key: 'department', header: 'Department' },
]

function renderTable(
  data = employees,
  pageSize = 10,
  customColumns = columns,
) {
  return render(
    <DataTable
      columns={customColumns}
      data={data}
      rowKey={(row) => row.id}
      pageSize={pageSize}
    />,
  )
}

describe('DataTable', () => {
  it('renders column headers and records', () => {
    renderTable()

    expect(screen.getByRole('columnheader', { name: 'Name' }))
      .toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Department' }))
      .toBeInTheDocument()

    expect(screen.getByText('Alice Martin')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.getByText('Charlie Brown')).toBeInTheDocument()
  })

  it('filters records using a case-insensitive search', async () => {
    const user = userEvent.setup()

    renderTable()

    await user.type(
      screen.getByRole('searchbox', { name: 'Search records' }),
      'finance',
    )

    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.queryByText('Alice Martin')).not.toBeInTheDocument()
    expect(screen.queryByText('Charlie Brown')).not.toBeInTheDocument()
    expect(screen.getByText('1 record(s) found')).toBeInTheDocument()
  })

  it('displays a custom empty message when no records match', async () => {
    const user = userEvent.setup()

    render(
      <DataTable
        columns={columns}
        data={employees}
        rowKey={(row) => row.id}
        emptyMessage="No matching employees."
      />,
    )

    await user.type(
      screen.getByRole('searchbox', { name: 'Search records' }),
      'unknown',
    )

    expect(
      screen.getByText('No matching employees.'),
    ).toBeInTheDocument()
  })

  it('displays the default empty message when data is empty', () => {
    renderTable([])

    expect(screen.getByText('No records found.')).toBeInTheDocument()
    expect(screen.getByText('0 record(s) found')).toBeInTheDocument()
  })

  it('navigates between pages', async () => {
    const user = userEvent.setup()

    renderTable(employees, 2)

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Alice Martin')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.queryByText('Charlie Brown')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
    expect(screen.getByText('Charlie Brown')).toBeInTheDocument()
    expect(screen.queryByText('Alice Martin')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Alice Martin')).toBeInTheDocument()
  })

  it('disables pagination buttons at the page boundaries', () => {
    renderTable(employees, 2)

    expect(screen.getByRole('button', { name: 'Previous' }))
      .toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' }))
      .toBeEnabled()
  })

  it('resets pagination to the first page when searching', async () => {
    const user = userEvent.setup()

    renderTable(employees, 2)

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()

    await user.type(
      screen.getByRole('searchbox', { name: 'Search records' }),
      'Alice',
    )

    expect(screen.getByText('Page 1 of 1')).toBeInTheDocument()
    expect(screen.getByText('Alice Martin')).toBeInTheDocument()
  })

  it('displays a dash for null or undefined cell values', () => {
    const data: Employee[] = [
      {
        id: 4,
        name: 'David Green',
        department: 'HR',
        position: null,
      },
    ]

    const testColumns: TableColumn<Employee>[] = [
      ...columns,
      { key: 'position', header: 'Position' },
    ]

    renderTable(data, 10, testColumns)

    const row = screen.getByRole('row', { name: /David Green/ })

    expect(within(row).getByText('—')).toBeInTheDocument()
  })

  it('uses a custom renderer for a column', () => {
    const customColumns: TableColumn<Employee>[] = [
      {
        key: 'name',
        header: 'Employee',
        render: (row) => <strong>{row.name.toUpperCase()}</strong>,
      },
    ]

    renderTable(employees, 10, customColumns)

    expect(screen.getByText('ALICE MARTIN')).toBeInTheDocument()
  })
})

describe('DataTable server pagination', () => {
  it('displays server data and the total server record count', () => {
    render(
      <DataTable
        columns={columns}
        data={employees.slice(0, 2)}
        rowKey={(row) => row.id}
        pageSize={10}
        serverPagination={{
          page: 1,
          totalCount: 25,
          onPageChange: () => {},
        }}
      />,
    )

    expect(screen.getByText('25 record(s) found')).toBeInTheDocument()
    expect(screen.getByText('Showing 1 to 10 of 25 records'))
      .toBeInTheDocument()
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()

    expect(screen.getByText('Alice Martin')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  })

  it('calls onPageChange with the next server page', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()

    render(
      <DataTable
        columns={columns}
        data={employees.slice(0, 2)}
        rowKey={(row) => row.id}
        pageSize={2}
        serverPagination={{
          page: 1,
          totalCount: 5,
          onPageChange,
        }}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(onPageChange).toHaveBeenCalledWith(2)
    expect(onPageChange).toHaveBeenCalledTimes(1)
  })

  it('calls onPageChange with the previous server page', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()

    render(
      <DataTable
        columns={columns}
        data={[employees[2]]}
        rowKey={(row) => row.id}
        pageSize={2}
        serverPagination={{
          page: 2,
          totalCount: 5,
          onPageChange,
        }}
      />,
    )

    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Previous' }))

    expect(onPageChange).toHaveBeenCalledWith(1)
    expect(onPageChange).toHaveBeenCalledTimes(1)
  })

  it('disables server pagination buttons at page boundaries', () => {
    const onPageChange = vi.fn()

    const { rerender } = render(
      <DataTable
        columns={columns}
        data={employees.slice(0, 2)}
        rowKey={(row) => row.id}
        pageSize={2}
        serverPagination={{
          page: 1,
          totalCount: 5,
          onPageChange,
        }}
      />,
    )

    expect(screen.getByRole('button', { name: 'Previous' }))
      .toBeDisabled()
    expect(screen.getByRole('button', { name: 'Next' }))
      .toBeEnabled()

    rerender(
      <DataTable
        columns={columns}
        data={[employees[2]]}
        rowKey={(row) => row.id}
        pageSize={2}
        serverPagination={{
          page: 3,
          totalCount: 5,
          onPageChange,
        }}
      />,
    )

    expect(screen.getByRole('button', { name: 'Previous' }))
      .toBeEnabled()
    expect(screen.getByRole('button', { name: 'Next' }))
      .toBeDisabled()
  })
})

describe('DataTable accessibility and robustness', () => {
  it('provides an accessible table name and caption', () => {
    renderTable()

    expect(
      screen.getByRole('region', { name: 'Data table' }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('table', { name: 'Records table' }),
    ).toBeInTheDocument()
  })

  it('identifies the pagination navigation accessibly', () => {
    renderTable()

    expect(
      screen.getByRole('navigation', { name: 'Table pagination' }),
    ).toBeInTheDocument()
  })

  it('uses the default page size when pageSize is zero', () => {
    const data = Array.from({ length: 11 }, (_, index) => ({
      id: index + 1,
      name: `Employee ${index + 1}`,
      department: 'HR',
    }))

    renderTable(data, 0)

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Employee 10')).toBeInTheDocument()
    expect(screen.queryByText('Employee 11')).not.toBeInTheDocument()
  })

  it('uses an integer page size when pageSize is fractional', () => {
    renderTable(employees, 2.5)

    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Bob Smith')).toBeInTheDocument()
    expect(screen.queryByText('Charlie Brown')).not.toBeInTheDocument()
  })
})
