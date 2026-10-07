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

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn() },
}))

const { createProduitApi, updateProduitApi } = vi.hoisted(() => ({
  createProduitApi: vi.fn((data) => Promise.resolve({ data: { id: 42, ...data } })),
  updateProduitApi: vi.fn((id, data) => Promise.resolve({ data: { id, ...data } })),
}))

vi.mock('../../api/stockApi', () => ({
  default: {
    getProduitPrixFournisseurs: () => Promise.resolve({ data: [] }),
    comparerFournisseurs: () => Promise.resolve({ data: [] }),
    comparerTcoFournisseurs: () => Promise.resolve({ data: { fournisseurs: [] } }),
    uploadProduitImage: () => Promise.resolve({ data: {} }),
    getFichesTechniques: () => Promise.resolve({ data: [] }),
    createProduit: (...args) => createProduitApi(...args),
    updateProduit: (...args) => updateProduitApi(...args),
  },
}))

import ProduitForm from './ProduitForm.jsx'
import { CatalogueTable } from './CatalogueTable.jsx'

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    stock: (s = { categories: [], fournisseurs: [], produits: [] }) => s,
  },
})

function wrapper({ children }) {
  return (
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}

const PRODUIT = {
  id: 9, nom: 'Onduleur 5 kW', sku: 'OND-5', marque: '', description: '',
  prix_vente: '3200', prix_achat: '1800', tva: 20, quantite_stock: 10,
  seuil_alerte: 1, categorie: null, fournisseur: null,
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
})

describe('ASTK33 — fiche produit : le stock ne part jamais dans le PATCH', () => {
  it('édition : le payload ne contient pas quantite_stock', async () => {
    render(<ProduitForm produit={PRODUIT} onClose={() => {}} onSaved={() => {}} />, { wrapper })
    await screen.findByText(/Éditer/)
    fireEvent.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(updateProduitApi).toHaveBeenCalled())
    const [, payload] = updateProduitApi.mock.calls[0]
    expect(payload).not.toHaveProperty('quantite_stock')
    expect(payload.nom).toBe('Onduleur 5 kW')
  })

  it('création : le stock initial est toujours envoyé', async () => {
    render(<ProduitForm produit={null} onClose={() => {}} onSaved={() => {}} />, { wrapper })
    await screen.findByText('Nouveau produit')
    fireEvent.change(screen.getByPlaceholderText('Nom du produit'), { target: { value: 'Câble 6 mm²' } })
    fireEvent.change(document.getElementById('pf-vente'), { target: { value: '12' } })
    fireEvent.change(document.getElementById('pf-qte'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le produit' }))
    await waitFor(() => expect(createProduitApi).toHaveBeenCalled())
    expect(createProduitApi.mock.calls[0][0].quantite_stock).toBe(7)
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
