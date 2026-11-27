import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'

import { getDocumentById } from '../api/documentService'

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

function formatFileSize(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`

  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export default function DocumentDetailPage() {
  const { id } = useParams()

  const isValidId =
    id !== undefined &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      id,
    )

  const documentQuery = useQuery({
    queryKey: ['hr-document', id],
    queryFn: () => getDocumentById(id!),
    enabled: isValidId,
  })

  const document = documentQuery.data

  if (!isValidId) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Invalid document ID." />
        <Link
          to="/documents"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Back to documents
        </Link>
      </div>
    )
  }

  if (documentQuery.isLoading) {
    return <Loading message="Loading document details..." />
  }

  if (documentQuery.isError || !document) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <ErrorMessage message="Unable to load this document. It may not exist or you may not have permission to view it." />

        <button
          type="button"
          onClick={() => documentQuery.refetch()}
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          Retry
        </button>

        <div>
          <Link
            to="/documents"
            className="text-sm font-semibold text-blue-700 hover:underline"
          >
            Back to documents
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <Link
          to="/documents"
          className="text-sm font-semibold text-blue-700 hover:underline"
        >
          ← Back to documents
        </Link>

        <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
          Document details
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Document ID: {document.id}
        </p>
      </div>

      <section
        aria-label="Document information"
        className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h2 className="border-b border-slate-100 pb-4 text-lg font-semibold text-slate-900">
          Document information
        </h2>

        <div className="grid gap-6 pt-6 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Title
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.title}
            </p>
          </div>

          <div className="sm:col-span-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Original filename
            </p>
            <p className="mt-1 break-all text-sm text-slate-900">
              {document.original_filename}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Document type
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatLabel(document.document_type)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Status
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatLabel(document.status)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Employee ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.employee}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              File size
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatFileSize(document.size_bytes)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              MIME type
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.mime_type}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Uploaded by user ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.uploaded_by}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Verified by user ID
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.verified_by ?? '—'}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Uploaded at
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(document.uploaded_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Last updated
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(document.updated_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Verified at
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {formatDate(document.verified_at)}
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Expiration date
            </p>
            <p className="mt-1 text-sm font-medium text-slate-900">
              {document.expires_at ?? '—'}
            </p>
          </div>

          {document.rejection_reason && (
            <div className="sm:col-span-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Rejection reason
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-900">
                {document.rejection_reason}
              </p>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
