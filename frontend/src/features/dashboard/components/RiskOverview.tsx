import type { RiskMetrics } from '../../../api/dashboardService'

interface RiskOverviewProps {
  data: RiskMetrics
}

export default function RiskOverview({ data }: RiskOverviewProps) {
  const complianceItems = [
    {
      label: 'Incomplete profiles',
      value: data.compliance.incomplete_profiles,
    },
    {
      label: 'Employees missing required documents',
      value: data.compliance.employees_missing_required_documents,
    },
    {
      label: 'Expired documents',
      value: data.compliance.expired_documents,
    },
    {
      label: 'Documents expiring soon',
      value: data.compliance.documents_expiring_soon,
    },
  ]

  const lifecycleItems = [
    { label: 'Pending scan', value: data.document_lifecycle.pending_scan },
    { label: 'Pending review', value: data.document_lifecycle.pending_review },
    { label: 'Quarantined', value: data.document_lifecycle.quarantined },
    { label: 'Rejected', value: data.document_lifecycle.rejected },
    { label: 'Verified', value: data.document_lifecycle.verified },
    { label: 'Archived', value: data.document_lifecycle.archived },
  ]

  const securityItems = [
    { label: 'Brute force', value: data.security.brute_force },
    { label: 'Suspicious IP', value: data.security.suspicious_ip },
    { label: 'Unauthorized access', value: data.security.unauthorized_access },
    { label: 'Privilege escalation', value: data.security.privilege_escalation },
  ]

  const maxCompliance = Math.max(...complianceItems.map((item) => item.value), 1)
  const maxLifecycle = Math.max(...lifecycleItems.map((item) => item.value), 1)
  const maxSecurity = Math.max(...securityItems.map((item) => item.value), 1)

  const hasComplianceRisks = complianceItems.some((item) => item.value > 0)
  const hasLifecycleActivity = lifecycleItems.some((item) => item.value > 0)
  const hasSecurityDetections = securityItems.some((item) => item.value > 0)

  const renderMetrics = (
    items: Array<{ label: string; value: number }>,
    maxValue: number,
    barColor: string,
  ) => (
    <ul className="mt-4 space-y-4">
      {items.map((item) => {
        const percentage = Math.min((item.value / maxValue) * 100, 100)

        return (
          <li key={item.label}>
            <div className="mb-1 flex justify-between gap-3 text-sm">
              <span className="text-slate-600">{item.label}</span>
              <span className="font-medium tabular-nums text-slate-900">
                {item.value}
              </span>
            </div>

            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className={`h-full rounded-full ${barColor}`}
                style={{ width: `${percentage}%` }}
              />
            </div>
          </li>
        )
      })}
    </ul>
  )

  return (
    <section aria-labelledby="risk-heading" className="space-y-5">
      <div>
        <h2 id="risk-heading" className="text-lg font-semibold text-slate-900">
          Risk overview
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          HR compliance, document lifecycle, and security risk indicators.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Compliance risks
          </h3>

          {!hasComplianceRisks ? (
            <p className="mt-4 text-sm text-slate-500">
              No compliance risks detected.
            </p>
          ) : (
            renderMetrics(complianceItems, maxCompliance, 'bg-amber-500')
          )}
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-slate-900">
            Document lifecycle
          </h3>

          {!hasLifecycleActivity ? (
            <p className="mt-4 text-sm text-slate-500">
              No document lifecycle activity.
            </p>
          ) : (
            renderMetrics(lifecycleItems, maxLifecycle, 'bg-blue-500')
          )}
        </article>

        <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <h3 className="text-sm font-semibold text-slate-900">
            Security detections
          </h3>

          {!hasSecurityDetections ? (
            <p className="mt-4 text-sm text-slate-500">
              No security detections.
            </p>
          ) : (
            renderMetrics(securityItems, maxSecurity, 'bg-rose-500')
          )}
        </article>
      </div>
    </section>
  )
}
