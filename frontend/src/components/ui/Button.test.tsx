
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import Button from './Button'

describe('Button', () => {
  it('renders its children', () => {
    render(<Button>Save changes</Button>)

    expect(
      screen.getByRole('button', { name: 'Save changes' }),
    ).toBeInTheDocument()
  })

  it('uses the primary variant by default', () => {
    render(<Button>Save</Button>)

    expect(screen.getByRole('button')).toHaveClass('bg-blue-700')
  })

  it('supports the secondary variant', () => {
    render(<Button variant="secondary">Cancel</Button>)

    expect(screen.getByRole('button')).toHaveClass('bg-white')
  })

  it('supports the danger variant', () => {
    render(<Button variant="danger">Delete</Button>)

    expect(screen.getByRole('button')).toHaveClass('bg-red-600')
  })

  it('preserves custom class names', () => {
    render(<Button className="w-full">Sign in</Button>)

    expect(screen.getByRole('button')).toHaveClass('w-full')
  })

  it('calls onClick when clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(<Button onClick={onClick}>Save</Button>)

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not trigger onClick when disabled', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(
      <Button disabled onClick={onClick}>
        Save
      </Button>,
    )

    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onClick).not.toHaveBeenCalled()
  })

  it('preserves the submit button type', () => {
    render(<Button type="submit">Sign in</Button>)

    expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
  })
})
