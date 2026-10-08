import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import authReducer from '../../features/auth/store/authSlice'

/* ============================================================================
   ASTK68 (C-ASTK-016) — l'enregistrement d'un BCF brouillon envoie l'`id` de
   chaque ligne EXISTANTE (le serveur met à jour par identifiant, ASTK67 :
   frais annexes et champs non transmis conservés) ; une ligne ajoutée à
   l'écran part SANS id. Même payload avant l'envoi au fournisseur.
   Composant réel ; seule l'API est simulée (frontière réseau).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    updateBonCommandeFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    createBonCommandeFournisseur: vi.fn(() => Promise.resolve({ data: { id: 99 } })),
    envoyerBcf: vi.fn(() => Promise.resolve({ data: {} })),
    getBcfSimilaires: vi.fn(() => Promise.resolve({ data: [] })),
    prixEffectifFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    getCategories: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}))

vi.mock('../../api/coreApi', () => ({
  default: { utilisateurs: { list: vi.fn().mockResolvedValue({ data: [] }) } },
}))

import stockApi from '../../api/stockApi'
import { BcfDetail } from './BonsCommandeFournisseur.jsx'

const DIRECTEUR = {
  role: 'admin', role_nom: 'Directeur',
  permissions: ['stock_voir', 'prix_achat_voir', 'achats_commander'],
}

const BCF = {
  id: 42, reference: 'BCF-2026-10-0042', statut: 'brouillon', fournisseur: 3,
  fournisseur_nom: 'JA Solar', note: '',
  lignes: [
    { id: 9, produit: 5, produit_nom: 'Onduleur 5 kW', designation: '', quantite: 4,
      quantite_recue: 0, prix_achat_unitaire: '1000.00', frais_annexes: '150.00' },
    { id: 10, produit: null, produit_nom: null, designation: 'Transport Casablanca', quantite: 1,
      quantite_recue: 0, prix_achat_unitaire: '300.00', sans_stock: true },
  ],
}

function renderDetail() {
  const store = configureStore({
    reducer: { auth: authReducer },
    preloadedState: { auth: { user: { id: 1 }, ...DIRECTEUR, isAuthenticated: true, loading: false } },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>
          <BcfDetail bcf={BCF} fournisseurs={[{ id: 3, nom: 'JA Solar' }]}
                     produits={[{ id: 5, nom: 'Onduleur 5 kW' }]} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
})

describe('ASTK68 — ids des lignes dans le payload du BCF', () => {
  it('« Enregistrer » envoie l\'id de chaque ligne existante, aucune pour une ligne neuve', async () => {
    renderDetail()
    fireEvent.click(await screen.findByRole('button', { name: /Ligne libre|Ajouter une ligne libre/ }))
    const designations = screen.getAllByPlaceholderText(/Désignation libre/)
    fireEvent.change(designations[designations.length - 1], { target: { value: 'Grue' } })
    fireEvent.click(screen.getByRole('button', { name: /^Enregistrer$/ }))
    await waitFor(() => expect(stockApi.updateBonCommandeFournisseur).toHaveBeenCalled())
    const [id, payload] = stockApi.updateBonCommandeFournisseur.mock.calls[0]
    expect(id).toBe(42)
    expect(payload.lignes.map((l) => l.id)).toEqual([9, 10, undefined])
    expect(payload.lignes[2]).not.toHaveProperty('id')
    expect(payload.lignes[2].designation).toBe('Grue')
  })

  it('« Envoyer au fournisseur » enregistre d\'abord avec les mêmes ids', async () => {
    renderDetail()
    fireEvent.click(await screen.findByRole('button', { name: /Envoyer au fournisseur/ }))
    await waitFor(() => expect(stockApi.envoyerBcf).toHaveBeenCalledWith(42))
    const payload = stockApi.updateBonCommandeFournisseur.mock.calls[0][1]
    expect(payload.lignes.map((l) => l.id)).toEqual([9, 10])
  })
})
