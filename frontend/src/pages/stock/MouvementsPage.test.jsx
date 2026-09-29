import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ZSTK7 — « Vue groupée / pivot » sur les mouvements de stock : bascule vers
   un tableau agrégé (entrées/sorties/net) par produit/type/mois/emplacement
   (mouvements/agregation/), avec son propre export Excel.
   ========================================================================== */

// Environnement local (pas de @sentry/react dans node_modules de cet hôte) :
// évite que le transform de test échoue sur l'import dynamique optionnel de
// ui/ErrorBoundary.jsx (barrel '../../ui' → lib/monitoring.js). N'affecte
// aucun comportement testé ici (aucun test ne déclenche le monitoring).
vi.mock('../../lib/monitoring', () => ({
  captureException: () => {},
  initMonitoring: () => {},
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getTransferts: vi.fn(),
    mouvementsAgregation: vi.fn(),
    mouvementsAgregationXlsx: vi.fn(),
    exportMouvementsXlsx: vi.fn(),
  },
}))

vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchMouvements: () => ({ type: 'stock/fetchMouvements/noop' }),
  fetchProduits: () => ({ type: 'stock/fetchProduits/noop' }),
  // ERR-QAH-STOCK-MOUVEMENT-QUANTITE-DECIMALE-TRONQUEE — vi.fn() (pas une
  // simple flèche) pour pouvoir affirmer qu'une quantité invalide n'est
  // JAMAIS envoyée au serveur (le formulaire doit refuser avant dispatch).
  createMouvement: vi.fn((payload) => ({ type: 'stock/createMouvement/noop', payload })),
}))

import stockApi from '../../api/stockApi'
import { createMouvement } from '../../features/stock/store/stockSlice'
import MouvementsPage from './MouvementsPage.jsx'

function store({ role = 'admin', mouvements = [], produits = [] } = {}) {
  return configureStore({
    reducer: {
      auth: (s = { role, permissions: [] }) => s,
      stock: (s = { mouvements, produits, loading: false, error: null }) => s,
    },
  })
}

function renderPage(opts) {
  return render(
    <Provider store={store(opts)}>
      <MemoryRouter>
        <ThemeProvider><MouvementsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  URL.revokeObjectURL = vi.fn()
})

describe('ZSTK7 — bascule Vue liste / Vue groupée', () => {
  it('la vue liste est affichée par défaut', () => {
    renderPage({ mouvements: [{ id: 1, produit: 1, produit_nom: 'Panneau', type_mouvement: 'entree', date: '2026-07-01T10:00:00Z', quantite_avant: 0, quantite_apres: 5 }] })
    expect(screen.getByRole('button', { name: /Vue groupée/ })).toBeInTheDocument()
    expect(screen.queryByText('Groupe')).toBeNull()
  })

  it('bascule vers la vue groupée et affiche les colonnes agrégées', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({
      data: [{ libelle: 'Panneau 550', entrees: 20, sorties: 5, net: 15 }],
    })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'produit' }))
    expect((await screen.findAllByText('Panneau 550'))[0]).toBeInTheDocument()
    expect(screen.getAllByText('+20')[0]).toBeInTheDocument()
    expect(screen.getAllByText('-5')[0]).toBeInTheDocument()
    // Le bouton bascule en « Vue liste » une fois actif.
    expect(screen.getByRole('button', { name: /Vue liste/ })).toBeInTheDocument()
  })

  it('changer le regroupement recharge l\'agrégation avec le nouveau group_by', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({ data: [] })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'produit' }))
    await userEvent.click(screen.getByRole('combobox'))
    fireEvent.click(await screen.findByText('Par type'))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalledWith({ group_by: 'type' }))
  })

  it('exporte l\'agrégation en Excel', async () => {
    stockApi.mouvementsAgregation.mockResolvedValue({ data: [] })
    stockApi.mouvementsAgregationXlsx.mockResolvedValue({ data: new Blob(['x']) })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /Vue groupée/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregation).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: /Exporter Excel/ }))
    await waitFor(() => expect(stockApi.mouvementsAgregationXlsx).toHaveBeenCalledWith({ group_by: 'produit' }))
    clickSpy.mockRestore()
  })
})

/* ============================================================================
   ERR-QAH-STOCK-MOUVEMENT-QUANTITE-DECIMALE-TRONQUEE — une quantité décimale
   (7.5) saisie dans « Saisir un mouvement de stock » ne doit JAMAIS être
   tronquée en silence à 7 : ni dans l'aperçu « Après : … », ni dans le corps
   envoyé au serveur. `MouvementStock.quantite` est un `IntegerField` côté
   modèle (aucune migration dans le périmètre de cette lane) — le formulaire
   doit donc REFUSER la saisie fractionnaire avec un message nommant le champ
   et la raison, jamais l'arrondir/tronquer sans le dire.
   ========================================================================== */

describe('ERR-QAH-STOCK-MOUVEMENT-QUANTITE-DECIMALE-TRONQUEE — quantité décimale', () => {
  async function ouvrirFormulaireEtChoisirProduit() {
    renderPage({ produits: [{ id: 1, nom: 'Panneau', quantite_stock: 10 }] })
    await userEvent.click(screen.getByRole('button', { name: /Saisir mouvement/ }))
    const combos = screen.getAllByRole('combobox')
    await userEvent.click(combos[0])
    await userEvent.click(await screen.findByRole('option', { name: /Panneau — stock : 10/ }))
    return screen.getByLabelText(/Quantité/)
  }

  it("n'affiche jamais un aperçu tronqué (7.5 → 17) : l'aperçu disparaît tant que la quantité n'est pas un entier", async () => {
    const qteInput = await ouvrirFormulaireEtChoisirProduit()
    fireEvent.change(qteInput, { target: { value: '7.5' } })

    // OBSERVÉ (bug) : l'aperçu affichait « Après : 17 » (7.5 tronqué en
    // silence par parseInt). ATTENDU : aucun aperçu tant que 7.5 n'est pas
    // un nombre entier valide.
    expect(screen.queryByText('17')).not.toBeInTheDocument()
    expect(screen.queryByText(/Après\s*:/)).not.toBeInTheDocument()
  })

  it("refuse la soumission d'une quantité décimale (7.5) au lieu de l'envoyer tronquée à 7", async () => {
    const qteInput = await ouvrirFormulaireEtChoisirProduit()
    fireEvent.change(qteInput, { target: { value: '7.5' } })
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer le mouvement/ }))

    // OBSERVÉ (bug) : POST .../mouvements/ avec "quantite":7, 201.
    // ATTENDU : aucun envoi, un message nommant le champ + la raison.
    expect(createMouvement).not.toHaveBeenCalled()
    expect(screen.getByText(/entier|fractionnable/i)).toBeInTheDocument()
  })

  it('accepte toujours une quantité entière (7) et l\'envoie telle quelle', async () => {
    const qteInput = await ouvrirFormulaireEtChoisirProduit()
    fireEvent.change(qteInput, { target: { value: '7' } })
    expect(await screen.findByText('17')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Enregistrer le mouvement/ }))
    await waitFor(() => expect(createMouvement).toHaveBeenCalledWith(
      expect.objectContaining({ quantite: 7 }),
    ))
  })
})
