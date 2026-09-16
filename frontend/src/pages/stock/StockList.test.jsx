import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
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

vi.mock('../../api/stockApi', () => ({
  default: {
    getMarques: vi.fn(() => Promise.resolve({ data: [] })),
    getEmplacements: vi.fn(() => Promise.resolve({ data: [] })),
    getFichesTechniques: vi.fn(() => Promise.resolve({ data: [] })),
    inventaire: vi.fn(() => Promise.resolve({ data: {} })),
    valorisation: vi.fn(() => Promise.resolve({ data: {} })),
    getRapportPertes: vi.fn(() => Promise.resolve({ data: [] })),
    bulkProduits: vi.fn(() => Promise.resolve({ data: {} })),
    exportProduitsXlsx: vi.fn(() => Promise.resolve({ data: new Blob(['x']) })),
    etiquettesProduits: vi.fn(() => Promise.resolve({ data: new Blob(['x']) })),
    etiquettesKanbanEmplacement: vi.fn(() => Promise.resolve({ data: new Blob(['x']) })),
    etiquettesShowroom: vi.fn(() => Promise.resolve({ data: new Blob(['x']) })),
    resolveCode: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchProduits: () => ({ type: 'stock/fetchProduits/noop' }),
  fetchProduitsArchived: () => ({ type: 'stock/fetchProduitsArchived/noop' }),
  fetchCategories: () => ({ type: 'stock/fetchCategories/noop' }),
  updateProduit: () => ({ type: 'stock/updateProduit/noop' }),
  deleteProduit: () => ({ type: 'stock/deleteProduit/noop' }),
  unarchiveProduit: () => ({ type: 'stock/unarchiveProduit/noop' }),
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

import stockApi from '../../api/stockApi'
import { createViewMock } from '../../features/uxviews/useServerSavedViews'
import StockList from './StockList.jsx'

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
} = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, role_nom: role, permissions }) => s,
      stock: (s = {
        produits, produitsArchived: [], categories, loading: false, error: null,
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
  stockApi.getMarques.mockResolvedValue({ data: [] })
  stockApi.getEmplacements.mockResolvedValue({ data: [] })
  stockApi.getFichesTechniques.mockResolvedValue({ data: [] })
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
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
