import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Toast from './Toast'
import { ToastProvider } from './ToastProvider'
import { useToast } from './useToast'

function ToastTestTrigger() {
  const { showToast } = useToast()

  return (
    <div>
      <button onClick={() => showToast('Success message')}>
        Show success
      </button>

      <button onClick={() => showToast('Error message', 'error')}>
        Show error
      </button>

      <button onClick={() => showToast('Info message', 'info')}>
        Show info
      </button>
    </div>
  )
}

describe('Toast', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('displays a success notification with status role', () => {
    render(
      <Toast
        type="success"
        message="Saved successfully"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'Saved successfully',
    )
  })

  it('displays an information notification with status role', () => {
    render(
      <Toast
        type="info"
        message="Information message"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent(
      'Information message',
    )
  })

  it('displays an error notification with alert role', () => {
    render(
      <Toast
        type="error"
        message="Something went wrong"
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Something went wrong',
    )
  })

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn()

    render(
      <Toast
        type="success"
        message="Notification"
        onClose={onClose}
      />,
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Close notification' }),
    )

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('automatically closes after four seconds', () => {
    vi.useFakeTimers()

    const onClose = vi.fn()

    render(
      <Toast
        type="success"
        message="Temporary notification"
        onClose={onClose}
      />,
    )

    act(() => {
      vi.advanceTimersByTime(3999)
    })

    expect(onClose).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1)
    })

    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('ToastProvider', () => {
  it('displays a success notification using the default type', () => {
    render(
      <ToastProvider>
        <ToastTestTrigger />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Show success' }))

    expect(screen.getByRole('status')).toHaveTextContent(
      'Success message',
    )
  })

  it('displays error and information notifications', () => {
    render(
      <ToastProvider>
        <ToastTestTrigger />
      </ToastProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Show error' }))

    expect(screen.getByRole('alert')).toHaveTextContent('Error message')

    fireEvent.click(screen.getByRole('button', { name: 'Show info' }))

    expect(screen.getByRole('status')).toHaveTextContent('Info message')
  })
})
