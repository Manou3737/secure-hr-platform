import { useId, type InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  error?: string
}

export default function Input({
  label,
  error,
  id,
  className = '',
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...props
}: InputProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const hasError = Boolean(error)
  const errorId = `${inputId}-error`

  const describedBy = [
    ariaDescribedBy,
    hasError ? errorId : undefined,
  ]
    .filter(Boolean)
    .join(' ') || undefined

  return (
    <div className="min-w-0 space-y-1">
      <label
        htmlFor={inputId}
        className="block text-sm font-medium text-slate-700"
      >
        {label}
      </label>

      <input
        {...props}
        id={inputId}
        aria-invalid={hasError ? true : ariaInvalid}
        aria-describedby={describedBy}
        className={[
          'w-full rounded-lg border bg-white px-3 py-2 text-sm text-slate-900',
          'outline-none transition-colors duration-150',
          'focus-visible:ring-2 focus-visible:ring-offset-1',
          hasError
            ? 'border-red-500 focus-visible:border-red-600 focus-visible:ring-red-200'
            : 'border-slate-300 focus-visible:border-blue-600 focus-visible:ring-blue-100',
          'disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500',
          className,
        ].join(' ')}
      />

      {hasError && (
        <p
          id={errorId}
          className="text-sm text-red-600"
        >
          {error}
        </p>
      )}
    </div>
  )
}
