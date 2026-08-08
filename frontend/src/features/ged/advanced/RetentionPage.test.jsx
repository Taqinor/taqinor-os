import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import RetentionPage from './RetentionPage.jsx'

/* PACT134 — onglet « Dispositions » : revue humaine avant destruction/
   archivage en fin de rétention (XGED23). Couvre UNIQUEMENT le nouvel onglet
   (le smoke test des autres onglets existants vit déjà dans advanced.test.jsx).
   Mocks alignés sur `DemandeDispositionSerializer` (id, libelle, action,
   documents, statut, demandeur_nom, approbateur_nom, certificats[]) — jamais
   un champ inventé. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getPolitiquesRetention: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsEchus: vi.fn(() => Promise.resolve({ data: [
      { document: 12, document_nom: 'Vieux-devis.pdf', politique_nom: 'Devis', jours_depasses: 40, action_echeance: 'archiver' },
    ] })),
    getArchivagesLegaux: vi.fn(() => Promise.resolve({ data: [] })),
    getLegalHolds: vi.fn(() => Promise.resolve({ data: [] })),
    getPartages: vi.fn(() => Promise.resolve({ data: [] })),
    getJournalAcces: vi.fn(() => Promise.resolve({ data: [] })),
    getDocumentsList: vi.fn(() => Promise.resolve({ data: [] })),
    getQuotaEtat: vi.fn(() => Promise.resolve({
      data: { usage_octets: 0, quota_octets: 0, restant_octets: 0, depasse: false, illimite: true },
    })),
    getDemandesDisposition: vi.fn(),
    createDemandeDisposition: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    approuverDisposition: vi.fn(() => Promise.resolve({ data: {} })),
    rejeterDisposition: vi.fn(() => Promise.resolve({ data: {} })),
    executerDisposition: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><RetentionPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getDocumentsEchus.mockResolvedValue({ data: [
    { document: 12, document_nom: 'Vieux-devis.pdf', politique_nom: 'Devis', jours_depasses: 40, action_echeance: 'archiver' },
  ] })
  gedApi.getDemandesDisposition.mockResolvedValue({
    data: [{
      id: 3, libelle: 'Purge devis 2023', action: 'detruire', documents: [12],
      statut: 'en_attente', demandeur_nom: 'Reda', approbateur_nom: null,
      commentaire: '', certificats: [], created_at: '2026-08-01T09:00:00Z',
    }],
  })
})

describe('PACT134 RetentionPage — Dispositions', () => {
  it('liste les demandes de disposition et propose un nouveau lot', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Dispositions' }))
    expect(await screen.findByText('Purge devis 2023')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Nouvelle demande/i }))
    await userEvent.type(screen.getByLabelText('Libellé du lot'), 'Purge devis 2022')
    await userEvent.click(screen.getByLabelText('Documents échus concernés'))
    const listbox = await screen.findByRole('listbox')
    await userEvent.click(within(listbox).getByText('Vieux-devis.pdf'))
    await userEvent.click(screen.getByRole('button', { name: 'Proposer' }))

    await waitFor(() => {
      expect(gedApi.createDemandeDisposition).toHaveBeenCalledWith({
        libelle: 'Purge devis 2022', action: 'detruire', documents: ['12'],
      })
      expect(toast.success).toHaveBeenCalledWith('Demande de disposition créée.')
    })
  })

  it('approuve une demande en attente', async () => {
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Dispositions' }))
    await screen.findByText('Purge devis 2023')

    await userEvent.click(screen.getByRole('button', { name: 'Approuver' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approuver' }))

    await waitFor(() => {
      expect(gedApi.approuverDisposition).toHaveBeenCalledWith(3, { commentaire: '' })
      expect(toast.success).toHaveBeenCalledWith('Demande approuvée.')
    })
  })

  it('exécute une demande approuvée après confirmation et affiche les certificats émis', async () => {
    gedApi.getDemandesDisposition.mockResolvedValueOnce({
      data: [{
        id: 4, libelle: 'Purge devis 2021', action: 'detruire', documents: [12],
        statut: 'approuvee', demandeur_nom: 'Reda', approbateur_nom: 'Meryem',
        commentaire: '', certificats: [], created_at: '2026-08-01T09:00:00Z',
      }],
    })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Dispositions' }))
    await screen.findByText('Purge devis 2021')

    await userEvent.click(screen.getByRole('button', { name: 'Exécuter' }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(
      await within(dialog).findByRole('button', { name: 'Exécuter définitivement' }))

    await waitFor(() => {
      expect(gedApi.executerDisposition).toHaveBeenCalledWith(4)
      expect(toast.success).toHaveBeenCalledWith('Disposition exécutée.')
    })
  })

  it('affiche les certificats émis d’une demande exécutée', async () => {
    gedApi.getDemandesDisposition.mockResolvedValueOnce({
      data: [{
        id: 5, libelle: 'Purge devis 2020', action: 'detruire', documents: [12],
        statut: 'executee', demandeur_nom: 'Reda', approbateur_nom: 'Meryem',
        commentaire: '', created_at: '2026-08-01T09:00:00Z',
        certificats: [{
          id: 77, demande: 5, document_id_origine: 12, document_nom: 'Vieux-devis.pdf',
          politique_appliquee: 'Devis (365 j)', hash_metadonnees: 'abc123',
          detruit_le: '2026-08-02T10:00:00Z', detruit_par: 2, detruit_par_nom: 'Reda',
        }],
      }],
    })
    renderPage()
    await userEvent.click(await screen.findByRole('tab', { name: 'Dispositions' }))
    await screen.findByText('Purge devis 2020')

    await userEvent.click(screen.getByRole('button', { name: 'Voir les certificats' }))
    expect(await screen.findByText('Devis (365 j)')).toBeInTheDocument()
  })
})
