import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// U14 — la GED n'est plus en lecture seule : on couvre les NOUVEAUX chemins
// d'écriture (créer une armoire / un dossier, renommer, déplacer, téléverser un
// document) + l'état vide qui guide le premier usage. Le module API est mocké :
// on vérifie que l'UI appelle les bons endpoints avec les bons corps.
vi.mock('../../api/gedApi', () => ({
  default: {
    getCabinets: vi.fn(),
    createCabinet: vi.fn(),
    getDossiers: vi.fn(),
    createDossier: vi.fn(),
    renameDossier: vi.fn(),
    moveDossier: vi.fn(),
    getDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    searchDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    semanticSearch: vi.fn(() => Promise.resolve({ data: [] })),
    // ZGED7/8/13 — favoris/récents/vues (rendus par GedSearch, monté ici).
    getMesFavoris: vi.fn(() => Promise.resolve({ data: { dossiers: [], documents: [] } })),
    getMesRecents: vi.fn(() => Promise.resolve({ data: { consultes: [], deposes: [] } })),
    getVues: vi.fn(() => Promise.resolve({ data: [] })),
    createVue: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    deleteVue: vi.fn(() => Promise.resolve({ data: {} })),
    // GED14 — aperçu inline.
    getVersions: vi.fn(() => Promise.resolve({ data: [] })),
    apercuVersionUrl: (id) => `/api/django/ged/versions/${id}/apercu/`,
    // GED16 — check-out / check-in ; GED26 — corbeille.
    checkOutDocument: vi.fn(() => Promise.resolve({ data: {} })),
    checkInDocument: vi.fn(() => Promise.resolve({ data: {} })),
    mettreEnCorbeille: vi.fn(() => Promise.resolve({ data: {} })),
    // XGED14 — opérations en lot.
    operationsLot: vi.fn(() => Promise.resolve({ data: { resultats: [], erreurs: [] } })),
    // WIR204 — ZIP de lot (blob DÉDIÉ) + restauration d'une version antérieure.
    telechargerZipLot: vi.fn(() => Promise.resolve({ data: new Blob(['zip']) })),
    restaurerVersionDocument: vi.fn(() => Promise.resolve({ data: { id: 24, numero: 3 } })),
    // WIR249 — surfaces de second rang.
    docqa: vi.fn(() => Promise.resolve({ data: { enabled: false, results: [] } })),
    ocrPieceDocument: vi.fn(() => Promise.resolve({ data: { metadonnees: {} } })),
    verrouillerDocument: vi.fn(() => Promise.resolve({ data: {} })),
    deverrouillerDocument: vi.fn(() => Promise.resolve({ data: {} })),
    changerCycleVieDocument: vi.fn(() => Promise.resolve({ data: {} })),
    officeOuvrirDocument: vi.fn(() => Promise.resolve({
      data: { editor_url: 'https://office.example/edit/8', document_id: 8 },
    })),
    // XGED24 — caviardage.
    caviarderDocument: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
    // XGED10/17 — scission, fusion, comparaison de versions.
    scinderDocument: vi.fn(() => Promise.resolve({ data: [{ id: 100 }, { id: 101 }] })),
    fusionnerDocuments: vi.fn(() => Promise.resolve({ data: { id: 102 } })),
    comparerVersions: vi.fn(() => Promise.resolve({ data: {
      metadonnees: { size: { v1: 100, v2: 200 } }, texte_disponible: false,
      message: 'Comparaison binaire indisponible.',
    } })),
  },
}))

// Toaster s'appuie sur un ThemeProvider absent du test — on neutralise `toast`.
vi.mock('../../ui/Toaster', () => ({
  Toaster: () => null,
  toast: { success: vi.fn(), error: vi.fn() },
}))

import gedApi from '../../api/gedApi'
import GedNavigator from './GedNavigator'
// VX152 — GedNavigator rend désormais le moteur DataTable partagé, qui lit la
// densité via useTheme : comme tout écran consommant DataTable, le test doit
// fournir le ThemeProvider (cf. flotte/*Screen.test.jsx, RolesManagement.test.jsx).
import { ThemeProvider } from '../../design/ThemeProvider'
// Le moteur DataTable appelle TOUJOURS useSearchParams (hook, même sans
// persistToUrl) → il lui faut aussi un <Router>, en plus du <ThemeProvider>.
import { MemoryRouter } from 'react-router-dom'

