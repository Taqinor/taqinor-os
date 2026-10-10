// AFAC70 — une ligne de facture refusée par le serveur dit POURQUOI (sous la
// ligne) et LAQUELLE (message de soumission) ; la saisie reste dans le champ ;
// réessayer après correction ne crée aucun doublon.
// Réponse 400 à la forme produite par le test d'AFAC69 : {"remise": ["…"]}.
// Run : npx vitest run src/pages/ventes/FactureForm.erreursLignes.test.jsx
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const MOTIF = 'La remise doit être comprise entre 0 et 100 %'

// Faux serveur en mémoire : applique la règle d'AFAC69 (remise 0-100) et
// garde les lignes réellement enregistrées.
const { serveur, refus } = vi.hoisted(() => ({
  serveur: { lignes: new Map(), prochainId: 100 },
  refus: (remise) => {
    const r = Number(remise)
    if (r < 0 || r > 100) {
      const err = new Error('Request failed with status code 400')
      err.response = { status: 400, data: { remise: ['La remise doit être comprise entre 0 et 100 %'] } }
      return err
    }
    return null
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { count: 0, next: null, results: [] } })),
    post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksVentesEcrans.js')).stockApiVide())
vi.mock('../../api/ventesApi', () => ({
  default: {
    getBonsCommande: vi.fn().mockResolvedValue({ data: { count: 0, next: null, results: [] } }),
    getFacture: vi.fn().mockResolvedValue({ data: {} }),
    updateFacture: vi.fn((id, data) => Promise.resolve({ data: { id, ...data } })),
    createFacture: vi.fn((data) => Promise.resolve({ data: { id: 77, ...data } })),
    updateLigneFacture: vi.fn((id, data) => {
      const err = refus(data.remise)
      if (err) return Promise.reject(err)
      serveur.lignes.set(id, { id, ...data })
      return Promise.resolve({ data: { id, ...data } })
    }),
    createLigneFacture: vi.fn((data) => {
      const err = refus(data.remise)
      if (err) return Promise.reject(err)
      const id = serveur.prochainId++
      serveur.lignes.set(id, { id, ...data })
      return Promise.resolve({ data: { id, ...data } })
    }),
    deleteLigneFacture: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

const ligne = (n, extra = {}) => ({
  produit: 3, designation: `Ligne ${n}`, quantite: '1', prix_unitaire: '100',
  remise: '0', taux_tva: '20.00', ...extra,
})
const facture = (lignes) => ({
  id: 77, reference: 'FAC-202610-0070', client: 1, statut: 'brouillon', taux_tva: '20.00',
  remise_globale: '0', updated_at: '2026-10-01T10:00:00Z',
  montant_ht: '300.00', montant_tva: '60.00', montant_ttc: '360.00', lignes,
})
const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rendre = (f) => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth: AUTH } })}>
    <FactureForm facture={f} onClose={() => {}} onSaved={() => {}} />
  </Provider>,
)

const lignesDom = () => [...document.querySelectorAll('tr[data-line-key]')]
const champRemise = (i) => lignesDom()[i].querySelector('td[data-label="Rem. %"] input')
// Le motif est rendu DANS la ligne, sous ses champs (role="alert").
const erreurSous = (i) => lignesDom()[i].querySelector('[data-line-error][role="alert"]')?.textContent ?? null
const enregistrer = () => fireEvent.click(screen.getByRole('button', { name: /Mettre à jour/ }))

beforeEach(() => {
  serveur.lignes.clear()
  serveur.prochainId = 100
})

describe('AFAC70 — FactureForm : motif serveur sous la ligne refusée', () => {
  it('remise 150 sur la ligne 2 : motif sous la ligne 2, ligne nommée, lignes 1 et 3 enregistrées', async () => {
    rendre(facture([ligne(1, { id: 1 }), ligne(2, { id: 2 }), ligne(3, { id: 3 })]))
    fireEvent.change(champRemise(1), { target: { value: '150' } })
    enregistrer()

    await waitFor(() => expect(erreurSous(1)).toBe(MOTIF))
    expect(erreurSous(0)).toBeNull()
    expect(erreurSous(2)).toBeNull()
    expect(screen.getByText(/Facture enregistrée, mais la ligne 2 n'a pas pu être enregistrée : /))
      .toHaveTextContent(MOTIF)
    // La saisie reste dans le champ (jamais corrigée en silence).
    expect(champRemise(1).value).toBe('150')
    expect([...serveur.lignes.keys()].sort()).toEqual([1, 3])
  })

  it('nouvelles lignes : 1 et 3 créées, 2 absente ; après correction, réessayer ne crée aucun doublon', async () => {
    const ventesApi = (await import('../../api/ventesApi')).default
    ventesApi.createLigneFacture.mockClear()
    rendre(facture([ligne(1), ligne(2), ligne(3)]))
    fireEvent.change(champRemise(1), { target: { value: '150' } })
    enregistrer()

    await waitFor(() => expect(erreurSous(1)).toBe(MOTIF))
    expect(serveur.lignes.size).toBe(2)
    expect([...serveur.lignes.values()].map(l => l.designation).sort()).toEqual(['Ligne 1', 'Ligne 3'])

    fireEvent.change(champRemise(1), { target: { value: '15' } })
    expect(erreurSous(1)).toBeNull()
    enregistrer()

    await waitFor(() => expect(serveur.lignes.size).toBe(3))
    expect(ventesApi.createLigneFacture).toHaveBeenCalledTimes(4) // 3 puis seule la ligne 2
    expect([...serveur.lignes.values()].map(l => l.designation).sort())
      .toEqual(['Ligne 1', 'Ligne 2', 'Ligne 3'])
  })
})
