import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import DocumentDetailPage from './DocumentDetailPage'
import { getDocumentById } from '../api/documentService'

vi.mock('../api/documentService', () => ({
  getDocumentById: vi.fn(),
}))

const documentId = '550e8400-e29b-41d4-a716-446655440000'

const mockDocument = {
  id: documentId,
  employee: 12,
  title: 'Identity document',
  document_type: 'IDENTITY_DOCUMENT' as const,
  original_filename: 'identity.pdf',
  mime_type: 'application/pdf',
  size_bytes: 1024,
  checksum_sha256: 'a'.repeat(64),
  status: 'PENDING_REVIEW' as const,
  uploaded_by: 12,
  verified_by: null,
  uploaded_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
  verified_at: null,
  rejection_reason: '',
  expires_at: null,
  metadata: {
    internal_note: 'Sensitive internal metadata',
  },
}

function renderDocumentDetail(path = `/documents/${documentId}`) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/documents/:id"
            element={<DocumentDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DocumentDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays document details returned by the API', async () => {
    vi.mocked(getDocumentById).mockResolvedValue(mockDocument)

    renderDocumentDetail()

    expect(
      await screen.findByRole('heading', { name: 'Document details' }),
    ).toBeInTheDocument()

    expect(screen.getByText('Identity document')).toBeInTheDocument()
    expect(screen.getByText('identity.pdf')).toBeInTheDocument()
    expect(screen.getByText('Identity Document')).toBeInTheDocument()
    expect(screen.getByText('Pending Review')).toBeInTheDocument()
    expect(screen.getByText('application/pdf')).toBeInTheDocument()
    expect(screen.getByText('1.0 KB')).toBeInTheDocument()
    expect(screen.getAllByText('12')).toHaveLength(2)

    expect(getDocumentById).toHaveBeenCalledWith(documentId)
  })

  it('does not call the API when the document ID is invalid', () => {
    renderDocumentDetail('/documents/not-a-valid-uuid')

    expect(screen.getByText('Invalid document ID.')).toBeInTheDocument()
    expect(getDocumentById).not.toHaveBeenCalled()
  })

  it('displays a loading state while the API request is pending', () => {
    vi.mocked(getDocumentById).mockImplementation(
      () => new Promise(() => {}),
    )

    renderDocumentDetail()

    expect(screen.getByText('Loading document details...')).toBeInTheDocument()
  })

  it('displays a safe error when the API request fails', async () => {
    vi.mocked(getDocumentById).mockRejectedValue(
      new Error('Sensitive backend error details'),
    )

    renderDocumentDetail()

    expect(
      await screen.findByText(
        'Unable to load this document. It may not exist or you may not have permission to view it.',
      ),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Sensitive backend error details'),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Retry' }),
    ).toBeInTheDocument()
  })

  it('does not expose checksum or metadata in the rendered page', async () => {
    vi.mocked(getDocumentById).mockResolvedValue(mockDocument)

    renderDocumentDetail()

    await screen.findByRole('heading', { name: 'Document details' })

    expect(
      screen.queryByText(mockDocument.checksum_sha256),
    ).not.toBeInTheDocument()

    expect(
      screen.queryByText('Sensitive internal metadata'),
    ).not.toBeInTheDocument()

    expect(
      screen.queryByText(/storage_key/i),
    ).not.toBeInTheDocument()
  })

  it('provides a link back to the documents list', async () => {
    vi.mocked(getDocumentById).mockResolvedValue(mockDocument)

    renderDocumentDetail()

    expect(
      await screen.findByRole('link', { name: /back to documents/i }),
    ).toHaveAttribute('href', '/documents')
  })
})
