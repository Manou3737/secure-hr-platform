import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { WorkforceMetrics } from '../../../api/dashboardService'
import StatCard from '../../../components/ui/StatCard'

interface WorkforceOverviewProps {
  data: WorkforceMetrics
}

interface DistributionItem {
  label: string
  count: number
}

function DistributionChart({
  title,
  description,
  data,
}: {
  title: string
  description: string
  data: DistributionItem[]
}) {
  return (
    <section className="min-w-0 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div>
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>

      {data.length > 0 ? (
        <div
          className="mt-5 h-72 w-full"
          role="img"
          aria-label={`${title} bar chart`}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 4, right: 16, bottom: 4, left: 8 }}
            >
              <CartesianGrid
                stroke="#e2e8f0"
                strokeDasharray="3 3"
                horizontal={false}
              />
              <XAxis
                type="number"
                allowDecimals={false}
                tick={{ fontSize: 12, fill: '#64748b' }}
              />
              <YAxis
                type="category"
                dataKey="label"
                width={110}
                tick={{ fontSize: 12, fill: '#475569' }}
              />
              <Tooltip
                formatter={(value) => [value, 'Employees']}
                cursor={{ fill: '#eff6ff' }}
              />
              <Bar
                dataKey="count"
                name="Employees"
                fill="#2563eb"
                radius={[0, 5, 5, 0]}
                maxBarSize={28}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="py-12 text-center text-sm text-slate-500">
          No distribution data available.
        </p>
      )}
    </section>
  )
}

export default function WorkforceOverview({
  data,
}: WorkforceOverviewProps) {
  const departmentData: DistributionItem[] =
    data.departments.distribution.map((department) => ({
      label: department.department__name,
      count: department.employee_count,
    }))

  const roleData: DistributionItem[] = data.roles.map((role) => ({
    label: role.user__role.replaceAll('_', ' '),
    count: role.employee_count,
  }))

  return (
    <section aria-labelledby="workforce-heading" className="space-y-5">
      <div>
        <h2
          id="workforce-heading"
          className="text-lg font-semibold tracking-tight text-slate-900"
        >
          Workforce overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Employee distribution and hiring activity.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Hires this month"
          value={data.hires.this_month}
          description="New employees this month"
          icon="📈"
        />
        <StatCard
          label="Hires this year"
          value={data.hires.this_year}
          description="New employees this year"
          icon="📅"
        />
        <StatCard
          label="Departments"
          value={data.departments.total}
          description="Departments in the organization"
          icon="🏢"
        />
        <StatCard
          label="Positions"
          value={data.positions.total}
          description="Defined organizational positions"
          icon="💼"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <DistributionChart
          title="Employees by department"
          description="Workforce distribution across departments."
          data={departmentData}
        />

        <DistributionChart
          title="Employees by role"
          description="Distribution across platform access roles."
          data={roleData}
        />
      </div>
    </section>
  )
}
