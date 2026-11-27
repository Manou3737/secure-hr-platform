import type { OnboardingMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'
import { Link } from 'react-router-dom'
interface OnboardingOverviewProps {
  data: OnboardingMetrics
}

const journeyStatuses = [
  { key: 'pending', label: 'Pending', color: 'bg-amber-500' },
  { key: 'in_progress', label: 'In progress', color: 'bg-blue-600' },
  { key: 'suspended', label: 'Suspended', color: 'bg-orange-500' },
  { key: 'completed', label: 'Completed', color: 'bg-emerald-600' },
  { key: 'cancelled', label: 'Cancelled', color: 'bg-slate-400' },
] as const

const taskStatuses = [
  { key: 'pending', label: 'Pending', color: 'bg-amber-500' },
  { key: 'in_progress', label: 'In progress', color: 'bg-blue-600' },
  { key: 'blocked', label: 'Blocked', color: 'bg-red-500' },
  { key: 'completed', label: 'Completed', color: 'bg-emerald-600' },
  { key: 'cancelled', label: 'Cancelled', color: 'bg-slate-400' },
] as const

export default function OnboardingOverview({
  data,
}: OnboardingOverviewProps) {
  const progress = Math.min(100, Math.max(0, data.progress.percentage))

  const journeyItems = journeyStatuses.map((status) => ({
    ...status,
    count: data.journeys[status.key],
  }))

  const taskItems = taskStatuses.map((status) => ({
    ...status,
    count: data.tasks[status.key],
  }))

  return (
    <section aria-labelledby="onboarding-heading" className="space-y-5">
      <div>
        <h2
          id="onboarding-heading"
          className="text-lg font-semibold tracking-tight text-slate-900"
        >
          Onboarding overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Employee onboarding journeys, task progress and outstanding work.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total Journeys"
          value={data.journeys.total}
          description="All onboarding journeys"
          icon="🧭"
        />
        <StatCard
          label="Completed Journeys"
          value={data.journeys.completed}
          description="Successfully completed journeys"
          icon="✅"
        />
        <StatCard
          label="Total Tasks"
          value={data.tasks.total}
          description="Tasks across onboarding journeys"
          icon="📝"
        />
        <StatCard
          label="Overdue Tasks"
          value={data.tasks.overdue}
          description="Tasks requiring attention"
          icon="⏰"
        />
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Overall onboarding progress
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Completed eligible tasks
            </p>
          </div>
          <span className="text-2xl font-bold tabular-nums text-slate-900">
            {progress.toFixed(1)}%
          </span>
        </div>

        <div
          className="mt-4 h-3 overflow-hidden rounded-full bg-slate-100"
          role="progressbar"
          aria-label="Overall onboarding progress"
          aria-valuenow={progress}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div
            className="h-full rounded-full bg-blue-600 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>

        <p className="mt-3 text-xs text-slate-500">
          {data.progress.completed_tasks} of{' '}
          {data.progress.total_eligible_tasks} eligible tasks completed.
        </p>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-slate-900">
              Journey status
            </h3>
            <span className="text-sm font-semibold tabular-nums text-slate-700">
              {data.journeys.total} total
            </span>
          </div>

          <div className="mt-5 space-y-4">
            {journeyItems.map((item) => (
              <div key={item.key}>
                <div className="mb-1 flex justify-between gap-3 text-sm">
                  <span className="text-slate-600">{item.label}</span>
                  <span className="font-medium tabular-nums text-slate-900">
                    {item.count}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{
                      width: `${
                        data.journeys.total > 0
                          ? (item.count / data.journeys.total) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-base font-semibold text-slate-900">
              Task status
            </h3>
            <span className="text-sm font-semibold tabular-nums text-slate-700">
              {data.tasks.total} total
            </span>
          </div>

          <div className="mt-5 space-y-4">
            {taskItems.map((item) => (
              <div key={item.key}>
                <div className="mb-1 flex justify-between gap-3 text-sm">
                  <span className="text-slate-600">{item.label}</span>
                  <span className="font-medium tabular-nums text-slate-900">
                    {item.count}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${item.color}`}
                    style={{
                      width: `${
                        data.tasks.total > 0
                          ? (item.count / data.tasks.total) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section
        aria-label="Onboarding task priorities"
        className="grid grid-cols-2 gap-4 xl:grid-cols-4"
      >
        <StatCard label="Low priority" value={data.tasks.low_priority} />
        <StatCard label="Medium priority" value={data.tasks.medium_priority} />
        <StatCard label="High priority" value={data.tasks.high_priority} />
        <StatCard label="Urgent priority" value={data.tasks.urgent_priority} />
      </section>
      <section
        aria-labelledby="overdue-tasks-heading"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <h3
          id="overdue-tasks-heading"
          className="text-sm font-semibold text-slate-800"
        >
          Overdue task details
        </h3>

        {data.tasks.overdue_details.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">
            No overdue tasks.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-100">
            {data.tasks.overdue_details.map((task) => (
              <li key={task.id} className="flex flex-col gap-2 py-3">
                <Link
                  to={`/tasks/${task.id}`}
                  className="text-sm font-medium text-blue-700 underline hover:text-blue-900"
                  >
                  {task.title}
                </Link>

                <p className="text-sm text-slate-600">
                  {task.employee_name}
                </p>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                  <span>
                    Due:{' '}
                    <time dateTime={task.due_date}>{task.due_date}</time>
                  </span>
                  <span>Priority: {task.priority}</span>
                  <span>Status: {task.status}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  )
}
