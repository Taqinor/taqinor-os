import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ASTK33 (C-ASTK-005, S1) — `quantite_stock` n'est JAMAIS réécrit par une
   édition de fiche : une réception arrivée entre l'ouverture et
   l'enregistrement de la fiche (stock 10 → 15) serait sinon écrasée à 10.
     - le PATCH d'édition de la fiche ne porte pas `quantite_stock`
       (la création, elle, l'envoie toujours) ;
     - la cellule « Stock » du catalogue ne PATCHe plus le produit : elle
       pose un comptage d'inventaire (mouvement d'ajustement tracé).
   Composants réels ; seule l'API est simulée (frontière réseau).
   ========================================================================== */

// ASTK252 — frontière réseau RÉELLE : stockApi est le module réel
// (vi.importActual) et seul `../../api/axios` est simulé ; les écritures sont
// observées par méthode HTTP + URL (une erreur de câblage stockApi ne passe plus).
const http = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
}))
vi.mock('../../api/axios', () => ({ default: http }))
vi.mock('../../api/stockApi', () => vi.importActual('../../api/stockApi'))
const appel = (methode, url) => http[methode].mock.calls.find(([u]) => u === url)

// ASTK251 — StockList réel : ses dépendances hors sujet (pilotage, vues
// serveur) sont neutralisées, même patron que StockList.test.jsx.
vi.mock('./PilotageStock', () => ({ default: () => null }))
vi.mock('../../features/uxviews/useServerSavedViews', () => ({
  useServerSavedViews: () => ({ createView: vi.fn() }),
}))
vi.mock('../../features/uxviews/ViewsManagerPopover', () => ({ default: () => null }))

import ProduitForm from './ProduitForm.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'
import StockList from './StockList.jsx'
import { installerCalesJsdom } from '../../test/fixtures/calesJsdom'

const magasin = configureStore({ reducer: {
  auth: () => ({ role: 'admin', role_nom: 'Directeur', permissions: [] }),
  stock: () => ({ categories: [], fournisseurs: [], produits: [] }),
} })
const enveloppe = ({ children }) => (
  <Provider store={magasin}><MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter></Provider>
)

const PRODUIT = {
  id: 9, nom: 'Onduleur 5 kW', sku: 'OND-5', marque: '', description: '',
  prix_vente: '3200', prix_achat: '1800', tva: 20, quantite_stock: 10,
  seuil_alerte: 1, categorie: null, fournisseur: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  http.get.mockResolvedValue({ data: [] })
  http.post.mockImplementation(async (url, data) => ({ data: { id: 42, ...data } }))
  http.patch.mockImplementation(async (url, data) => ({ data: { id: 9, ...data } }))
  installerCalesJsdom()
})

