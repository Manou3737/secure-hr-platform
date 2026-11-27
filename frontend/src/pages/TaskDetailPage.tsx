import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getTaskById } from '../api/taskService'

import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

function formatLabel(value: string) {
  return value
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatDate(value: string | null) {
  if (!value) return '—'

  const date = new Date(value)

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString()
}

export default function TaskDetailPage() {
  const { id } = useParams()

  const isValidId =
    id !== undefined &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      id,
    )

  const taskQuery = useQuery({
    queryKey: ['onboarding-task', id],
    queryFn: () => getTaskById(id!),
    enabled: isValidId,
  })

  const task = taskQuery.data

  if (!isValidId) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Invalid task ID." />
        <Link
          to="/tasks"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Back to tasks
        </Link>
      </div>
    )
  }

  if (taskQuery.isLoading) {
    return <Loading message="Loading task details..." />
  }

  if (taskQuery.isError || !task) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Unable to load this task. It may not exist or you may not have permission to view it." />

        <button
          type="button"
          onClick={() => taskQuery.refetch()}
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Retry
        </button>

        <div>
          <Link
            to="/tasks"
            className="text-sm font-semibold text-blue-700 hover:underline"
          >
            Back to tasks
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Link
          to="/tasks"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          ← Back to tasks
        </Link>

        <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
          Task details
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Task ID: {task.id}
        </p>
      </div>

      <section
        aria-label="Task information"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="border-b border-slate-100 pb-4 text-lg font-semibold text-slate-900">
          Task information
        </h2>

        <div className="grid gap-6 pt-6 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Title
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {task.title}
            </p>
          </div>

          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Description
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
              {task.description || '—'}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Status
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatLabel(task.status)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Priority
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatLabel(task.priority)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Journey ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {task.journey}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Activity template ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {task.activity_template}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Assigned user ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {task.assigned_to ?? 'Unassigned'}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Due date
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {task.due_date ?? '—'}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Started at
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(task.started_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Completed at
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(task.completed_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Created at
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(task.created_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Last updated
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(task.updated_at)}
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
