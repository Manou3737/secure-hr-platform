import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ConfirmDialog from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('does not render when closed', () => {
    render(
      <ConfirmDialog
        open={false}
        title="Delete employee"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('renders the title and message when open', () => {
    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="This action cannot be undone."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('Delete employee')).toBeInTheDocument()
    expect(
      screen.getByText('This action cannot be undone.'),
    ).toBeInTheDocument()
  })

  it('calls onConfirm when confirmation is clicked', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()

    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="Are you sure?"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when cancellation is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when Escape is pressed', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )

    await user.keyboard('{Escape}')

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when the backdrop is clicked', async () => {
    const user = userEvent.setup()
    const onCancel = vi.fn()

    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="Are you sure?"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    )

    await user.click(screen.getByRole('alertdialog').parentElement!)

    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('supports custom labels and danger variant', () => {
    render(
      <ConfirmDialog
        open
        title="Delete employee"
        message="Are you sure?"
        confirmLabel="Delete"
        cancelLabel="Keep"
        variant="danger"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Keep' })).toBeInTheDocument()
  })
})
