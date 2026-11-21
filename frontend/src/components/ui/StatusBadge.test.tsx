
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it.each([
    'ACTIVE',
    'VERIFIED',
    'APPROVED',
    'PENDING',
    'PENDING_REVIEW',
    'PENDING_SCAN',
    'REJECTED',
    'QUARANTINED',
    'INACTIVE',
    'ARCHIVED',
  ])('renders the %s status', (status) => {
    render(<StatusBadge status={status} />)

    expect(
      screen.getByText(status.replaceAll('_', ' ')),
    ).toBeInTheDocument()
  })

  it('normalizes lowercase statuses', () => {
    render(<StatusBadge status="active" />)

    expect(screen.getByText('ACTIVE')).toBeInTheDocument()
  })

  it('removes surrounding whitespace', () => {
    render(<StatusBadge status="  pending  " />)

    expect(screen.getByText('PENDING')).toBeInTheDocument()
  })

  it('formats underscores as spaces', () => {
    render(<StatusBadge status="PENDING_REVIEW" />)

    expect(screen.getByText('PENDING REVIEW')).toBeInTheDocument()
  })

  it('renders an unknown status with the default style', () => {
    render(<StatusBadge status="CUSTOM_STATUS" />)

    expect(screen.getByText('CUSTOM STATUS')).toBeInTheDocument()
  })
})
