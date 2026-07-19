import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from '../../design/ThemeProvider'

/* WIR70 — le panneau Détails charge la timeline et le rapport ACL d'un
   document, et exporte l'ACL en CSV. */

const H = vi.hoisted(() => ({
  getTimeline: vi.fn(() => Promise.resolve({
    data: [{ evenement: 'creation', message: 'Document créé', utilisateur: 'reda', created_at: '2026-07-18T09:00:00Z' }],
  })),
  getPermissionsEffectives: vi.fn(() => Promise.resolve({
    data: [{ type: 'utilisateur', id: 5, label: 'Sami', niveau: 'lecture', source: 'heritage_dossier' }],
  })),
  exportCsv: vi.fn(() => Promise.resolve({ data: 'csv,content' })),
  toggleFavori: vi.fn(() => Promise.resolve({ data: { favori: true } })),
}))
vi.mock('../../api/gedApi', () => ({
  default: {
    getTimeline: H.getTimeline,
    getPermissionsEffectives: H.getPermissionsEffectives,
    exportPermissionsEffectivesCsv: H.exportCsv,
    toggleFavoriDocument: H.toggleFavori,
  },
}))

import GedDocumentInsights from './GedDocumentInsights'

const doc = { id: 42, nom: 'Contrat.pdf', favori: false }
const renderPanel = () => render(
  <ThemeProvider>
    <GedDocumentInsights document={doc} onClose={() => {}} />
  </ThemeProvider>,
)

beforeEach(() => Object.values(H).forEach((f) => f.mockClear()))
afterEach(() => cleanup())

describe('WIR70 GedDocumentInsights', () => {
  it('charge la timeline du document', async () => {
    renderPanel()
    await waitFor(() => expect(H.getTimeline).toHaveBeenCalledWith(42))
    expect(await screen.findByText('Document créé')).toBeInTheDocument()
  })

  it('affiche le rapport ACL et exporte en CSV', async () => {
    const user = userEvent.setup()
    // jsdom : stub des API de téléchargement.
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:x')
    globalThis.URL.revokeObjectURL = vi.fn()
    renderPanel()
    await waitFor(() => expect(H.getPermissionsEffectives).toHaveBeenCalledWith(42))
    await user.click(screen.getByRole('tab', { name: /Accès/ }))
    expect(await screen.findByText('Sami')).toBeInTheDocument()
    expect(screen.getByText('heritage_dossier')).toBeInTheDocument()
    fireEvent.click(screen.getByText('CSV'))
    await waitFor(() => expect(H.exportCsv).toHaveBeenCalledWith(42))
  })
})
