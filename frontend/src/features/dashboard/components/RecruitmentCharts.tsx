import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { RecruitmentMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface RecruitmentChartsProps {
  data: RecruitmentMetrics
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="flex min-h-64 items-center justify-center rounded-lg bg-slate-50 px-4 text-center text-sm text-slate-500">
      {message}
    </div>
  )
}

function formatDate(date: string) {
  const [, month, day] = date.split('-')
  return month && day ? `${month}/${day}` : date
}

export default function RecruitmentCharts({
  data,
}: RecruitmentChartsProps) {
  const openPostings =
    data.job_postings.by_status.find(
      (item) => item.status === 'OPEN',
    )?.count ?? 0

  const hiredRate =
    data.applications.total > 0
      ? `${((data.applications.hired_in_period / data.applications.total) * 100).toFixed(1)}%`
      : '0%'

  const postingStatus = data.job_postings.by_status.map((item) => ({
    status: item.status.replaceAll('_', ' '),
    count: item.count,
  }))

  const applicationStatus = data.applications.by_status.map((item) => ({
    status: item.status.replaceAll('_', ' '),
    count: item.count,
  }))

  const dailyActivity = data.daily_activity.map((item) => ({
    date: formatDate(item.applied_at__date),
    count: item.count,
  }))

  return (
    <section aria-labelledby="recruitment-heading" className="space-y-5">
      <div>
        <h2
          id="recruitment-heading"
          className="text-lg font-semibold text-slate-900"
        >
          Recruitment overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Recruitment activity over the last {data.period_days} days.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total Job Postings"
          value={data.job_postings.total}
          description="All job postings"
          icon="💼"
        />

        <StatCard
          label="Open Postings"
          value={openPostings}
          description="Currently accepting applications"
          icon="📢"
        />

        <StatCard
          label="Applications Received"
          value={data.applications.received_in_period}
          description={`During the last ${data.period_days} days`}
          icon="📥"
        />

        <StatCard
          label="Hired"
          value={data.applications.hired_in_period}
          description={`${hiredRate} of total applications`}
          icon="✓"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <article className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Job postings by status
          </h3>

          <div className="mt-4">
            {postingStatus.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={postingStatus}
                  margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="status" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar
                    dataKey="count"
                    name="Postings"
                    fill="#2563eb"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart message="No job posting status data available." />
            )}
          </div>
        </article>

        <article className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Applications by status
          </h3>

          <div className="mt-4">
            {applicationStatus.length > 0 ? (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={applicationStatus}
                  margin={{ top: 8, right: 12, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="status"
                    tick={{ fontSize: 12 }}
                    interval={0}
                  />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar
                    dataKey="count"
                    name="Applications"
                    fill="#0d9488"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart message="No application status data available." />
            )}
          </div>
        </article>
      </div>

      <article className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-slate-900">
          Daily application activity
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Applications received each day.
        </p>

        <div className="mt-4">
          {dailyActivity.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart
                data={dailyActivity}
                margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  minTickGap={20}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="Applications"
                  stroke="#7c3aed"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart message="No daily application activity available." />
          )}
        </div>
      </article>
    </section>
  )
}
