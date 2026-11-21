import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ErrorMessage from './ErrorMessage'

describe('ErrorMessage', () => {
  it('renders the supplied error message', () => {
    render(<ErrorMessage message="Unable to load employees." />)

    expect(
      screen.getByText('Unable to load employees.'),
    ).toBeInTheDocument()
  })

  it('announces the error through an alert', () => {
    render(<ErrorMessage message="Request failed." />)

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Request failed.',
    )
  })

  it('renders nothing when the message is empty', () => {
    const { container } = render(<ErrorMessage message="" />)

    expect(container.firstChild).toBeNull()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not expose technical details unless supplied as the message', () => {
    render(
      <ErrorMessage message="Unable to load employees. Please try again." />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to load employees. Please try again.',
    )
  })
})
