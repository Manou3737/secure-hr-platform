import type { SecurityMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface SecurityOverviewProps {
  data: SecurityMetrics
}

export default function SecurityOverview({ data }: SecurityOverviewProps) {
  const maxEventCount = Math.max(
    ...data.events.distribution.map((item) => item.count),
    1,
  )

  const maxDailyCount = Math.max(
    ...data.daily_activity.map((item) => item.count),
    1,
  )

  const detections = [
    { label: 'Brute force', value: data.detections.brute_force },
    { label: 'Suspicious IP', value: data.detections.suspicious_ip },
    { label: 'Unauthorized access', value: data.detections.unauthorized_access },
    { label: 'Privilege escalation', value: data.detections.privilege_escalation },
  ]

  return (
    <section aria-labelledby="security-heading" className="space-y-5">
      <div>
        <h2
          id="security-heading"
          className="text-xl font-semibold text-slate-900"
        >
          Security overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Security activity and detections over the last {data.period_days} days.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total events"
          value={data.overview.total_events}
          description="Recorded security events"
        />
        <StatCard
          label="Successful logins"
          value={data.overview.login_success}
          description="Successful authentication events"
        />
        <StatCard
          label="Failed logins"
          value={data.overview.login_failed}
          description="Failed authentication attempts"
        />
        <StatCard
          label="Distinct IPs"
          value={data.sources.distinct_ips}
          description="Unique IP addresses observed"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900">
            Security detections
          </h3>

          <div className="mt-4 space-y-4">
            {detections.map((item) => (
              <div key={item.label}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="text-slate-600">{item.label}</span>
                  <span className="font-semibold tabular-nums text-slate-900">
                    {item.value}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900">
            Security sources
          </h3>

          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Distinct IPs</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {data.sources.distinct_ips}
              </p>
            </div>

            <div className="rounded-lg bg-slate-50 p-4">
              <p className="text-sm text-slate-500">Distinct users</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900">
                {data.sources.distinct_users}
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900">
            Event distribution
          </h3>

          {data.events.distribution.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No security events available.
            </p>
          ) : (
            <div className="mt-4 space-y-4">
              {data.events.distribution.map((item) => (
                <div key={item.event_type}>
                  <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                    <span className="break-all text-slate-600">
                      {item.event_type}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-900">
                      {item.count}
                    </span>
                  </div>

                  <div
                    className="h-2 overflow-hidden rounded-full bg-slate-100"
                    role="progressbar"
                    aria-label={`${item.event_type} event count`}
                    aria-valuenow={item.count}
                    aria-valuemin={0}
                    aria-valuemax={maxEventCount}
                  >
                    <div
                      className="h-full rounded-full bg-blue-600"
                      style={{
                        width: `${Math.min((item.count / maxEventCount) * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-base font-semibold text-slate-900">
            Daily security activity
          </h3>

          {data.daily_activity.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No daily security activity available.
            </p>
          ) : (
            <div className="mt-4 space-y-4">
              {data.daily_activity.map((item) => (
                <div key={item.created_at__date}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="text-slate-600">
                      {item.created_at__date}
                    </span>
                    <span className="font-semibold tabular-nums text-slate-900">
                      {item.count}
                    </span>
                  </div>

                  <div
                    className="h-2 overflow-hidden rounded-full bg-slate-100"
                    role="progressbar"
                    aria-label={`${item.created_at__date} activity count`}
                    aria-valuenow={item.count}
                    aria-valuemin={0}
                    aria-valuemax={maxDailyCount}
                  >
                    <div
                      className="h-full rounded-full bg-indigo-600"
                      style={{
                        width: `${Math.min((item.count / maxDailyCount) * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-slate-900">
          Recent security events
        </h3>

        {data.recent_events.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">
            No recent security events.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {data.recent_events.map((event) => (
              <div
                key={event.id}
                className="flex flex-col gap-1 border-b border-slate-100 pb-3 last:border-0 last:pb-0"
              >
                <p className="text-sm font-medium text-slate-900">
                  {event.event_type}
                </p>
                <p className="text-xs text-slate-500">
                  {new Date(event.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
