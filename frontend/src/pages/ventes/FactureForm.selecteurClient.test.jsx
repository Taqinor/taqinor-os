// ALEA33 — le sélecteur client de la facture lisait la SEULE première page de
// `/crm/clients/` (50 lignes, pagination DRF par défaut) : le client le plus
// ancien d'une société de 60 clients n'y figurait pas. Le serveur factice
// ci-dessous applique la VRAIE pagination DRF du dépôt (PAGE_SIZE 50,
// `?page_size=` plafonné à 200, `core/pagination.py`) ; le client `crmApi`
// RÉEL tourne au-dessus. L'assertion porte sur l'option affichée.
// Run : npx vitest run src/pages/ventes/FactureForm.selecteurClient.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const serveur = vi.hoisted(() => {
  // 60 clients, le plus récent d'abord (ordre de la liste serveur).
  const clients = Array.from({ length: 60 }, (_, i) => ({
    id: 60 - i,
    nom: 60 - i === 1 ? 'Zzz Client Ancien' : `Client ${60 - i}`,
  }))
  const paginer = (url, params = {}) => {
    const demande = Number(params.page_size) || 50
    const taille = Math.min(demande, 200)
    const page = Number(params.page) || 1
    const debut = (page - 1) * taille
    const results = clients.slice(debut, debut + taille)
    const suivante = debut + taille < clients.length
    return {
      count: clients.length,
      next: suivante ? `${url}?page=${page + 1}` : null,
      previous: page > 1 ? `${url}?page=${page - 1}` : null,
      results,
    }
  }
  const get = (url, config = {}) => {
    if (url === '/crm/clients/') return Promise.resolve({ data: paginer(url, config.params) })
    return Promise.reject(new Error(`URL inattendue ${url}`))
  }
  return { get }
})

vi.mock('../../api/axios', () => ({
  default: {
    get: (...a) => serveur.get(...a),
    post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))

const apis = vi.hoisted(() => ({
  ventes: {
    getBonsCommande: vi.fn(() => Promise.resolve({ data: [] })),
    getFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
  stock: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })) },
}))
vi.mock('../../api/ventesApi', () => ({ default: apis.ventes }))
vi.mock('../../api/stockApi', () => ({ default: apis.stock }))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

// La facture porte le client le PLUS ANCIEN (60e de la liste).
const FACTURE = {
  id: 77, reference: 'FAC-202610-0001', client: 1, statut: 'brouillon', taux_tva: '20.00',
  remise_globale: '0', lignes: [], updated_at: '2026-10-01T10:00:00Z',
}

const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rien = () => {}

const rendre = () => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth: AUTH } })}>
    <FactureForm facture={FACTURE} onClose={rien} onSaved={rien} />
  </Provider>,
)

beforeEach(() => { vi.clearAllMocks() })

describe('ALEA33 — FactureForm : sélecteur client complet', () => {
  it('le client le plus ancien (hors des 50 premiers) est une option du sélecteur', async () => {
    rendre()
    // La valeur affichée du sélecteur est le libellé de l'option choisie :
    // elle n'existe que si le client 1 figure parmi les options chargées.
    await waitFor(() => expect(document.getElementById('fc-client'))
      .toHaveTextContent('Zzz Client Ancien'))  })
})
