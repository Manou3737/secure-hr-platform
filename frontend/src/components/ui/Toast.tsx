import { useEffect } from 'react'

export type ToastType = 'success' | 'error' | 'info'

interface ToastProps {
  type: ToastType
  message: string
  onClose: () => void
}

const styles: Record<ToastType, string> = {
  success: 'border-green-200 bg-green-50 text-green-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  info: 'border-blue-200 bg-blue-50 text-blue-800',
}

export default function Toast({ type, message, onClose }: ToastProps) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, 4000)
    return () => window.clearTimeout(timer)
  }, [onClose])

  return (
    <div
      role={type === 'error' ? 'alert' : 'status'}
      className={`fixed right-4 top-4 z-50 flex max-w-sm items-center gap-3 rounded-lg border px-4 py-3 shadow-lg ${styles[type]}`}
    >
      <p className="flex-1 text-sm font-medium">{message}</p>

      <button
        type="button"
        onClick={onClose}
        aria-label="Close notification"
        className="text-lg leading-none opacity-70 hover:opacity-100"
      >
        ×
      </button>
    </div>
  )
}
