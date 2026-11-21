import { useAuth } from '../auth/useAuth'
import StatusBadge from '../components/ui/StatusBadge'

export default function ProfilePage() {
  const { user } = useAuth()

  if (!user) {
    return null
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          My Profile
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          View your account information.
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center gap-4 border-b border-slate-100 pb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 text-2xl font-bold text-blue-700">
            {user.name.charAt(0).toUpperCase()}
          </div>

          <div className="min-w-0 flex-1">
            <h2 className="break-words text-lg font-semibold text-slate-900">
              {user.name}
            </h2>
            <p className="break-all text-sm text-slate-500">
              {user.email}
            </p>
          </div>
        </div>

        <div className="grid gap-6 pt-6 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Full name
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {user.name}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Email address
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {user.email}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Account role
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {user.role.replaceAll('_', ' ')}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Account status
            </p>
            <div className="mt-1">
              <StatusBadge status={user.is_active ? 'ACTIVE' : 'INACTIVE'} />
            </div>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Email verification
            </p>
            <div className="mt-1">
              <StatusBadge
                status={user.email_verified ? 'VERIFIED' : 'PENDING'}
              />
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
