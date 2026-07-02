import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import ApprobationPage from './ApprobationPage.jsx'
import RetentionPage from './RetentionPage.jsx'
import TagsPage from './TagsPage.jsx'

/* UX45–UX47 — tests de rendu (smoke) + chemin d'erreur legal-hold (403).
   Toutes les données gedApi sont mockées : on vérifie que les écrans montent
   sans planter et que la levée d'un legal hold refusée (403) est surfacée en
   toast propre (jamais de JSON brut, jamais d'échec silencieux). */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getDemandesApprobation: vi.fn(() => Promise.resolve({ data: [] })),
    getDemandesSignature: vi.fn(() => Promise.resolve({ data: [] })),
    getModelesDocument: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsList: vi.fn(() => Promise.resolve({ data: [] })),
    getPolitiquesRetention: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsEchus: vi.fn(() => Promise.resolve({ data: [] })),
    getArchivagesLegaux: vi.fn(() => Promise.resolve({ data: [] })),
    getLegalHolds: vi.fn(() => Promise.resolve({ data: [] })),
    getPartages: vi.fn(() => Promise.resolve({ data: [] })),
    getJournalAcces: vi.fn(() => Promise.resolve({ data: [] })),
    getQuotaEtat: vi.fn(() => Promise.resolve({
      data: { usage_octets: 0, quota_octets: 0, restant_octets: 0, depasse: false, illimite: true },
    })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getTagAssignments: vi.fn(() => Promise.resolve({ data: [] })),
    getLiens: vi.fn(() => Promise.resolve({ data: [] })),
    leverLegalHold: vi.fn(),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
  }
})

function renderPage(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('UX45 ApprobationPage', () => {
  it('rend les onglets sans planter', async () => {
    renderPage(<ApprobationPage />)
    expect(await screen.findByText('Approbations & revue')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Signatures' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Modèles' })).toBeInTheDocument()
  })
})

describe('UX46 RetentionPage', () => {
  it('rend les politiques et les onglets sans planter', async () => {
    renderPage(<RetentionPage />)
    expect(await screen.findByText('Politiques de rétention')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Legal holds' })).toBeInTheDocument()
  })

  it('surfacer un legal hold refusé (403) en toast (jamais de JSON brut)', async () => {
    // Un hold ACTIF est listé ; sa levée renvoie 403 (garde légale).
    gedApi.getLegalHolds.mockResolvedValueOnce({
      data: [{
        id: 7, document: 3, document_nom: 'Contrat.pdf', motif: 'Litige',
        actif: true, date_pose: '2026-06-01T10:00:00Z', place_par_nom: 'Reda',
      }],
    })
    gedApi.leverLegalHold.mockRejectedValueOnce({
      response: { status: 403, data: { detail: 'Levée refusée : document sous archivage légal.' } },
    })

    renderPage(<RetentionPage />)

    // Onglet Legal holds.
    await userEvent.click(await screen.findByRole('tab', { name: 'Legal holds' }))
    // L'action unique « Lever le hold » est un bouton d'action rapide de la ligne
    // (label = accessible name), présent même masqué visuellement.
    const levers = await screen.findAllByRole('button', { name: 'Lever le hold' })
    await userEvent.click(levers[0])

    await waitFor(() => {
      expect(gedApi.leverLegalHold).toHaveBeenCalledWith(7)
      expect(toast.error).toHaveBeenCalledWith(
        'Levée refusée : document sous archivage légal.',
      )
    })
  })
})

describe('UX47 TagsPage', () => {
  it('rend la taxonomie et les onglets sans planter', async () => {
    renderPage(<TagsPage />)
    expect(await screen.findByText('Taxonomie de tags')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Liens transverses' })).toBeInTheDocument()
  })
})
