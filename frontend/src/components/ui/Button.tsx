
import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger'
}

const variants = {
  primary:
    'border border-blue-700 bg-blue-700 text-white hover:border-blue-800 hover:bg-blue-800 active:bg-blue-900',
  secondary:
    'border border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50 active:bg-slate-100',
  danger:
    'border border-red-600 bg-red-600 text-white hover:border-red-700 hover:bg-red-700 active:bg-red-800',
}

export default function Button({
  variant = 'primary',
  className = '',
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={[
        'inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2',
        'text-sm font-semibold shadow-sm',
        'transition-colors duration-150',
        'focus-visible:outline-none focus-visible:ring-2',
        'focus-visible:ring-blue-500 focus-visible:ring-offset-2',
        'disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
        className,
      ].join(' ')}
      {...props}
    >
      {children}
    </button>
  )
}
