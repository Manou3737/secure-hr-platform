import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import FilterBar from './FilterBar'
import type { FilterConfig } from './FilterBar'

const filters: FilterConfig[] = [
  {
    key: 'department',
    label: 'Department',
    options: [
      { label: 'Human Resources', value: 'HR' },
      { label: 'Finance', value: 'FINANCE' },
    ],
  },
  {
    key: 'status',
    label: 'Status',
    options: [
      { label: 'Active', value: 'ACTIVE' },
      { label: 'Inactive', value: 'INACTIVE' },
    ],
  },
]

describe('FilterBar', () => {
  it('renders filter labels and available options', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ department: '', status: '' }}
        onChange={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Department')).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Human Resources' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Finance' }),
    ).toBeInTheDocument()
  })

  it('displays the currently selected filter values', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ department: 'HR', status: 'ACTIVE' }}
        onChange={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    expect(screen.getByLabelText('Department')).toHaveValue('HR')
    expect(screen.getByLabelText('Status')).toHaveValue('ACTIVE')
  })

  it('calls onChange with the selected filter key and value', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    render(
      <FilterBar
        filters={filters}
        values={{ department: '', status: '' }}
        onChange={onChange}
        onReset={vi.fn()}
      />,
    )

    await user.selectOptions(
      screen.getByLabelText('Department'),
      'FINANCE',
    )

    expect(onChange).toHaveBeenCalledWith('department', 'FINANCE')
  })

  it('disables Reset filters when no filter is active', () => {
    render(
      <FilterBar
        filters={filters}
        values={{ department: '', status: '' }}
        onChange={vi.fn()}
        onReset={vi.fn()}
      />,
    )

    expect(
      screen.getByRole('button', { name: 'Reset filters' }),
    ).toBeDisabled()
  })

  it('enables Reset filters and calls onReset when clicked', async () => {
    const user = userEvent.setup()
    const onReset = vi.fn()

    render(
      <FilterBar
        filters={filters}
        values={{ department: 'HR', status: '' }}
        onChange={vi.fn()}
        onReset={onReset}
      />,
    )

    const resetButton = screen.getByRole('button', {
      name: 'Reset filters',
    })

    expect(resetButton).toBeEnabled()

    await user.click(resetButton)

    expect(onReset).toHaveBeenCalledTimes(1)
  })
})
