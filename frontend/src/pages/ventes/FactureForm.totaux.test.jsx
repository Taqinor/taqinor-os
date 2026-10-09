// AFAC68 — FactureForm affiche les totaux SERVEUR tant que la facture n'est pas
// modifiée, puis une ESTIMATION dont le TTC = HT affiché + TVA affichée.
// Run : npx vitest run src/pages/ventes/FactureForm.totaux.test.jsx
import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { count: 0, next: null, results: [] } })),
    post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))
const apis = vi.hoisted(() => ({
  ventes: {
    getBonsCommande: vi.fn(() => Promise.resolve({ data: { count: 0, next: null, results: [] } })),
    getFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
  stock: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })) },
}))
vi.mock('../../api/ventesApi', () => ({ default: apis.ventes }))
vi.mock('../../api/stockApi', () => ({ default: apis.stock }))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

// Forme réelle FactureSerializer : 1,33 × 10,01 à 20 % ⇒ serveur HT 13,31 / TVA 2,66 / TTC 15,97.
const FACTURE = {
  id: 77, reference: 'FAC-202610-0001', client: 1, statut: 'brouillon', taux_tva: '20.00',
  remise_globale: '0', updated_at: '2026-10-01T10:00:00Z',
  montant_ht: '13.31', montant_tva: '2.66', montant_ttc: '15.97',
  lignes: [{
    id: 1, produit: 3, designation: 'Câble', quantite: '1.33', prix_unitaire: '10.01',
    remise: '0', taux_tva: '20.00',
  }],
}
const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rendre = () => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth: AUTH } })}>
    <FactureForm facture={FACTURE} onClose={() => {}} onSaved={() => {}} />
  </Provider>,
)

const bloc = () => document.querySelector('.ml-auto.max-w-xs')
const ligneTotal = (libelle) => {
  const el = within(bloc()).getByText(libelle)
  return within(el.parentElement).getByText(/DH/).textContent
}

describe('AFAC68 — FactureForm : totaux serveur puis estimation', () => {
  it('à l\'ouverture : Total TTC = valeur du serveur (15,97), pas de bandeau Estimation', () => {
    rendre()
    expect(ligneTotal('Total TTC')).toMatch(/15,97/)
    expect(screen.queryByTestId('totaux-estimation')).toBeNull()
  })

  it('après modification : « Estimation », TTC = HT affiché + TVA affichée', () => {
    rendre()
    const qte = document.querySelector('[data-role="line-qty"]')
    fireEvent.change(qte, { target: { value: '3' } })
    expect(screen.getByTestId('totaux-estimation'))
      .toHaveTextContent('Estimation — le total définitif est calculé à l\'enregistrement')
    const ht = ligneTotal('Total HT')
    const tva = ligneTotal(/^TVA/)
    const ttc = ligneTotal('Total TTC (estimation)')
    const n = (t) => Number(t.replace(/[^\d,]/g, '').replace(',', '.'))
    expect(n(ttc)).toBeCloseTo(n(ht) + n(tva), 2)
    expect(ttc).not.toMatch(/15,98/)
  })
})