describe('ASTK33 — fiche produit : le stock ne part jamais dans le PATCH', () => {
  it('édition : le payload ne contient pas quantite_stock', async () => {
    render(<ProduitForm produit={PRODUIT} onClose={() => {}} onSaved={() => {}} />, { wrapper: enveloppe })
    await screen.findByText(/Éditer/)
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(appel('patch', '/stock/produits/9/')).toBeTruthy())
    const [, payload] = appel('patch', '/stock/produits/9/')
    expect(payload).not.toHaveProperty('quantite_stock')
    expect(payload.nom).toBe('Onduleur 5 kW')
  })

  it('création : le stock initial est toujours envoyé', async () => {
    render(<ProduitForm produit={null} onClose={() => {}} onSaved={() => {}} />, { wrapper: enveloppe })
    await screen.findByText('Nouveau produit')
    fireEvent.change(screen.getByPlaceholderText('Nom du produit'), { target: { value: 'Câble 6 mm²' } })
    fireEvent.change(document.getElementById('pf-vente'), { target: { value: '12' } })
    fireEvent.change(document.getElementById('pf-qte'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le produit' }))
    await waitFor(() => expect(appel('post', '/stock/produits/')).toBeTruthy())
    expect(appel('post', '/stock/produits/')[1].quantite_stock).toBe(7)
  })
})

describe('ASTK33 — cellule « Stock » du catalogue : ajustement d\'inventaire', () => {
  const produit = {
    id: 1, nom: 'Panneau 550 Wc', sku: 'PAN-550', prix_vente: '1000.00', tva: '20',
    quantite_stock: 15, seuil_alerte: 2, unite: 'piece', is_archived: false,
    categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
  }
  const table = (props) => render(
    <MemoryRouter>
      <ThemeProvider>
        <CatalogueTable produits={[produit]} categories={[{ id: 3, nom: 'Panneaux' }]} loading={false}
                        canWrite onEdit={() => {}} onDelete={() => {}} onHistorique={() => {}} {...props} />
      </ThemeProvider>
    </MemoryRouter>,
  )

  it('taper 12 appelle l\'ajustement d\'inventaire, jamais un PATCH quantite_stock', async () => {
    const onInlineSave = vi.fn().mockResolvedValue({})
    const onAjusterStock = vi.fn().mockResolvedValue({})
    table({ onInlineSave, onAjusterStock })
    const cellule = screen.getAllByTitle('Double-cliquez pour modifier')
      .find((b) => b.textContent.includes('15'))
    fireEvent.doubleClick(cellule)
    const input = document.querySelector('input')
    fireEvent.change(input, { target: { value: '12' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(onAjusterStock).toHaveBeenCalledTimes(1))
    const [prod, valeur] = onAjusterStock.mock.calls[0]
    expect(prod.id).toBe(1)
    expect(String(valeur)).toBe('12')
    expect(onInlineSave.mock.calls.some(([, champ]) => champ === 'quantite_stock')).toBe(false)
  })
})

/* ASTK251 (C-ASTK-VER-005) — `POST /stock/produits/inventaire/` est réservé à
   l'administrateur (IsAdminRole) : la cellule Stock suit le droit du bouton
   « Inventaire » (`canDelete`), jamais `canWrite` (un responsable recevait 403). */
describe('ASTK251 — cellule « Stock » de StockList : éditable seulement par l\'administrateur', () => {
  const produitListe = {
    id: 1, nom: 'Panneau 550 Wc', sku: 'PAN-550', prix_vente: '1000.00', tva: '20',
    quantite_stock: 15, quantite_reservee: 0, quantite_disponible: 15, seuil_alerte: 2,
    unite: 'piece', is_archived: false, categorie: { id: 3, nom: 'Panneaux', ordre: 1 },
  }
  const rendreListe = (auth) => render(
    <Provider store={configureStore({ reducer: {
      auth: () => auth,
      stock: () => ({ produits: [produitListe], produitsArchived: [], fournisseurs: [],
        categories: [{ id: 3, nom: 'Panneaux', ordre: 1 }], loading: false, error: null }),
    } })}>
      <MemoryRouter><ThemeProvider><StockList /></ThemeProvider></MemoryRouter>
    </Provider>,
  )
  const cellulesStockEditables = () => document.querySelectorAll(
    '.pcat-stock-val [title="Double-cliquez pour modifier"]')

  it('responsable non administrateur : la cellule Stock n\'est pas éditable', async () => {
    rendreListe({ role: 'responsable', role_nom: 'Technicien responsable',
      permissions: ['stock_voir', 'stock_modifier'] })
    expect((await screen.findAllByText('Panneau 550 Wc')).length).toBeGreaterThan(0)
    expect(cellulesStockEditables()).toHaveLength(0)
    expect(screen.queryByRole('button', { name: /^Inventaire$/ })).toBeNull()
  })

  it('administrateur : la cellule Stock est éditable, comme le bouton « Inventaire »', async () => {
    rendreListe({ role: 'admin', role_nom: 'Directeur', permissions: [] })
    expect((await screen.findAllByText('Panneau 550 Wc')).length).toBeGreaterThan(0)
    expect(cellulesStockEditables().length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /^Inventaire$/ }).length).toBeGreaterThan(0)
  })

  it('ASTK252 — taper 12 dans la cellule pose un POST /stock/produits/inventaire/ (câblage réel)', async () => {
    rendreListe({ role: 'admin', role_nom: 'Directeur', permissions: [] })
    await screen.findAllByText('Panneau 550 Wc')
    fireEvent.doubleClick(cellulesStockEditables()[0])
    const input = document.querySelector('.pcat-stock-val input')
    fireEvent.change(input, { target: { value: '12' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => expect(http.post).toHaveBeenCalledWith('/stock/produits/inventaire/', {
      motif: 'Correction depuis le catalogue', lignes: [{ produit: 1, quantite_comptee: 12 }],
    }))
    expect(http.patch).not.toHaveBeenCalled()
  })
})
