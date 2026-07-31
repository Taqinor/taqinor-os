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
import ChecklistPage from './ChecklistPage.jsx'

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
    // XGED2/XGED3 — circuit multi-signataires + champs positionnés.
    getRolesSignataire: vi.fn(() => Promise.resolve({ data: [] })),
    creerDemandeMultiSignataires: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    getChampsSignature: vi.fn(() => Promise.resolve({ data: [] })),
    createChampSignature: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    deleteChampSignature: vi.fn(() => Promise.resolve({ data: {} })),
    annulerDemandeSignature: vi.fn(() => Promise.resolve({ data: {} })),
    // WIR164 — checklist (XGED8), validation OCR (XGED13), tampons (XGED16).
    getDossiers: vi.fn(() => Promise.resolve({ data: [] })),
    getCabinets: vi.fn(() => Promise.resolve({ data: [] })),
    getExigences: vi.fn(() => Promise.resolve({ data: [] })),
    getDemandesDocument: vi.fn(() => Promise.resolve({ data: [] })),
    getValidationsOcr: vi.fn(() => Promise.resolve({ data: [] })),
    getTamponsSociete: vi.fn(() => Promise.resolve({ data: [] })),
    getStampsDisponibles: vi.fn(() => Promise.resolve({
      data: ['Payé', 'Validé', 'Confidentiel'],
    })),
    getChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    createExigence: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    deleteExigence: vi.fn(() => Promise.resolve({ data: {} })),
    createDemandeDocument: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    relancerDemandeDocument: vi.fn(() => Promise.resolve({ data: {} })),
    validerOcr: vi.fn(() => Promise.resolve({ data: {} })),
    createTamponSociete: vi.fn(() => Promise.resolve({ data: { id: 9, libelle: 'Archivé RH' } })),
    deleteTamponSociete: vi.fn(() => Promise.resolve({ data: {} })),
    getVersions: vi.fn(() => Promise.resolve({ data: [{ id: 55, version: 1 }] })),
    createAnnotation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
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

  it('XGED2 — le circuit multi-signataires ajoute/retire des destinataires ordonnés', async () => {
    gedApi.getDocumentsList.mockResolvedValue({
      data: [{ id: 4, nom: 'Bail.pdf' }],
    })
    renderPage(<ApprobationPage />)
    await userEvent.click(await screen.findByRole('tab', { name: 'Signatures' }))
    await userEvent.click(await screen.findByRole('button', { name: /Circuit multi-signataires/i }))

    // Un destinataire de départ + le routage séquentiel par défaut.
    expect(await screen.findByText(/Ordre de signature/i)).toBeInTheDocument()
    expect(screen.getAllByPlaceholderText('Nom')).toHaveLength(1)

    // Ajout d'un 2e destinataire (les ordres 1, 2 sont posés à la création).
    await userEvent.click(screen.getByRole('button', { name: /Ajouter un destinataire/i }))
    expect(screen.getAllByPlaceholderText('Nom')).toHaveLength(2)

    // Retrait du 2e destinataire.
    await userEvent.click(screen.getByRole('button', { name: /Retirer le destinataire 2/i }))
    expect(screen.getAllByPlaceholderText('Nom')).toHaveLength(1)
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

describe('WIR164 ChecklistPage', () => {
  it('rend les onglets checklist/exigences/demandes/OCR/tampons sans planter', async () => {
    renderPage(<ChecklistPage />)
    expect(await screen.findByRole('tab', { name: /Checklist/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Exigences' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Demandes de pièces' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Validation OCR' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Tampons/ })).toBeInTheDocument()
  })

  it('crée un tampon société propre depuis le formulaire (WIR164)', async () => {
    renderPage(<ChecklistPage />)
    await userEvent.click(await screen.findByRole('tab', { name: /Tampons/ }))
    await userEvent.click(screen.getByRole('button', { name: /Nouveau tampon/i }))
    await userEvent.type(screen.getByPlaceholderText('Ex. Archivé RH'), 'Archivé RH')
    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => {
      expect(gedApi.createTamponSociete).toHaveBeenCalledWith({ libelle: 'Archivé RH' })
      expect(toast.success).toHaveBeenCalledWith('Tampon créé.')
    })
  })

  it('appose un tampon sur la dernière version d’un document (WIR164)', async () => {
    gedApi.getDocumentsList.mockResolvedValueOnce({
      data: [{ id: 4, nom: 'Bail.pdf' }],
    })
    renderPage(<ChecklistPage />)
    await userEvent.click(await screen.findByRole('tab', { name: /Tampons/ }))
    await userEvent.click(screen.getByRole('button', { name: /Apposer un tampon/i }))

    await userEvent.click(screen.getByRole('combobox', { name: /Choisir un document/i }))
    await userEvent.click(await screen.findByText('Bail.pdf'))
    await userEvent.click(screen.getByRole('combobox', { name: /Choisir un tampon/i }))
    await userEvent.click(await screen.findByText('Payé'))
    await userEvent.click(screen.getByRole('button', { name: 'Apposer' }))

    await waitFor(() => {
      expect(gedApi.getVersions).toHaveBeenCalledWith({ document: '4' })
      expect(gedApi.createAnnotation).toHaveBeenCalledWith({
        version: 55, type_annotation: 'tampon', page: 0, x: 10, y: 10, contenu: 'Payé',
      })
      expect(toast.success).toHaveBeenCalledWith('Tampon apposé.')
    })
  })
})
