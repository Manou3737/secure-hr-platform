interface LoadingProps {
  message?: string
}

export default function Loading({
  message = 'Loading...',
}: LoadingProps) {
  return (
    <div
      role="status"
      className="flex min-h-32 items-center justify-center gap-3 text-slate-600"
    >
      <span
        className="h-5 w-5 animate-spin rounded-full border-2 border-blue-700 border-t-transparent motion-reduce:animate-none"
        aria-hidden="true"
      />
      <span>{message}</span>
    </div>
  )
}
