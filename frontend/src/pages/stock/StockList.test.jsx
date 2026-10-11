import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   STKCAT14 — le rail de catégories filtre par ID, jamais par nom.
   Régression 851e1e3c (2026-06-21) : le rail posait `activeCat` (nom) mais le
   memo `filtered` ne le lisait plus jamais — cliquer une catégorie ne
   filtrait rien. Ce fichier est le PREMIER test d'écran de StockList.

   Harnais copié du patron `MouvementsPage.test.jsx` / `FournisseursStock.test.jsx`
   (store redux minimal `{ auth, stock }`, stockSlice mocké en actions noop) —
   étendu ici avec les mocks nécessaires aux dépendances lourdes de StockList
   (PilotageStock, vues enregistrées serveur) qui n'ont rien à voir avec le
   rail de catégories.
   ========================================================================== */

// ASTK252 — stockApi RÉEL : seule la frontière HTTP `../../api/axios` est
// simulée ; les assertions portent sur la méthode et l'URL réellement appelées.
const http = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
}))
vi.mock('../../api/axios', () => ({ default: http }))
vi.mock('../../api/stockApi', () => vi.importActual('../../api/stockApi'))
const URL_INVENTAIRE = '/stock/produits/inventaire/'
const postsInventaire = () => http.post.mock.calls.filter(([url]) => url === URL_INVENTAIRE)

// ASTK83 — capture le rappel « Annuler » du toast de désarchivage.
vi.mock('../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastWithUndo: vi.fn() }
})

vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchProduits: () => ({ type: 'stock/fetchProduits/noop' }),
  fetchProduitsArchived: () => ({ type: 'stock/fetchProduitsArchived/noop' }),
  fetchCategories: () => ({ type: 'stock/fetchCategories/noop' }),
  updateProduit: () => ({ type: 'stock/updateProduit/noop' }),
  deleteProduit: vi.fn(() => ({ type: 'stock/deleteProduit/noop' })),
  // ASTK83 — thunk simulé : `dispatch(unarchiveProduit(id)).unwrap()`.
  unarchiveProduit: () => () => ({ unwrap: () => Promise.resolve({}) }),
  forceDeleteArchivedProduit: () => ({ type: 'stock/forceDeleteArchivedProduit/noop' }),
}))

// PilotageStock (VX33) tire son propre store singleton + stockApi + charts :
// hors sujet pour le rail de catégories, ouvert par défaut sur StockList
// (`showPilotage` initial `true`) — un stub évite tout ce bruit.
vi.mock('./PilotageStock', () => ({ default: () => null }))

// Vues enregistrées serveur (NTUX2) : `createViewMock` exporté par le mock
// pour espionner l'appel de `saveCurrentStockView` (aller-retour de vue).
vi.mock('../../features/uxviews/useServerSavedViews', () => {
  const createView = vi.fn().mockResolvedValue({})
  return {
    __esModule: true,
    createViewMock: createView,
    useServerSavedViews: () => ({ createView }),
    default: () => ({ createView }),
  }
})

// Stub du popover réel (liste/gère les vues serveur) : deux boutons de test
// simulent l'application d'une vue déjà enregistrée — nouveau format
// (`activeCatIds`) et ancien format hérité (`activeCat`, nom).
vi.mock('../../features/uxviews/ViewsManagerPopover', () => ({
  default: ({ onApply }) => (
    <div>
      <button type="button" onClick={() => onApply({ activeCatIds: [2] })}>
        __apply_view_activeCatIds__
      </button>
      <button type="button" onClick={() => onApply({ activeCat: 'Onduleurs' })}>
        __apply_view_legacy_onduleurs__
      </button>
      <button type="button" onClick={() => onApply({ activeCat: 'Categorie Disparue' })}>
        __apply_view_legacy_inconnue__
      </button>
    </div>
  ),
}))

import { toastWithUndo } from '../../lib/toast'
import { deleteProduit } from '../../features/stock/store/stockSlice'
import { createViewMock } from '../../features/uxviews/useServerSavedViews'
import StockList from './StockList.jsx'
import { installJsdomPolyfills } from './__tests__/jsdomPolyfills.js'

const CAT_PANNEAUX = { id: 1, nom: 'Panneaux', ordre: 1 }
const CAT_ONDULEURS = { id: 2, nom: 'Onduleurs', ordre: 2 }

const baseProduit = (over = {}) => ({
  id: 1,
  nom: 'Panneau 550 Wc',
  sku: 'PAN-550',
  marque: 'JA Solar',
  prix_vente: '1000',
  prix_achat: '700',
  tva: 20,
  quantite_stock: 12,
  quantite_reservee: 0,
  quantite_disponible: 12,
  seuil_alerte: 5,
  is_low_stock: false,
  is_archived: false,
  categorie: CAT_PANNEAUX,
  ...over,
})

const panneau = baseProduit({ id: 1, nom: 'Panneau 550 Wc', sku: 'PAN-550', categorie: CAT_PANNEAUX })
const onduleur = baseProduit({
  id: 2, nom: 'Onduleur Deye 5 kW', sku: 'OND-DEY-5', categorie: CAT_ONDULEURS,
})
const orphelin = baseProduit({
  id: 3, nom: 'Produit Sans Categorie', sku: 'ORPH-1', categorie: null,
})

