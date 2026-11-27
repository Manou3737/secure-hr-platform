import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import {
  archiveDocument,
  createDocument,
  downloadDocument,
  getDocuments,
  rejectDocument,
  verifyDocument,
} from '../api/documentService'
import type { HRDocument } from '../api/documentService'
import type { AuthUser } from '../auth/authService'
import DocumentsPage from './DocumentsPage'

vi.mock('../auth/useAuth', () => ({
  useAuth: vi.fn(),
}))

vi.mock('../api/documentService', () => ({
  archiveDocument: vi.fn(),
  createDocument: vi.fn(),
  downloadDocument: vi.fn(),
  getDocuments: vi.fn(),
  rejectDocument: vi.fn(),
  verifyDocument: vi.fn(),
}))

const document: HRDocument = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  employee: 12,
  title: 'Identity document',
  document_type: 'IDENTITY_DOCUMENT',
  original_filename: 'identity.pdf',
  mime_type: 'application/pdf',
  size_bytes: 1024,
  checksum_sha256: 'a'.repeat(64),
  status: 'PENDING_REVIEW',
  uploaded_by: 12,
  verified_by: null,
  uploaded_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
  verified_at: null,
  rejection_reason: '',
  expires_at: null,
  metadata: {},
}

function createUser(role: AuthUser['role']): AuthUser {
  return {
    id: 1,
    email: 'test@example.com',
    name: 'Test User',
    role,
    email_verified: true,
    is_active: true,
  }
}