const ok = (data) => Promise.resolve({ data })
const renderGed = () =>
  render(
    <ThemeProvider>
      <MemoryRouter>
        <GedNavigator />
      </MemoryRouter>
    </ThemeProvider>,
  )

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getCabinets.mockResolvedValue(ok([]))
  gedApi.getDossiers.mockResolvedValue(ok([]))
  gedApi.getDocuments.mockResolvedValue(ok([]))
})

describe('GedNavigator — écriture (U14)', () => {
  it('état vide guide le premier usage et permet de créer une armoire', async () => {
    gedApi.createCabinet.mockResolvedValue(ok({ id: 7, nom: 'Administratif' }))
    // Après création, le rechargement renvoie la nouvelle armoire.
    gedApi.getCabinets
      .mockResolvedValueOnce(ok([])) // montage : aucune armoire
      .mockResolvedValue(ok([{ id: 7, nom: 'Administratif' }]))

    renderGed()

    // L'état vide propose explicitement de créer la première armoire.
    const cta = await screen.findByRole('button', { name: /première armoire/i })
    await userEvent.click(cta)

    const dialog = await screen.findByRole('dialog')
    await userEvent.type(
      within(dialog).getByLabelText("Nom de l'armoire"), 'Administratif')
    await userEvent.click(
      within(dialog).getByRole('button', { name: /Créer l'armoire/i }))

    await waitFor(() => expect(gedApi.createCabinet).toHaveBeenCalledWith({ nom: 'Administratif' }))
  })

  it('crée un dossier dans le cabinet courant', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([]))
    gedApi.createDossier.mockResolvedValue(ok({ id: 9, nom: 'Contrats' }))

    renderGed()

    // L'arbre vide propose de créer un dossier.
    const btn = await screen.findByRole('button', { name: /Créer un dossier/i })
    await userEvent.click(btn)

    const dialog = await screen.findByRole('dialog')
    await userEvent.type(
      within(dialog).getByLabelText('Nom du dossier'), 'Contrats')
    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(gedApi.createDossier).toHaveBeenCalled())
    expect(gedApi.createDossier.mock.calls[0][0]).toMatchObject({
      cabinet: 1, nom: 'Contrats',
    })
  })

  it('téléverse un document dans le dossier sélectionné', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([]))
    gedApi.uploadDocument.mockResolvedValue(ok({ id: 3, nom: 'cni.pdf' }))

    renderGed()

    // Sélectionne le dossier dans l'arbre.
    const folderBtn = await screen.findByText('Docs')
    await userEvent.click(folderBtn)

    // Le bouton « Téléverser » ouvre le dialogue d'upload.
    const upBtn = await screen.findByRole('button', { name: /Téléverser un document/i })
    await userEvent.click(upBtn)

    const dialog = await screen.findByRole('dialog')
    const input = dialog.querySelector('input[type="file"]')
    const file = new File(['%PDF-1.4'], 'cni.pdf', { type: 'application/pdf' })
    await userEvent.upload(input, file)

    await userEvent.click(
      within(dialog).getByRole('button', { name: 'Téléverser' }))

    await waitFor(() => expect(gedApi.uploadDocument).toHaveBeenCalled())
    expect(gedApi.uploadDocument.mock.calls[0][0]).toMatchObject({ folder: 5 })
    expect(gedApi.uploadDocument.mock.calls[0][0].file).toBeInstanceOf(File)
  })

  it('GED14 — clic sur un document ouvre l’aperçu inline', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', version_count: 1, updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getVersions.mockResolvedValue(ok([
      { id: 22, numero: 1, mime: 'application/pdf', filename: 'facture.pdf' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))

    // Le bouton « Aperçu » de la ligne ouvre la modale.
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de facture\.pdf/i }))

    const dialog = await screen.findByRole('dialog')
    await waitFor(() => expect(gedApi.getVersions).toHaveBeenCalledWith({ document: 8 }))
    // L'aperçu PDF est rendu dans un iframe pointant sur le proxy même-origine.
    await waitFor(() => {
      const iframe = dialog.querySelector('iframe')
      expect(iframe).toBeTruthy()
      expect(iframe.getAttribute('src')).toContain('/ged/versions/22/apercu/')
    })
  })

  it('XGED24 — caviarde une zone du PDF depuis l’aperçu (copie, original intact)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', version_count: 1, updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getVersions.mockResolvedValue(ok([
      { id: 22, numero: 1, mime: 'application/pdf', filename: 'facture.pdf' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de facture\.pdf/i }))
    await waitFor(() => expect(gedApi.getVersions).toHaveBeenCalledWith({ document: 8 }))

    await userEvent.click(await screen.findByRole('button', { name: /Caviarder…/i }))
    await userEvent.click(await screen.findByRole('button', { name: /^Caviarder$/i }))

    await waitFor(() => expect(gedApi.caviarderDocument).toHaveBeenCalledWith(8, {
      zones: [{ page: 0, x0: 0, y0: 0, x1: 20, y1: 10 }], version: 22,
    }))
  })

  it('XGED10 — scinde un PDF depuis l’aperçu (points de coupe)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', version_count: 1, updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getVersions.mockResolvedValue(ok([
      { id: 22, numero: 1, mime: 'application/pdf', filename: 'facture.pdf' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de facture\.pdf/i }))
    await waitFor(() => expect(gedApi.getVersions).toHaveBeenCalledWith({ document: 8 }))

    await userEvent.click(await screen.findByRole('button', { name: /^Scinder…$/i }))
    await userEvent.type(await screen.findByLabelText('Points de coupe'), '1, 3')
    await userEvent.click(screen.getByRole('button', { name: /^Scinder$/i }))

    await waitFor(() => expect(gedApi.scinderDocument).toHaveBeenCalledWith(8, {
      pointsDeCoupe: [1, 3], version: 22,
    }))
  })

  it('XGED10 — fusionne les documents sélectionnés depuis la barre en lot', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'a.pdf', updated_at: '2026-06-01T10:00:00Z' },
      { id: 9, nom: 'b.pdf', updated_at: '2026-06-02T10:00:00Z' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('checkbox', { name: /Sélectionner a\.pdf/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Sélectionner b\.pdf/i }))

    await userEvent.click(await screen.findByRole('button', { name: /^Fusionner$/i }))
    await userEvent.click(await screen.findByRole('button', { name: /^Fusionner$/i }))

    await waitFor(() => expect(gedApi.fusionnerDocuments).toHaveBeenCalledWith({
      documents: [8, 9], nom: undefined,
    }))
  })

  it('XGED17 — compare deux versions d’un document', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', version_count: 2, updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getVersions.mockResolvedValue(ok([
      { id: 22, numero: 1, mime: 'application/pdf', filename: 'facture.pdf' },
      { id: 23, numero: 2, mime: 'application/pdf', filename: 'facture.pdf' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de facture\.pdf/i }))
    await waitFor(() => expect(gedApi.getVersions).toHaveBeenCalledWith({ document: 8 }))

    await userEvent.click(await screen.findByRole('button', { name: /Comparer versions…/i }))
    await userEvent.click(await screen.findByRole('button', { name: /^Comparer$/i }))

    await waitFor(() => expect(gedApi.comparerVersions).toHaveBeenCalledWith(8, '22', '23'))
    expect(await screen.findByText('Comparaison binaire indisponible.')).toBeInTheDocument()
  })

  it('GED16 — extrait un document (check-out)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', is_locked: false, updated_at: '2026-06-01T10:00:00Z' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('button', { name: /Extraire facture\.pdf/i }))

    await waitFor(() => expect(gedApi.checkOutDocument).toHaveBeenCalledWith(8))
  })

  it('XGED14 — sélection + mise en corbeille par lot', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'a.pdf', updated_at: '2026-06-01T10:00:00Z' },
      { id: 9, nom: 'b.pdf', updated_at: '2026-06-02T10:00:00Z' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))

    // Coche deux documents.
    await userEvent.click(await screen.findByRole('checkbox', { name: /Sélectionner a\.pdf/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Sélectionner b\.pdf/i }))

    // La barre d'actions apparaît → mise en corbeille par lot.
    await userEvent.click(await screen.findByRole('button', { name: /Mettre en corbeille/i }))

    await waitFor(() => expect(gedApi.operationsLot).toHaveBeenCalledWith({
      documents: [8, 9], operation: 'corbeille',
    }))
  })

  it('WIR204 — ZIP du lot : wrapper DÉDIÉ (blob), jamais operationsLot générique', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'a.pdf', updated_at: '2026-06-01T10:00:00Z' },
      { id: 9, nom: 'b.pdf', updated_at: '2026-06-02T10:00:00Z' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('checkbox', { name: /Sélectionner a\.pdf/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Sélectionner b\.pdf/i }))

    await userEvent.click(await screen.findByTestId('ged-bulk-zip'))
    await waitFor(() => expect(gedApi.telechargerZipLot).toHaveBeenCalledWith([8, 9]))
    // L'appel JSON générique décoderait l'archive en texte : jamais utilisé ici.
    expect(gedApi.operationsLot).not.toHaveBeenCalled()
  })

  it('WIR204 — déplacement par lot : les erreurs par document sont RAPPORTÉES', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
      { id: 6, nom: 'Archives', cabinet: 1, parent: null, path: '/6/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'a.pdf', updated_at: '2026-06-01T10:00:00Z' },
      { id: 9, nom: 'b.pdf', updated_at: '2026-06-02T10:00:00Z' },
    ]))
    gedApi.operationsLot.mockResolvedValue(ok({
      resultats: [{ document: 8, ok: true }],
      erreurs: [{ document: 9, erreur: 'Document sous conservation légale.' }],
    }))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('checkbox', { name: /Sélectionner a\.pdf/i }))
    await userEvent.click(screen.getByRole('checkbox', { name: /Sélectionner b\.pdf/i }))
    await userEvent.click(await screen.findByTestId('ged-bulk-move'))
    await userEvent.click(await screen.findByTestId('ged-bulk-confirm'))

    await waitFor(() => expect(gedApi.operationsLot).toHaveBeenCalledWith({
      documents: [8, 9], operation: 'deplacer', params: { folder: '5' },
    }))
  })

  it('WIR204 — tagger par lot envoie {tag} (jamais un corps deviné)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'a.pdf', updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getTags.mockResolvedValue(ok([{ id: 3, nom: 'Contrats' }]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('checkbox', { name: /Sélectionner a\.pdf/i }))
    await userEvent.click(await screen.findByTestId('ged-bulk-tag'))
    await userEvent.click(await screen.findByTestId('ged-bulk-confirm'))

    await waitFor(() => expect(gedApi.operationsLot).toHaveBeenCalledWith({
      documents: [8], operation: 'tagger', params: { tag: '3' },
    }))
  })

  it('WIR204 — restaure une version antérieure depuis l\'écran de versions', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', version_count: 2, updated_at: '2026-06-01T10:00:00Z' },
    ]))
    gedApi.getVersions.mockResolvedValue(ok([
      { id: 22, numero: 1, mime: 'application/pdf', filename: 'facture.pdf' },
      { id: 23, numero: 2, mime: 'application/pdf', filename: 'facture.pdf' },
    ]))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByRole('button', { name: /Aperçu de facture\.pdf/i }))
    await userEvent.click(await screen.findByRole('button', { name: /Comparer versions…/i }))
    await userEvent.click(await screen.findByTestId('ged-restaurer-version'))

    // GED15 : le corps porte l'id de la VERSION source (additif côté serveur).
    await waitFor(() => expect(gedApi.restaurerVersionDocument)
      .toHaveBeenCalledWith(8, '22'))
  })

  it('renomme le dossier sélectionné', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([]))
    gedApi.renameDossier.mockResolvedValue(ok({ id: 5, nom: 'Archives' }))

    renderGed()
    await userEvent.click(await screen.findByText('Docs'))

    await userEvent.click(await screen.findByRole('button', { name: /Renommer/i }))
    const dialog = await screen.findByRole('dialog')
    const field = within(dialog).getByLabelText('Nom du dossier')
    await userEvent.clear(field)
    await userEvent.type(field, 'Archives')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Valider' }))

    await waitFor(() => expect(gedApi.renameDossier).toHaveBeenCalledWith(5, 'Archives'))
  })
})

