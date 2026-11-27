
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { getTasks, transitionTask } from '../api/taskService'
import type { OnboardingTask, TaskStatus } from '../api/taskService'

import DataTable from '../components/ui/DataTable'
import type { TableColumn } from '../components/ui/DataTable'
import StatusBadge from '../components/ui/StatusBadge'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

const PAGE_SIZE = 20

const ALLOWED_TRANSITIONS: Record<TaskStatus, TaskStatus[]> = {
  PENDING: ['IN_PROGRESS', 'CANCELLED'],
  IN_PROGRESS: ['COMPLETED', 'CANCELLED'],
  BLOCKED: ['PENDING'],
  COMPLETED: [],
  CANCELLED: [],
}

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
    : date.toLocaleDateString()
}

function getPriorityClass(priority: string) {
  switch (priority) {
    case 'URGENT':
      return 'bg-red-100 text-red-800'
    case 'HIGH':
      return 'bg-orange-100 text-orange-800'
    case 'MEDIUM':
      return 'bg-yellow-100 text-yellow-800'
    case 'LOW':
      return 'bg-slate-100 text-slate-700'
    default:
      return 'bg-slate-100 text-slate-700'
  }
}

export default function TasksPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [page, setPage] = useState(1)
  const [selectedTask, setSelectedTask] = useState<OnboardingTask | null>(
    null,
  )
  const [targetStatus, setTargetStatus] = useState<TaskStatus | null>(null)

  const role = user?.role

  const canManageTasks =
    role === 'SUPER_ADMIN' ||
    role === 'HR_ADMIN' ||
    role === 'HR_MANAGER'

  const tasksQuery = useQuery({
    queryKey: ['onboarding-tasks', page],
    queryFn: () =>
      getTasks({
        page,
        page_size: PAGE_SIZE,
      }),
    enabled: user !== null,
  })

  const transitionMutation = useMutation({
    mutationFn: (input: {
      id: string
      targetStatus: TaskStatus
    }) => transitionTask(input.id, input.targetStatus),

    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['onboarding-tasks'],
      })

      setSelectedTask(null)
      setTargetStatus(null)
    },
  })

  function requestTransition(
    task: OnboardingTask,
    nextStatus: TaskStatus,
  ) {
    setSelectedTask(task)
    setTargetStatus(nextStatus)
  }

  function confirmTransition() {
    if (!selectedTask || !targetStatus) return

    transitionMutation.mutate({
      id: selectedTask.id,
      targetStatus,
    })
  }

  const columns: TableColumn<OnboardingTask>[] = [
    {
      key: 'title',
      header: 'Task',
      render: (task) => (
        <div className="min-w-40">
        <Link
          to={`/tasks/${task.id}`}
          className="font-medium text-blue-700 hover:underline"
          >
          {task.title}
          </Link>
          {task.description && (
            <p className="mt-1 text-xs text-slate-500">
              {task.description}
            </p>
          )}
        </div>
      ),
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (task) => (
        <span
          className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${getPriorityClass(task.priority)}`}
        >
          {formatLabel(task.priority)}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (task) => <StatusBadge status={task.status} />,
    },
    {
      key: 'assigned_to',
      header: 'Assigned user ID',
      render: (task) => task.assigned_to ?? 'Unassigned',
    },
    {
      key: 'due_date',
      header: 'Due date',
      render: (task) => formatDate(task.due_date),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (task) => {
        const availableTransitions = ALLOWED_TRANSITIONS[task.status]

        if (!canManageTasks || availableTransitions.length === 0) {
          return <span className="text-sm text-slate-400">—</span>
        }

        return (
          <div className="flex flex-wrap gap-2">
            {availableTransitions.map((nextStatus) => (
              <button
                key={nextStatus}
                type="button"
                onClick={() => requestTransition(task, nextStatus)}
                disabled={transitionMutation.isPending}
                className="text-sm font-medium text-blue-700 underline disabled:opacity-50"
              >
                {formatLabel(nextStatus)}
              </button>
            ))}
          </div>
        )
      },
    },
  ]

  if (!user) {
    return (
      <div className="mx-auto max-w-7xl">
        <ErrorMessage message="Unable to identify the current user." />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section>
        <h1 className="text-2xl font-bold text-slate-900">
          Onboarding Tasks
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          View onboarding tasks and track their progress according to your
          access permissions.
        </p>
      </section>

      {transitionMutation.isError && (
        <ErrorMessage message="The task status could not be changed. Check the task prerequisites, its current status and your permissions." />
      )}

      {tasksQuery.isLoading && (
        <Loading message="Loading onboarding tasks..." />
      )}

      {tasksQuery.isError && (
        <div className="space-y-3">
          <ErrorMessage message="Unable to load onboarding tasks." />
          <button
            type="button"
            onClick={() => tasksQuery.refetch()}
            className="text-sm font-semibold text-blue-700 underline"
          >
            Try again
          </button>
        </div>
      )}

      {tasksQuery.data && !tasksQuery.isError && (
        <DataTable<OnboardingTask>
          columns={columns}
          data={tasksQuery.data.results}
          rowKey={(task) => task.id}
          emptyMessage="No onboarding tasks found."
          pageSize={PAGE_SIZE}
          serverPagination={{
            page,
            totalCount: tasksQuery.data.count,
            onPageChange: setPage,
          }}
        />
      )}

      <ConfirmDialog
        open={selectedTask !== null && targetStatus !== null}
        title="Change task status"
        message={
          selectedTask && targetStatus
            ? `Change "${selectedTask.title}" from ${formatLabel(selectedTask.status)} to ${formatLabel(targetStatus)}?`
            : ''
        }
        confirmLabel="Confirm"
        cancelLabel="Cancel"
        variant="primary"
        onConfirm={confirmTransition}
        onCancel={() => {
          if (!transitionMutation.isPending) {
            setSelectedTask(null)
            setTargetStatus(null)
          }
        }}
      />
    </div>
  )
}
