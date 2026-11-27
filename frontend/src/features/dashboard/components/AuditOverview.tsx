import type { AuditMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface AuditOverviewProps {
  data: AuditMetrics
}

function formatTimestamp(timestamp: string) {
  return new Date(timestamp).toLocaleString()
}

export default function AuditOverview({ data }: AuditOverviewProps) {
  const workflowOutcomeTotal = Object.values(data.workflows.outcomes).reduce(
    (total, count) => total + count,
    0,
  )

  const maxGeneralAuditCount = Math.max(
    ...data.general_audit.distribution.map((item) => item.count),
    1,
  )

  const maxDocumentAccessCount = Math.max(
    ...data.document_access.distribution.map((item) => item.count),
    1,
  )

  const maxWorkflowCount = Math.max(
    ...data.workflows.distribution.map((item) => item.count),
    1,
  )

  const dailyActivity = [
    ...data.daily_activity.general_audit.map((item) => ({
      type: 'General audit',
      date: item.created_at__date,
      count: item.count,
    })),
    ...data.daily_activity.document_access.map((item) => ({
      type: 'Document access',
      date: item.created_at__date,
      count: item.count,
    })),
    ...data.daily_activity.workflow.map((item) => ({
      type: 'Workflow',
      date: item.created_at__date,
      count: item.count,
    })),
  ].sort((a, b) => a.date.localeCompare(b.date))

  const maxDailyCount = Math.max(...dailyActivity.map((item) => item.count), 1)

  const recentEvents = [
    ...data.recent_events.general_audit.map((item) => ({
      type: 'General audit',
      event: item.action,
      timestamp: item.created_at,
    })),
    ...data.recent_events.document_access.map((item) => ({
      type: 'Document access',
      event: item.action,
      timestamp: item.created_at,
    })),
    ...data.recent_events.workflow.map((item) => ({
      type: 'Workflow',
      event: item.event_type,
      timestamp: item.created_at,
    })),
  ].sort((a, b) => b.timestamp.localeCompare(a.timestamp))

  return (
    <section aria-labelledby="audit-heading" className="space-y-5">
      <div>
        <h2 id="audit-heading" className="text-lg font-semibold text-slate-900">
          Audit overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Audit activity over the last {data.period_days} days.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total audit entries"
          value={data.overview.total_entries}
          description="All recorded audit entries"
          icon="📋"
        />
        <StatCard
          label="General audit entries"
          value={data.overview.general_audit_entries}
          description="General activity records"
          icon="📝"
        />
        <StatCard
          label="Document access entries"
          value={data.overview.document_access_entries}
          description="Document access records"
          icon="📄"
        />
        <StatCard
          label="Workflow entries"
          value={data.overview.workflow_entries}
          description="Workflow audit records"
          icon="⚙️"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            General audit actions
          </h3>

          {data.general_audit.distribution.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No general audit actions available.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {data.general_audit.distribution.map((item) => (
                <li key={item.action}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="break-all text-slate-600">
                      {item.action}
                    </span>
                    <span className="font-medium tabular-nums text-slate-900">
                      {item.count}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-blue-600"
                      style={{
                        width: `${(item.count / maxGeneralAuditCount) * 100}%`,
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
            Document access activity
          </h3>

          <div className="mt-4 rounded-lg bg-amber-50 p-3">
            <p className="text-sm text-amber-800">Access denied</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-900">
              {data.document_access.access_denied}
            </p>
          </div>

          {data.document_access.distribution.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No document access activity available.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {data.document_access.distribution.map((item) => (
                <li key={item.action}>
                  <div className="mb-1 flex justify-between gap-3 text-sm">
                    <span className="break-all text-slate-600">
                      {item.action}
                    </span>
                    <span className="font-medium tabular-nums text-slate-900">
                      {item.count}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-indigo-500"
                      style={{
                        width: `${(item.count / maxDocumentAccessCount) * 100}%`,
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
            Workflow event distribution
          </h3>

          {data.workflows.distribution.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No workflow events available.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {data.workflows.distribution.map((item) => (
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
                      className="h-full rounded-full bg-violet-500"
                      style={{
                        width: `${(item.count / maxWorkflowCount) * 100}%`,
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
            Workflow outcomes
          </h3>

          {Object.keys(data.workflows.outcomes).length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No workflow outcomes available.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {Object.entries(data.workflows.outcomes).map(([outcome, count]) => {
                const percentage =
                  workflowOutcomeTotal > 0
                    ? Math.min((count / workflowOutcomeTotal) * 100, 100)
                    : 0

                return (
                  <li key={outcome}>
                    <div className="mb-1 flex justify-between gap-3 text-sm">
                      <span className="text-slate-600">{outcome}</span>
                      <span className="font-medium tabular-nums text-slate-900">
                        {count}
                      </span>
                    </div>
                    <div
                      className="h-2 overflow-hidden rounded-full bg-slate-100"
                      role="progressbar"
                      aria-label={`${outcome} workflow outcomes`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={percentage}
                    >
                      <div
                        className="h-full rounded-full bg-emerald-500"
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-900">
            Daily audit activity
          </h3>

          {dailyActivity.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No daily audit activity available.
            </p>
          ) : (
            <ul className="mt-4 space-y-3">
              {dailyActivity.map((item, index) => (
                <li
                  key={`${item.type}-${item.date}-${index}`}
                  className="grid grid-cols-[6rem_6rem_1fr_2rem] items-center gap-3 text-sm"
                >
                  <span className="text-slate-500">{item.date}</span>
                  <span className="text-slate-600">{item.type}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-cyan-500"
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

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-900">
            Recent audit events
          </h3>

          {recentEvents.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">
              No recent audit events.
            </p>
          ) : (
            <ul className="mt-4 divide-y divide-slate-100">
              {recentEvents.map((item, index) => (
                <li
                  key={`${item.type}-${item.event}-${item.timestamp}-${index}`}
                  className="flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {item.event}
                    </p>
                    <p className="text-xs text-slate-500">{item.type}</p>
                  </div>
                  <time
                    dateTime={item.timestamp}
                    className="text-xs text-slate-500"
                  >
                    {formatTimestamp(item.timestamp)}
                  </time>
                </li>
              ))}
            </ul>
          )}
        </article>
      </div>
    </section>
  )
}
