
import api from './client'
import type { PaginatedResponse } from './employeeService'

export type DocumentType =
  | 'IDENTITY_DOCUMENT'
  | 'EMPLOYMENT_CONTRACT'
  | 'TAX_FORM'
  | 'CERTIFICATION'
  | 'POLICY_ACKNOWLEDGMENT'
  | 'ONBOARDING_FORM'
  | 'OTHER'

export type DocumentStatus =
  | 'PENDING_SCAN'
  | 'PENDING_REVIEW'
  | 'VERIFIED'
  | 'QUARANTINED'
  | 'REJECTED'
  | 'ARCHIVED'

export interface HRDocument {
  id: string
  employee: number
  title: string
  document_type: DocumentType
  original_filename: string
  mime_type: string
  size_bytes: number
  checksum_sha256: string
  status: DocumentStatus
  uploaded_by: number
  verified_by: number | null
  uploaded_at: string
  updated_at: string
  verified_at: string | null
  rejection_reason: string
  expires_at: string | null
  metadata: Record<string, unknown>
}

export interface DocumentListParams {
  page?: number
  page_size?: number
  employee?: number
  document_type?: DocumentType
  status?: DocumentStatus
  ordering?: string
}

export interface CreateDocumentData {
  title: string
  document_type: DocumentType
  document_file: File
  employee?: number
  expires_at?: string
}

export interface UpdateDocumentData {
  title?: string
  document_type?: DocumentType
  expires_at?: string | null
  metadata?: Record<string, unknown>
}

// Version and review response structures are intentionally
// kept flexible until their serializers are inspected.
export type DocumentVersion = Record<string, unknown>
export type DocumentReview = Record<string, unknown>

const DOCUMENTS_URL = '/employees/hr-documents/'

/**
 * Retrieve the paginated list of accessible HR documents.
 */
 export async function getDocuments(
   params: DocumentListParams = {},
 ): Promise<PaginatedResponse<HRDocument>> {
   const response = await api.get<PaginatedResponse<HRDocument>>(
     DOCUMENTS_URL,
     {
       params: {
         ...params,
         page: params.page ?? 1,
         page_size: params.page_size ?? 20,
       },
     },
   )

   return response.data
 }

/**
 * Retrieve one document by its UUID.
 */
export async function getDocumentById(
  id: string,
): Promise<HRDocument> {
  const response = await api.get<HRDocument>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/`,
  )

  return response.data
}

/**
 * Upload a new HR document.
 *
 * HR roles must provide employee.
 * EMPLOYEE accounts are associated with their own profile by the backend.
 */
export async function createDocument(
  data: CreateDocumentData,
): Promise<HRDocument> {
  const formData = new FormData()

  formData.append('title', data.title)
  formData.append('document_type', data.document_type)
  formData.append('document_file', data.document_file)

  if (data.employee !== undefined) {
    formData.append('employee', String(data.employee))
  }

  if (data.expires_at) {
    formData.append('expires_at', data.expires_at)
  }

  const response = await api.post<HRDocument>(
    DOCUMENTS_URL,
    formData,
    {
      headers: {
        'Content-Type': undefined,
      },
    },
  )

  return response.data
}

/**
 * Update document metadata.
 *
 * PATCH is used so that the required document_file field
 * is not needed for metadata-only updates.
 */
export async function updateDocument(
  id: string,
  data: UpdateDocumentData,
): Promise<HRDocument> {
  const response = await api.patch<HRDocument>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/`,
    data,
  )

  return response.data
}

/**
 * Download a document.
 *
 * The backend permits downloads only when the document
 * is VERIFIED and the user passes download permissions.
 */
export async function downloadDocument(
  id: string,
): Promise<Blob> {
  const response = await api.get<Blob>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/download/`,
    { responseType: 'blob' },
  )

  return response.data
}

/**
 * Retrieve document version history.
 */
export async function getDocumentVersions(
  id: string,
): Promise<DocumentVersion[]> {
  const response = await api.get<DocumentVersion[]>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/versions/`,
  )

  return response.data
}

/**
 * Upload a new immutable document version.
 */
export async function createDocumentVersion(
  id: string,
  file: File,
): Promise<DocumentVersion> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post<DocumentVersion>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/create-version/`,
    formData,
    {
      headers: {
        'Content-Type': undefined,
      },
    },
  )

  return response.data
}

/**
 * Retrieve document review history.
 */
export async function getDocumentReviews(
  id: string,
): Promise<DocumentReview[]> {
  const response = await api.get<DocumentReview[]>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/reviews/`,
  )

  return response.data
}

/**
 * Approve a document.
 */
export async function verifyDocument(
  id: string,
): Promise<HRDocument> {
  const response = await api.post<HRDocument>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/verify/`,
  )

  return response.data
}

/**
 * Reject a document with a mandatory reason.
 */
export async function rejectDocument(
  id: string,
  reason: string,
): Promise<HRDocument> {
  const response = await api.post<HRDocument>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/reject/`,
    { reason },
  )

  return response.data
}

/**
 * Archive a VERIFIED or REJECTED document.
 */
export async function archiveDocument(
  id: string,
): Promise<HRDocument> {
  const response = await api.post<HRDocument>(
    `${DOCUMENTS_URL}${encodeURIComponent(id)}/archive/`,
  )

  return response.data
}
