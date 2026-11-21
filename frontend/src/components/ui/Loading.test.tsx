import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Loading from './Loading'

describe('Loading', () => {
  it('renders the default loading message', () => {
    render(<Loading />)

    expect(screen.getByRole('status')).toHaveTextContent('Loading...')
  })

  it('renders a custom loading message', () => {
    render(<Loading message="Loading employees..." />)

    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading employees...',
    )
  })

  it('provides an accessible status role', () => {
    render(<Loading message="Checking authentication..." />)

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('hides the decorative spinner from assistive technology', () => {
    const { container } = render(<Loading />)

    const spinner = container.querySelector('[aria-hidden="true"]')

    expect(spinner).toBeInTheDocument()
    expect(spinner).toHaveClass('animate-spin')
    expect(spinner).toHaveClass('motion-reduce:animate-none')
  })
})
