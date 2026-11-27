
import { useState } from 'react'
import type { FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import {
  archiveDocument,
  createDocument,
  downloadDocument,
  getDocuments,
  rejectDocument,
  verifyDocument,
} from '../api/documentService'

import type {
  DocumentStatus,
  DocumentType,
  HRDocument,
} from '../api/documentService'

import DataTable from '../components/ui/DataTable'
import type { TableColumn } from '../components/ui/DataTable'
import Loading from '../components/ui/Loading'
import ErrorMessage from '../components/ui/ErrorMessage'

const PAGE_SIZE = 20
const MAX_FILE_SIZE = 10 * 1024 * 1024

const DOCUMENT_TYPES: DocumentType[] = [
  'IDENTITY_DOCUMENT',
  'EMPLOYMENT_CONTRACT',
  'TAX_FORM',
  'CERTIFICATION',
  'POLICY_ACKNOWLEDGMENT',
  'ONBOARDING_FORM',
  'OTHER',
]

const DOCUMENT_STATUSES: DocumentStatus[] = [
  'PENDING_SCAN',
  'PENDING_REVIEW',
  'VERIFIED',
  'QUARANTINED',
  'REJECTED',
  'ARCHIVED',
]

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

function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function isAllowedFile(file: File) {
  const extension = file.name.split('.').pop()?.toLowerCase()

  return (
    file.size > 0 &&
    file.size <= MAX_FILE_SIZE &&
    ['pdf', 'png', 'jpg', 'jpeg'].includes(extension ?? '')
  )
}

export default function DocumentsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<DocumentStatus | ''>('')
  const [documentType, setDocumentType] = useState<DocumentType | ''>('')
  const [employeeId, setEmployeeId] = useState('')
  const [title, setTitle] = useState('')
  const [uploadType, setUploadType] = useState<DocumentType>('OTHER')
  const [uploadEmployeeId, setUploadEmployeeId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [formError, setFormError] = useState('')

  const role = user?.role

  const isEmployee = role === 'EMPLOYEE'
  const isManager = role === 'HR_MANAGER'
  const isAdmin = role === 'HR_ADMIN' || role === 'SUPER_ADMIN'

  const canUpload = isEmployee || isAdmin
  const canReview = isManager || isAdmin
  const canDownload = isEmployee || isAdmin

  const documentsQuery = useQuery({
    queryKey: ['hr-documents', page, status, documentType, employeeId],
    queryFn: () =>
      getDocuments({
        page,
        page_size: PAGE_SIZE,
        ...(status ? { status } : {}),
        ...(documentType ? { document_type: documentType } : {}),
        ...(employeeId.trim() && isAdmin
          ? { employee: Number(employeeId) }
          : {}),
      }),
    enabled: user !== null,
  })

  const uploadMutation = useMutation({
    mutationFn: createDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['hr-documents'],
      })

      setTitle('')
      setUploadType('OTHER')
      setUploadEmployeeId('')
      setFile(null)
      setFormError('')

      const fileInput = document.getElementById(
        'document-file',
      ) as HTMLInputElement | null

      if (fileInput) fileInput.value = ''
    },
  })

  const actionMutation = useMutation({
    mutationFn: async (input: {
      id: string
      action: 'verify' | 'reject' | 'archive'
      reason?: string
    }) => {
      if (input.action === 'verify') {
        return verifyDocument(input.id)
      }

      if (input.action === 'reject') {
        return rejectDocument(input.id, input.reason ?? '')
      }

      return archiveDocument(input.id)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['hr-documents'],
      })
    },
  })


  const downloadMutation = useMutation({
    mutationFn: downloadDocument,
    onSuccess: (blob, id) => {
      const selectedDocument = documentsQuery.data?.results.find(
        (item) => item.id === id,
      )

      const url = window.URL.createObjectURL(blob)
      const link = window.document.createElement('a')

      link.href = url
      link.download = selectedDocument?.original_filename || 'hr-document'

      window.document.body.appendChild(link)
      link.click()
      link.remove()

      window.URL.revokeObjectURL(url)
    },
  })


  function handleFilterChange() {
    setPage(1)
  }

  function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFormError('')

    if (!title.trim()) {
      setFormError('Please enter a document title.')
      return
    }

    if (!file) {
      setFormError('Please select a document file.')
      return
    }

    if (!isAllowedFile(file)) {
      setFormError(
        'Select a non-empty PDF, PNG or JPEG file no larger than 10 MB.',
      )
      return
    }

    if (isAdmin && !/^[1-9]\d*$/.test(uploadEmployeeId)) {
      setFormError('Enter a valid employee profile ID.')
      return
    }

    uploadMutation.mutate({
      title: title.trim(),
      document_type: uploadType,
      document_file: file,
      ...(isAdmin ? { employee: Number(uploadEmployeeId) } : {}),
    })
  }

  function handleReject(documentId: string) {
    const reason = window.prompt(
      'Enter the reason for rejecting this document:',
    )

    if (reason === null) return

    if (!reason.trim()) {
      setFormError('A rejection reason is required.')
      return
    }

    setFormError('')

    actionMutation.mutate({
      id: documentId,
      action: 'reject',
      reason: reason.trim(),
    })
  }

  const columns: TableColumn<HRDocument>[] = [
    {
      key: 'title',
      header: 'Document',
      render: (document) => (
        <div>
        <Link
          to={`/documents/${document.id}`}
          className="font-medium text-blue-700 hover:underline"
          >
          {document.title}
          </Link>
          <p className="text-xs text-slate-500">
            {document.original_filename}
          </p>
        </div>
      ),
    },
    {
      key: 'employee',
      header: 'Employee ID',
      render: (document) => document.employee,
    },
    {
      key: 'document_type',
      header: 'Type',
      render: (document) => formatLabel(document.document_type),
    },
    {
      key: 'status',
      header: 'Status',
      render: (document) => (
        <span className="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
          {formatLabel(document.status)}
        </span>
      ),
    },
    {
      key: 'size_bytes',
      header: 'Size',
      render: (document) => formatFileSize(document.size_bytes),
    },
    {
      key: 'uploaded_at',
      header: 'Uploaded',
      render: (document) => formatDate(document.uploaded_at),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (document) => (
        <div className="flex flex-wrap gap-2">
          {canDownload && document.status === 'VERIFIED' && (
            <button
              type="button"
              onClick={() => downloadMutation.mutate(document.id)}
              disabled={downloadMutation.isPending}
              className="text-sm font-medium text-blue-700 underline disabled:opacity-50"
            >
              Download
            </button>
          )}

          {canReview && document.status === 'PENDING_REVIEW' && (
            <>
              <button
                type="button"
                onClick={() =>
                  actionMutation.mutate({
                    id: document.id,
                    action: 'verify',
                  })
                }
                disabled={actionMutation.isPending}
                className="text-sm font-medium text-green-700 underline disabled:opacity-50"
              >
                Verify
              </button>

              <button
                type="button"
                onClick={() => handleReject(document.id)}
                disabled={actionMutation.isPending}
                className="text-sm font-medium text-red-700 underline disabled:opacity-50"
              >
                Reject
              </button>
            </>
          )}

          {canReview &&
            ['VERIFIED', 'REJECTED'].includes(document.status) && (
              <button
                type="button"
                onClick={() =>
                  actionMutation.mutate({
                    id: document.id,
                    action: 'archive',
                  })
                }
                disabled={actionMutation.isPending}
                className="text-sm font-medium text-slate-600 underline disabled:opacity-50"
              >
                Archive
              </button>
            )}
        </div>
      ),
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
          HR Documents
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          View and manage documents according to your access permissions.
        </p>
      </section>

      {canUpload && (
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="text-lg font-semibold text-slate-900">
            Upload a document
          </h2>

          <form
            onSubmit={handleUpload}
            className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2"
          >
            <div>
              <label
                htmlFor="document-title"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Document title
              </label>
              <input
                id="document-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={255}
                required
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label
                htmlFor="document-type"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Document type
              </label>
              <select
                id="document-type"
                value={uploadType}
                onChange={(event) =>
                  setUploadType(event.target.value as DocumentType)
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              >
                {DOCUMENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {formatLabel(type)}
                  </option>
                ))}
              </select>
            </div>

            {isAdmin && (
              <div>
                <label
                  htmlFor="upload-employee-id"
                  className="mb-1 block text-sm font-medium text-slate-700"
                >
                  Employee profile ID
                </label>
                <input
                  id="upload-employee-id"
                  type="number"
                  min="1"
                  value={uploadEmployeeId}
                  onChange={(event) =>
                    setUploadEmployeeId(event.target.value)
                  }
                  required
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            )}

            <div>
              <label
                htmlFor="document-file"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                File (PDF, PNG or JPEG — maximum 10 MB)
              </label>
              <input
                id="document-file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                required
                onChange={(event) =>
                  setFile(event.target.files?.[0] ?? null)
                }
                className="w-full text-sm text-slate-700"
              />
            </div>

            {formError && (
              <div className="sm:col-span-2">
                <ErrorMessage message={formError} />
              </div>
            )}

            {uploadMutation.isError && (
              <div className="sm:col-span-2">
                <ErrorMessage message="Unable to upload the document. Check the file and your permissions, then try again." />
              </div>
            )}

            <div className="sm:col-span-2">
              <button
                type="submit"
                disabled={uploadMutation.isPending}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploadMutation.isPending
                  ? 'Uploading...'
                  : 'Upload document'}
              </button>
            </div>
          </form>
        </section>
      )}

      <section
        aria-label="Document filters"
        className="grid grid-cols-1 gap-4 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        <div>
          <label
            htmlFor="document-status-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by status
          </label>
          <select
            id="document-status-filter"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as DocumentStatus | '')
              handleFilterChange()
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All statuses</option>
            {DOCUMENT_STATUSES.map((item) => (
              <option key={item} value={item}>
                {formatLabel(item)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="document-type-filter"
            className="mb-1 block text-sm font-medium text-slate-700"
          >
            Filter by type
          </label>
          <select
            id="document-type-filter"
            value={documentType}
            onChange={(event) => {
              setDocumentType(event.target.value as DocumentType | '')
              handleFilterChange()
            }}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All types</option>
            {DOCUMENT_TYPES.map((item) => (
              <option key={item} value={item}>
                {formatLabel(item)}
              </option>
            ))}
          </select>
        </div>

        {isAdmin && (
          <div>
            <label
              htmlFor="document-employee-filter"
              className="mb-1 block text-sm font-medium text-slate-700"
            >
              Employee profile ID
            </label>
            <input
              id="document-employee-filter"
              type="number"
              min="1"
              value={employeeId}
              onChange={(event) => {
                setEmployeeId(event.target.value)
                handleFilterChange()
              }}
              placeholder="All employees"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </div>
        )}
      </section>

      {actionMutation.isError && (
        <ErrorMessage message="The document action could not be completed. Check its current status and your permissions." />
      )}

      {downloadMutation.isError && (
        <ErrorMessage message="Unable to download this document. It may not be verified or your account may not have download permission." />
      )}

      {documentsQuery.isLoading && (
        <Loading message="Loading HR documents..." />
      )}

      {documentsQuery.isError && (
        <div className="space-y-3">
          <ErrorMessage message="Unable to load HR documents." />
          <button
            type="button"
            onClick={() => documentsQuery.refetch()}
            className="text-sm font-semibold text-blue-700 underline"
          >
            Try again
          </button>
        </div>
      )}

      {documentsQuery.data && !documentsQuery.isError && (
        <DataTable<HRDocument>
          columns={columns}
          data={documentsQuery.data.results}
          rowKey={(document) => document.id}
          emptyMessage="No HR documents found."
          pageSize={PAGE_SIZE}
          serverPagination={{
            page,
            totalCount: documentsQuery.data.count,
            onPageChange: setPage,
          }}
        />
      )}
    </div>
  )
}