function makeStore({
  role = 'admin', permissions = [],
  produits = [panneau, onduleur, orphelin],
  categories = [CAT_PANNEAUX, CAT_ONDULEURS],
  produitsArchived = [],
} = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, role_nom: role, permissions }) => s,
      stock: (s = {
        produits, produitsArchived, categories, loading: false, error: null,
      }) => s,
    },
  })
}

function renderPage(opts) {
  return render(
    <Provider store={makeStore(opts)}>
      <MemoryRouter>
        <ThemeProvider><StockList /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  http.get.mockResolvedValue({ data: [] })
  http.post.mockImplementation(async (url) => ({
    data: url === '/stock/produits/export-xlsx/' ? new Blob(['x']) : {} }))
  http.patch.mockResolvedValue({ data: {} })
  http.delete.mockResolvedValue({ status: 204, data: {} })
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
  installJsdomPolyfills()
})

describe('StockList — rail de catégories filtre par ID (STKCAT14)', () => {
  it('clic sur une catégorie → seuls ses produits restent affichés', () => {
    renderPage()
    // Le catalogue complet est visible au départ (chaque produit peut être
    // rendu deux fois : ligne de tableau + carte mobile — DataTable engine).
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: /Onduleurs/ }))

    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)
    expect(screen.queryAllByText('Produit Sans Categorie').length).toBe(0)
  })

  it('la facette « Sans catégorie » ne montre que les produits sans catégorie', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Sans catégorie/ }))
    expect(screen.queryAllByText('Produit Sans Categorie').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBe(0)
  })

  it('« Tout le catalogue » réaffiche tout après une catégorie active', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Onduleurs/ }))
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)

    fireEvent.click(screen.getByRole('button', { name: /Tout le catalogue/ }))
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Produit Sans Categorie').length).toBeGreaterThan(0)
  })

  it('la recherche court-circuite le rail : une catégorie active n\'empêche pas un résultat d\'une AUTRE catégorie', () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Onduleurs/ }))
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)

    fireEvent.change(screen.getByPlaceholderText('Chercher partout…'), {
      target: { value: 'Panneau 550' },
    })
    // Recherche active : le résultat traverse TOUT le catalogue, la catégorie
    // « Onduleurs » sélectionnée dans le rail est court-circuitée.
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBeGreaterThan(0)
  })
})

describe('StockList — vue enregistrée : aller-retour + migration héritée (STKCAT14)', () => {
  it('sauvegarde la vue courante avec activeCatIds, puis la réapplique (aller-retour)', () => {
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('Ma vue Onduleurs')
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: /Onduleurs/ }))
    fireEvent.click(screen.getByText('⭐ Enregistrer cette vue'))
    expect(createViewMock).toHaveBeenCalledWith(expect.objectContaining({
      configuration: expect.objectContaining({ activeCatIds: [2] }),
    }))

    // Retour à « tout le catalogue », puis on réapplique la vue enregistrée
    // (simulée par le stub de ViewsManagerPopover) — le filtre doit revenir.
    fireEvent.click(screen.getByRole('button', { name: /Tout le catalogue/ }))
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('__apply_view_activeCatIds__'))
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)

    promptSpy.mockRestore()
  })

  it('migre une vue héritée `activeCat` (nom) vers l\'id à la lecture', () => {
    renderPage()
    fireEvent.click(screen.getByText('__apply_view_legacy_onduleurs__'))
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)
  })

  it('un nom de catégorie inconnu (vue héritée) est ignoré — le filtre courant ne bouge pas', () => {
    renderPage()
    fireEvent.click(screen.getByText('__apply_view_legacy_onduleurs__'))
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)

    fireEvent.click(screen.getByText('__apply_view_legacy_inconnue__'))
    // Nom introuvable dans `categories` : ignoré, la sélection « Onduleurs »
    // reste active — jamais un repli silencieux sur « tout le catalogue ».
    expect(screen.queryAllByText('Onduleur Deye 5 kW').length).toBeGreaterThan(0)
    expect(screen.queryAllByText('Panneau 550 Wc').length).toBe(0)
  })
})

/* ============================================================================
   STKCAT26 — Catalogue sur le moteur DataTable : export unique (le bouton
   d'export dupliqué de l'en-tête a disparu, `onExport` de CatalogueTable
   délègue au même endpoint xlsx serveur) + bascule groupement par catégorie.
   viewBuilder et la recherche moteur (`searchable`) ne sont PAS câblés — cf.
   CatalogueTable.jsx (raison documentée en commentaire) : incompatibles sans
   refonte plus large avec, respectivement, le format de vue de STKCAT14 et le
   court-circuit recherche/rail déjà testé plus haut. Le mode kanban n'existe
   pas dans le moteur (aucune trace de « kanban » dans DataTable.jsx).
   ========================================================================== */
