
interface ModulePageProps {
  title: string
}

export default function ModulePage({ title }: ModulePageProps) {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <section>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {title}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage and review {title.toLowerCase()}.
        </p>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h2 className="text-base font-semibold text-slate-800">
          Module preparation
        </h2>
        <p className="mt-2 text-sm text-slate-500">
          This module is being prepared for integration.
        </p>
      </section>
    </div>
  )
}
