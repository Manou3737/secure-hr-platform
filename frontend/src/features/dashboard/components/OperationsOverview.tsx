import type { OperationsMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface OperationsOverviewProps {
  data: OperationsMetrics
}

export default function OperationsOverview({
  data,
}: OperationsOverviewProps) {
  const workflowOutcomes = [
    { label: 'Successful', value: data.workflows.success },
    { label: 'Failed', value: data.workflows.failure },
    { label: 'Denied', value: data.workflows.denied },
  ]

  const maxEventCount = Math.max(
    ...data.events.distribution.map((item) => item.count),
    1,
  )

  const maxDailyCount = Math.max(
    ...data.daily_activity.map((item) => item.count),
    1,
  )

  return (
    <section
      aria-labelledby="operations-heading"
      className="space-y-5"
    >
      <div>
        <h2
          id="operations-heading"
          className="text-lg font-semibold text-slate-900"
        >
          Operations overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Workflow execution and operational activity over the last{' '}
          {data.period_days} days.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total workflows"
          value={data.workflows.total}
          description="Workflow executions"
          icon="⚙️"
        />

        <StatCard
          label="Successful workflows"
          value={data.workflows.success}
          description="Completed successfully"
          icon="✓"
        />

        <StatCard
          label="Failed workflows"
          value={data.workflows.failure}
          description="Execution failures"
          icon="⚠️"
        />

        <StatCard
          label="Failed notifications"
          value={data.notifications.failed}
          description="Notifications not delivered"
          icon="📨"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Workflow outcomes
          </h3>

          <div className="mt-4 space-y-4">
            {workflowOutcomes.map((item) => {
              const percentage =
                data.workflows.total > 0
                  ? Math.min(
                      (item.value / data.workflows.total) * 100,
                      100,
                    )
                  : 0

              return (
                <div key={item.label}>
                  <div className="mb-1 flex justify-between text-sm">
                    <span className="text-slate-600">{item.label}</span>
                    <span className="font-medium tabular-nums text-slate-900">
                      {item.value}
                    </span>
                  </div>

                  <div
                    className="h-2 overflow-hidden rounded-full bg-slate-100"
                    role="progressbar"
                    aria-label={`${item.label} workflows`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={percentage}
                  >
                    <div
                      className="h-full rounded-full bg-blue-600"
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Notifications by type
          </h3>

          {data.notifications.by_type.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No notification breakdown available.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {data.notifications.by_type.map((item) => (
                <li
                  key={item.details__notification_type}
                  className="flex items-center justify-between gap-3 py-3 text-sm"
                >
                  <span className="break-all text-slate-600">
                    {item.details__notification_type}
                  </span>
                  <span className="font-semibold tabular-nums text-slate-900">
                    {item.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Event distribution
          </h3>

          {data.events.distribution.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No operational events available.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {data.events.distribution.map((item) => (
                <li key={item.event_type}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="break-all text-slate-600">
                      {item.event_type}
                    </span>
                    <span className="font-medium tabular-nums text-slate-900">
                      {item.count}
                    </span>
                  </div>

                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{
                        width: `${(item.count / maxEventCount) * 100}%`,
                      }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Daily operational activity
          </h3>

          {data.daily_activity.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No daily activity available.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {data.daily_activity.map((item) => (
                <li
                  key={item.created_at__date}
                  className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3 text-sm"
                >
                  <span className="text-slate-500">
                    {item.created_at__date}
                  </span>

                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{
                        width: `${(item.count / maxDailyCount) * 100}%`,
                      }}
                    />
                  </div>

                  <span className="text-right font-medium tabular-nums text-slate-900">
                    {item.count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  )
}
