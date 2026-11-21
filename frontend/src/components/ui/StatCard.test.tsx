
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StatCard from './StatCard'

describe('StatCard', () => {
  it('renders the label and numeric value', () => {
    render(
      <StatCard
        label="Employees"
        value={125}
      />,
    )

    expect(screen.getByText('Employees')).toBeInTheDocument()
    expect(screen.getByText('125')).toBeInTheDocument()
  })

  it('renders a zero value correctly', () => {
    render(
      <StatCard
        label="Open Positions"
        value={0}
      />,
    )

    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('renders the description when provided', () => {
    render(
      <StatCard
        label="Employees"
        value={125}
        description="Total workforce"
      />,
    )

    expect(screen.getByText('Total workforce')).toBeInTheDocument()
  })

  it('renders the icon when provided', () => {
    render(
      <StatCard
        label="Employees"
        value={125}
        icon="👥"
      />,
    )

    expect(screen.getByText('👥')).toBeInTheDocument()
  })

  it('does not render an icon when omitted', () => {
    render(
      <StatCard
        label="Employees"
        value={125}
      />,
    )

    expect(screen.queryByText('👥')).not.toBeInTheDocument()
  })
})