/* WIR249 — surfaces GED de second rang, jusqu'ici sans aucun appelant :
   DocQA (FG352), OCR de pièce (GED33), verrou d'AVERTISSEMENT (ZGED9, distinct
   du check-out GED16), cycle de vie (GED17) et éditeur Office (XGED30). */
describe('GedNavigator — WIR249 surfaces de second rang', () => {
  const ouvrirAvance = async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'cin.pdf', statut: 'brouillon', updated_at: '2026-06-01T10:00:00Z' },
    ]))
    renderGed()
    await userEvent.click(await screen.findByText('Docs'))
    await userEvent.click(await screen.findByTestId('ged-avance-8'))
  }

  it('FG352 — DocQA : sans clé d\'indexation, l\'écran le DIT (jamais un vide qui ment)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([]))
    gedApi.getDocuments.mockResolvedValue(ok([]))
    renderGed()
    await userEvent.type(await screen.findByTestId('ged-docqa-q'), 'Où est le contrat ?')
    await userEvent.click(screen.getByTestId('ged-docqa-ask'))
    await waitFor(() => expect(gedApi.docqa).toHaveBeenCalledWith('Où est le contrat ?', 5))
    expect(await screen.findByTestId('ged-docqa-disabled')).toBeInTheDocument()
  })

  it('FG352 — DocQA : les extraits GED et base de connaissances sont rendus', async () => {
    gedApi.docqa.mockResolvedValue(ok({ enabled: true, results: [
      { source: 'ged', document: 8, document_nom: 'Contrat.pdf', chunk_index: 0,
        texte: 'Le délai est de 30 jours.', distance: 0.1 },
      { source: 'kb', article: 3, article_titre: 'Procédure achat', chunk_index: 1,
        texte: 'Toute commande passe par un BC.', distance: 0.2 },
    ] }))
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([]))
    gedApi.getDocuments.mockResolvedValue(ok([]))
    renderGed()
    await userEvent.type(await screen.findByTestId('ged-docqa-q'), 'délai ?')
    await userEvent.click(screen.getByTestId('ged-docqa-ask'))
    await waitFor(() => expect(screen.getAllByTestId('ged-docqa-result')).toHaveLength(2))
    expect(screen.getByText('Contrat.pdf')).toBeInTheDocument()
    expect(screen.getByText('Procédure achat')).toBeInTheDocument()
  })

  it('GED33 — OCR de pièce : envoie le type choisi', async () => {
    await ouvrirAvance()
    await userEvent.click(await screen.findByTestId('ged-ocr-piece'))
    await waitFor(() => expect(gedApi.ocrPieceDocument).toHaveBeenCalledWith(8, undefined))
  })

  it('ZGED9 — verrou d\'AVERTISSEMENT (distinct du check-out) avec son motif', async () => {
    await ouvrirAvance()
    await userEvent.type(await screen.findByTestId('ged-verrou-motif'), 'relecture juridique')
    await userEvent.click(screen.getByTestId('ged-verrouiller'))
    await waitFor(() => expect(gedApi.verrouillerDocument)
      .toHaveBeenCalledWith(8, 'relecture juridique'))
    // Le check-out GED16 est un AUTRE verrou : il ne doit pas être touché.
    expect(gedApi.checkOutDocument).not.toHaveBeenCalled()
  })

  it('GED17 — cycle de vie : POSTe le statut cible (le serveur reste juge)', async () => {
    await ouvrirAvance()
    await userEvent.click(await screen.findByTestId('ged-cycle-vie'))
    await waitFor(() => expect(gedApi.changerCycleVieDocument)
      .toHaveBeenCalledWith(8, 'brouillon'))
  })

  it('XGED30 — éditeur Office : ouvre l\'adresse renvoyée par le serveur', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    await ouvrirAvance()
    await userEvent.click(await screen.findByTestId('ged-office-ouvrir'))
    await waitFor(() => expect(gedApi.officeOuvrirDocument).toHaveBeenCalledWith(8))
    await waitFor(() => expect(openSpy)
      .toHaveBeenCalledWith('https://office.example/edit/8', '_blank', 'noopener'))
    openSpy.mockRestore()
  })
})