function renderDocumentsPage(role: AuthUser['role']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })

  vi.mocked(useAuth).mockReturnValue({
    user: createUser(role),
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DocumentsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    vi.mocked(getDocuments).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [document],
    })

    vi.mocked(createDocument).mockResolvedValue(document)
    vi.mocked(verifyDocument).mockResolvedValue({
      ...document,
      status: 'VERIFIED',
    })
    vi.mocked(rejectDocument).mockResolvedValue({
      ...document,
      status: 'REJECTED',
    })
    vi.mocked(archiveDocument).mockResolvedValue({
      ...document,
      status: 'ARCHIVED',
    })
  })

  it('displays documents returned by the API', async () => {
    renderDocumentsPage('HR_ADMIN')

    expect(
      await screen.findByText('Identity document'),
    ).toBeInTheDocument()

    expect(screen.getByText('identity.pdf')).toBeInTheDocument()
    expect(screen.getAllByText('Pending Review')[1]).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()

    expect(getDocuments).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
    })
  })

  it('links each document title to its detail page', async () => {
    renderDocumentsPage('HR_ADMIN')

    const documentLink = await screen.findByRole('link', {
      name: 'Identity document',
    })

    expect(documentLink).toHaveAttribute(
      'href',
      `/documents/${document.id}`,
    )
  })

  it('displays a loading state', () => {
    vi.mocked(getDocuments).mockReturnValue(new Promise(() => {}))

    renderDocumentsPage('HR_ADMIN')

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('displays a safe error message when loading documents fails', async () => {
    vi.mocked(getDocuments).mockRejectedValue(
      new Error('Internal database details'),
    )

    renderDocumentsPage('HR_ADMIN')

    expect(
      await screen.findByText(/unable to load/i),
    ).toBeInTheDocument()

    expect(
      screen.queryByText('Internal database details'),
    ).not.toBeInTheDocument()
  })

  it('displays an empty state when no documents are returned', async () => {
    vi.mocked(getDocuments).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    })

    renderDocumentsPage('HR_ADMIN')

    expect(
      await screen.findByText(/no hr documents found/i),
    ).toBeInTheDocument()
  })

  it('allows employees to upload documents but not review them', async () => {
    renderDocumentsPage('EMPLOYEE')

    await screen.findByText('Identity document')

    expect(
      screen.getByRole('heading', { name: 'Upload a document' }),
    ).toBeInTheDocument()

    expect(
      screen.queryByRole('button', { name: 'Verify' }),
    ).not.toBeInTheDocument()

    expect(
      screen.queryByRole('button', { name: 'Reject' }),
    ).not.toBeInTheDocument()

    expect(
      screen.queryByLabelText('Employee profile ID'),
    ).not.toBeInTheDocument()
  })

  it('allows employees to upload their own documents without an employee ID', async () => {
    const file = new File(
      ['employee document content'],
      'identity.pdf',
      { type: 'application/pdf' },
    )

    renderDocumentsPage('EMPLOYEE')

    await screen.findByText('Identity document')

    fireEvent.change(screen.getByLabelText('Document title'), {
      target: { value: 'My identity document' },
    })

    fireEvent.change(screen.getByLabelText('Document type'), {
      target: { value: 'IDENTITY_DOCUMENT' },
    })

    const fileInput = screen.getByLabelText(
      /File \(PDF/,
    ) as HTMLInputElement

    fireEvent.change(fileInput, {
      target: { files: [file] },
    })

    const form = fileInput.closest('form')
    expect(form).not.toBeNull()

    fireEvent.submit(form!)

    await waitFor(() => {
      expect(createDocument).toHaveBeenCalled()

      expect(
        vi.mocked(createDocument).mock.calls[0]?.[0],
      ).toEqual({
        title: 'My identity document',
        document_type: 'IDENTITY_DOCUMENT',
        document_file: file,
        employee: undefined,
      })
    })
  })

  it('rejects unsupported file extensions', async () => {
    const file = new File(
      ['malicious content'],
      'malware.exe',
      { type: 'application/octet-stream' },
    )

    renderDocumentsPage('EMPLOYEE')

    await screen.findByText('Identity document')

    fireEvent.change(screen.getByLabelText('Document title'), {
      target: { value: 'My document' },
    })

    fireEvent.change(screen.getByLabelText('Document type'), {
      target: { value: 'IDENTITY_DOCUMENT' },
    })

    const fileInput = screen.getByLabelText(
      /File \(PDF/,
    ) as HTMLInputElement

    fireEvent.change(fileInput, {
      target: { files: [file] },
    })

    const form = fileInput.closest('form')
    expect(form).not.toBeNull()

    fireEvent.submit(form!)

    expect(
      await screen.findByText(
        'Select a non-empty PDF, PNG or JPEG file no larger than 10 MB.',
      ),
    ).toBeInTheDocument()

    expect(createDocument).not.toHaveBeenCalled()
  })

  it('allows employees to download verified documents', async () => {
    vi.mocked(getDocuments).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ ...document, status: 'VERIFIED' }],
    })

    const blob = new Blob(['verified document content'], {
      type: 'application/pdf',
    })

    vi.mocked(downloadDocument).mockResolvedValue(blob)

    const createObjectURLSpy = vi
      .spyOn(URL, 'createObjectURL')
      .mockReturnValue('blob:test-document')

    const revokeObjectURLSpy = vi
      .spyOn(URL, 'revokeObjectURL')
      .mockImplementation(() => {})

    try {
      renderDocumentsPage('EMPLOYEE')

      await screen.findByText('Identity document')

      fireEvent.click(screen.getByRole('button', { name: 'Download' }))

      await waitFor(() => {
        expect(downloadDocument).toHaveBeenCalled()

        expect(
          vi.mocked(downloadDocument).mock.calls[0]?.[0],
        ).toBe(document.id)
      })
    } finally {
      createObjectURLSpy.mockRestore()
      revokeObjectURLSpy.mockRestore()
    }
  })

  it('allows HR managers to verify pending documents', async () => {
    renderDocumentsPage('HR_MANAGER')

    await screen.findByText('Identity document')

    fireEvent.click(screen.getByRole('button', { name: 'Verify' }))

    await waitFor(() => {
      expect(verifyDocument).toHaveBeenCalledWith(document.id)
    })
  })

  it('allows HR managers to reject pending documents with a reason', async () => {
    const promptSpy = vi
      .spyOn(window, 'prompt')
      .mockReturnValue('Document is incomplete')

    renderDocumentsPage('HR_MANAGER')

    await screen.findByText('Identity document')

    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))

    expect(promptSpy).toHaveBeenCalled()

    await waitFor(() => {
      expect(rejectDocument).toHaveBeenCalledWith(
        document.id,
        'Document is incomplete',
      )
    })

    promptSpy.mockRestore()
  })

  it('allows HR managers to archive verified documents', async () => {
    vi.mocked(getDocuments).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          ...document,
          status: 'VERIFIED',
        },
      ],
    })

    renderDocumentsPage('HR_MANAGER')

    await screen.findByText('Identity document')

    fireEvent.click(screen.getByRole('button', { name: 'Archive' }))

    await waitFor(() => {
      expect(archiveDocument).toHaveBeenCalledWith(document.id)
    })
  })

  it('allows HR managers to review documents but not upload or download', async () => {
    renderDocumentsPage('HR_MANAGER')

    await screen.findByText('Identity document')

    expect(
      screen.queryByRole('heading', { name: 'Upload a document' }),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Verify' }),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: 'Reject' }),
    ).toBeInTheDocument()

    expect(
      screen.queryByRole('button', { name: 'Download' }),
    ).not.toBeInTheDocument()
  })

  it.each(['HR_ADMIN', 'SUPER_ADMIN'] as const)(
    '%s can upload, review and filter documents by employee',
    async (role) => {
      renderDocumentsPage(role)

      await screen.findByText('Identity document')

      expect(
        screen.getByRole('heading', { name: 'Upload a document' }),
      ).toBeInTheDocument()

      expect(
        screen.getByRole('button', { name: 'Verify' }),
      ).toBeInTheDocument()

      expect(
        screen.getByRole('button', { name: 'Reject' }),
      ).toBeInTheDocument()

      expect(
        screen.getByLabelText('Employee profile ID', {
          selector: '#upload-employee-id',
        }),
      ).toBeInTheDocument()

      expect(
        screen.getByLabelText('Employee profile ID', {
          selector: '#document-employee-filter',
        }),
      ).toBeInTheDocument()
    },
  )

  it('allows HR_ADMIN to upload a document for an employee', async () => {
    const file = new File(
      ['test document content'],
      'identity.pdf',
      { type: 'application/pdf' },
    )

    renderDocumentsPage('HR_ADMIN')

    await screen.findByText('Identity document')

    fireEvent.change(screen.getByLabelText('Document title'), {
      target: { value: 'Employee identity document' },
    })

    fireEvent.change(screen.getByLabelText('Document type'), {
      target: { value: 'IDENTITY_DOCUMENT' },
    })

    fireEvent.change(
      screen.getByLabelText('Employee profile ID', {
        selector: '#upload-employee-id',
      }),
      {
        target: { value: '12' },
      },
    )

    const fileInput = screen.getByLabelText(/File \(PDF/) as HTMLInputElement

    fireEvent.change(fileInput, {
      target: { files: [file] },
    })

    expect(fileInput.files?.[0]).toBe(file)
    expect(fileInput.files?.[0].size).toBeGreaterThan(0)

    const form = fileInput.closest('form')

    expect(form).not.toBeNull()

    fireEvent.submit(form!)

    await waitFor(() => {
      expect(createDocument).toHaveBeenCalled()

      expect(
        vi.mocked(createDocument).mock.calls[0]?.[0],
      ).toEqual({
        title: 'Employee identity document',
        document_type: 'IDENTITY_DOCUMENT',
        document_file: file,
        employee: 12,
      })
    })
  })
})
