import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Input from './Input'

describe('Input', () => {
  it('renders a label associated with its input', () => {
    render(<Input label="Email" type="email" />)

    const input = screen.getByLabelText('Email')

    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute('type', 'email')
    expect(input.id).toBeTruthy()
  })

  it('uses a supplied id when provided', () => {
    render(<Input label="Email" id="user-email" />)

    const input = screen.getByLabelText('Email')

    expect(input).toHaveAttribute('id', 'user-email')
    expect(
      screen.getByText('Email').closest('label'),
    ).toHaveAttribute('for', 'user-email')
  })

  it('generates unique ids for multiple inputs', () => {
    render(
      <>
        <Input label="Email" />
        <Input label="Password" />
      </>,
    )

    const email = screen.getByLabelText('Email')
    const password = screen.getByLabelText('Password')

    expect(email.id).toBeTruthy()
    expect(password.id).toBeTruthy()
    expect(email.id).not.toBe(password.id)
  })

  it('displays an error and associates it with the input', () => {
    render(
      <Input
        label="Email"
        error="Enter a valid email address."
      />,
    )

    const input = screen.getByLabelText('Email')
    const error = screen.getByText('Enter a valid email address.')

    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute(
      'aria-describedby',
      `${input.id}-error`,
    )
    expect(error).toHaveAttribute('id', `${input.id}-error`)
  })

  it('preserves a custom aria-describedby when an error is present', () => {
    render(
      <>
        <p id="email-help">Use your work email address.</p>
        <Input
          label="Email"
          aria-describedby="email-help"
          error="Email is required."
        />
      </>,
    )

    const input = screen.getByLabelText('Email')

    expect(input.getAttribute('aria-describedby')).toBe(
      `email-help ${input.id}-error`,
    )
  })

  it('preserves a custom aria-invalid value when there is no error', () => {
    render(
      <Input
        label="Email"
        aria-invalid="false"
      />,
    )

    expect(screen.getByLabelText('Email')).toHaveAttribute(
      'aria-invalid',
      'false',
    )
  })

  it('forwards standard HTML input attributes', () => {
    render(
      <Input
        label="Email"
        type="email"
        placeholder="name@example.com"
        autoComplete="username"
        required
        disabled
      />,
    )

    const input = screen.getByLabelText('Email')

    expect(input).toHaveAttribute('type', 'email')
    expect(input).toHaveAttribute('placeholder', 'name@example.com')
    expect(input).toHaveAttribute('autocomplete', 'username')
    expect(input).toBeRequired()
    expect(input).toBeDisabled()
  })

  it('forwards custom class names', () => {
    render(
      <Input
        label="Email"
        className="custom-input-class"
      />,
    )

    expect(screen.getByLabelText('Email')).toHaveClass(
      'custom-input-class',
    )
  })

  it('handles user input through onChange', async () => {
    const user = userEvent.setup()
    const handleChange = vi.fn()

    render(
      <Input
        label="Email"
        onChange={handleChange}
      />,
    )

    await user.type(screen.getByLabelText('Email'), 'user@example.com')

    expect(handleChange).toHaveBeenCalled()
    expect(screen.getByLabelText('Email')).toHaveValue('user@example.com')
  })
})
