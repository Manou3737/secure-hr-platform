import {
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import Toast, { type ToastType } from './Toast'

import { ToastContext } from './toast-context'

interface ToastProviderProps {
  children: ReactNode
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toast, setToast] = useState<{
    message: string
    type: ToastType
  } | null>(null)

  const showToast = useCallback(
    (message: string, type: ToastType = 'success') => {
      setToast({ message, type })
    },
    [],
  )

  const contextValue = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={contextValue}>
      {children}

      {toast && (
        <Toast
          type={toast.type}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}
    </ToastContext.Provider>
  )
}
