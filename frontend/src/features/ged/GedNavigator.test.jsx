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
    // GED14 — aperçu inline.
    getVersions: vi.fn(() => Promise.resolve({ data: [] })),
    apercuVersionUrl: (id) => `/api/django/ged/versions/${id}/apercu/`,
    // GED16 — check-out / check-in ; GED26 — corbeille.
    checkOutDocument: vi.fn(() => Promise.resolve({ data: {} })),
    checkInDocument: vi.fn(() => Promise.resolve({ data: {} })),
    mettreEnCorbeille: vi.fn(() => Promise.resolve({ data: {} })),
    // XGED14 — opérations en lot.
    operationsLot: vi.fn(() => Promise.resolve({ data: { resultats: [], erreurs: [] } })),
  },
}))

// Toaster s'appuie sur un ThemeProvider absent du test — on neutralise `toast`.
vi.mock('../../ui/Toaster', () => ({
  Toaster: () => null,
  toast: { success: vi.fn(), error: vi.fn() },
}))

import gedApi from '../../api/gedApi'
import GedNavigator from './GedNavigator'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// VX38 — les documents sont désormais rendus par le moteur DataTable, qui lit
// la densité via `useDensity()`/`useTheme()` (lève sans <ThemeProvider>) et
// utilise des popovers Radix (menu kebab) qui appellent ResizeObserver.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
}
function renderNav(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

const ok = (data) => Promise.resolve({ data })

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

    renderNav(<GedNavigator />)

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

    renderNav(<GedNavigator />)

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

    renderNav(<GedNavigator />)

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

  it('VX38 — fil d’Ariane Armoire › Dossier au-dessus des documents', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Administratif' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Contrats', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([]))

    renderNav(<GedNavigator />)
    await userEvent.click(await screen.findByText('Contrats'))

    const breadcrumb = await screen.findByRole('navigation', { name: "Fil d'Ariane" })
    expect(within(breadcrumb).getByText('Administratif')).toBeInTheDocument()
    expect(within(breadcrumb).getByText('Contrats')).toBeInTheDocument()
  })

  it('VX38 — porte DataTable : tri/recherche disponibles sur les documents', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', updated_at: '2026-06-01T10:00:00Z' },
      { id: 9, nom: 'rapport.xlsx', updated_at: '2026-06-02T10:00:00Z' },
    ]))

    renderNav(<GedNavigator />)
    await userEvent.click(await screen.findByText('Docs'))

    // Le moteur DataTable expose une recherche — gagnée par le portage VX38,
    // absente de l'ancien <table> fait main.
    const search = await screen.findByPlaceholderText('Rechercher un document…')
    await userEvent.type(search, 'facture')

    expect(await screen.findByText('facture.pdf')).toBeInTheDocument()
    expect(screen.queryByText('rapport.xlsx')).not.toBeInTheDocument()
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

    renderNav(<GedNavigator />)
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

  it('GED16 — extrait un document (check-out)', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([
      { id: 8, nom: 'facture.pdf', is_locked: false, updated_at: '2026-06-01T10:00:00Z' },
    ]))

    renderNav(<GedNavigator />)
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

    renderNav(<GedNavigator />)
    await userEvent.click(await screen.findByText('Docs'))

    // VX38 — la sélection vit désormais dans le moteur DataTable (le même
    // qu'admin RolesManagement/UsersManagement) : chaque case à cocher de
    // ligne porte l'aria-label générique "Sélectionner la ligne N" (au lieu
    // du nom du document) — comportement standard du moteur, pas une
    // régression fonctionnelle (le lot ciblé reste correct, vérifié via
    // `operationsLot` ci-dessous).
    await userEvent.click(await screen.findByRole('checkbox', { name: 'Sélectionner la ligne 1' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'Sélectionner la ligne 2' }))

    // La barre d'actions apparaît → mise en corbeille par lot.
    await userEvent.click(await screen.findByRole('button', { name: /Mettre en corbeille/i }))

    await waitFor(() => expect(gedApi.operationsLot).toHaveBeenCalledWith({
      documents: [8, 9], operation: 'corbeille',
    }))
  })

  it('renomme le dossier sélectionné', async () => {
    gedApi.getCabinets.mockResolvedValue(ok([{ id: 1, nom: 'Cab' }]))
    gedApi.getDossiers.mockResolvedValue(ok([
      { id: 5, nom: 'Docs', cabinet: 1, parent: null, path: '/5/' },
    ]))
    gedApi.getDocuments.mockResolvedValue(ok([]))
    gedApi.renameDossier.mockResolvedValue(ok({ id: 5, nom: 'Archives' }))

    renderNav(<GedNavigator />)
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