describe('StockList — export unique sur le moteur DataTable (STKCAT26)', () => {
  it('le bouton d\'export dupliqué de l\'en-tête a disparu', () => {
    renderPage()
    expect(screen.queryByText('Exporter Excel')).toBeNull()
  })

  it('l\'export de CatalogueTable délègue au xlsx serveur avec les produits affichés', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Onduleurs/ }))

    fireEvent.click(screen.getByRole('button', { name: 'Exporter' }))

    await waitFor(() => expect(http.post).toHaveBeenCalledWith(
      '/stock/produits/export-xlsx/', { ids: [onduleur.id] }, { responseType: 'blob' }))
  })

  it('la bascule « Grouper par catégorie » change son propre libellé', () => {
    renderPage()
    const toggle = screen.getByRole('button', { name: /Grouper par catégorie/ })
    fireEvent.click(toggle)
    expect(screen.getByRole('button', { name: /Catégories groupées/ })).toBeInTheDocument()
  })
})

/* ============================================================================
   ASTK83 (C-ASTK-017, S1) — « Annuler » un désarchivage RÉ-ARCHIVE le produit
   (PATCH is_archived=true) ; il ne le SUPPRIME jamais (l'ancien onUndo
   appelait deleteProduit : un produit sans relation disparaissait pour de bon).
   ========================================================================== */
/* ASTK209 (C-ASTK-053, MVT-22) — l'inventaire physique ne tronque plus 7.5
   en 7 (parseInt muet) : l'erreur s'affiche sous le champ fautif et rien
   n'est envoyé tant qu'une ligne est invalide. */
describe('StockList — inventaire physique : quantités entières (ASTK209)', () => {
  const ouvrirInventaire = async () => {
    fireEvent.click(screen.getAllByRole('button', { name: /^Inventaire$/ })[0])
    return screen.findByRole('dialog')
  }

  it("7.5 affiche une erreur et n'envoie rien", async () => {
    renderPage()
    await ouvrirInventaire()
    const champ = screen.getByLabelText('Compté — Panneau 550 Wc')
    fireEvent.change(champ, { target: { value: '7.5' } })
    fireEvent.click(screen.getByRole('button', { name: "Valider l'inventaire" }))
    expect(await screen.findByText('Quantité entière ≥ 0 attendue.')).toBeInTheDocument()
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(postsInventaire()).toHaveLength(0)
  })

  it('un négatif est refusé ; une saisie entière part telle quelle', async () => {
    renderPage()
    await ouvrirInventaire()
    fireEvent.change(screen.getByLabelText('Compté — Panneau 550 Wc'), { target: { value: '-3' } })
    fireEvent.change(screen.getByLabelText('Compté — Onduleur Deye 5 kW'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: "Valider l'inventaire" }))
    expect(await screen.findByText('Quantité entière ≥ 0 attendue.')).toBeInTheDocument()
    expect(postsInventaire()).toHaveLength(0)

    fireEvent.change(screen.getByLabelText('Compté — Panneau 550 Wc'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: "Valider l'inventaire" }))
    await waitFor(() => expect(http.post).toHaveBeenCalledWith(URL_INVENTAIRE, {
      motif: '',
      lignes: [{ produit: 1, quantite_comptee: 7 }, { produit: 2, quantite_comptee: 7 }],
    }))
  })

  it('le 400 serveur par ligne est affiché sous le champ du produit', async () => {
    http.post.mockRejectedValueOnce({
      response: { status: 400, data: { error: 'x', lignes: { 0: ['Quantité entière ≥ 0 attendue.'] } } },
    })
    renderPage()
    await ouvrirInventaire()
    fireEvent.change(screen.getByLabelText('Compté — Panneau 550 Wc'), { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: "Valider l'inventaire" }))
    expect(await screen.findByText('Quantité entière ≥ 0 attendue.')).toBeInTheDocument()
    expect(screen.getByLabelText('Compté — Panneau 550 Wc')).toHaveAttribute('aria-invalid', 'true')
  })
})

describe('StockList — annuler un désarchivage (ASTK83)', () => {
  it('annuler un désarchivage ré-archive sans supprimer', async () => {
    const archive = baseProduit({ id: 7, nom: 'Ancien câble', sku: 'CAB-OLD', is_archived: true })
    vi.spyOn(window, 'confirm')
    renderPage({ produitsArchived: [archive] })
    fireEvent.click(screen.getByRole('button', { name: /Archivés/ }))
    fireEvent.click((await screen.findAllByLabelText('Désarchiver'))[0])
    // ASTK231 — l'AlertDialog commune remplace la boîte native.
    fireEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Désarchiver' }))
    expect(window.confirm).not.toHaveBeenCalled()
    await waitFor(() => expect(toastWithUndo).toHaveBeenCalled())
    const { onUndo } = toastWithUndo.mock.calls[0][0]
    await onUndo()
    // ASTK252 — vérifié à la frontière HTTP : un PATCH de ré-archivage, aucun DELETE.
    expect(http.patch).toHaveBeenCalledWith('/stock/produits/7/', { is_archived: true })
    expect(http.delete).not.toHaveBeenCalled()
    expect(deleteProduit).not.toHaveBeenCalled()
    window.confirm.mockRestore()
  })
})
