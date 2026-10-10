// AFAC71 — FactureForm : une facture hors BROUILLON s'ouvre en lecture seule pour
// l'argent et les lignes ; enregistrer ne peut plus réécrire un statut ni un montant.
// Test COMPORTEMENTAL : faux serveur en mémoire qui applique le corps reçu à la
// facture, puis relecture (aucune assertion sur les arguments d'appel).
// Run : npx vitest run src/pages/ventes/FactureForm.horsBrouillon.test.jsx
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const { base } = vi.hoisted(() => ({ base: { facture: null, lignes: new Map() } }))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: { count: 0, next: null, results: [] } }),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))
vi.mock('../../api/stockApi', async () => {
  const mocks = await import('../../test/mocksVentesEcrans.js')
  return mocks.stockApiVide()
})
vi.mock('../../api/ventesApi', () => ({
  default: {
    getBonsCommande: vi.fn().mockResolvedValue({ data: { count: 0, next: null, results: [] } }),
    getFacture: vi.fn(() => Promise.resolve({ data: base.facture })),
    // Le serveur applique tel quel le corps reçu : tout champ envoyé est réécrit.
    updateFacture: vi.fn((id, data) => {
      Object.assign(base.facture, data)
      return Promise.resolve({ data: { ...base.facture } })
    }),
    createFacture: vi.fn((data) => Promise.resolve({ data: { id: 78, ...data } })),
    updateLigneFacture: vi.fn((id, data) => {
      base.lignes.set(id, { id, ...data })
      return Promise.resolve({ data: { id, ...data } })
    }),
    createLigneFacture: vi.fn((data) => Promise.resolve({ data: { id: 900, ...data } })),
    deleteLigneFacture: vi.fn((id) => { base.lignes.delete(id); return Promise.resolve({ data: {} }) }),
  },
}))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

const LIGNE = {
  id: 1, produit: 3, designation: 'Panneau 550 Wc', quantite: '10', prix_unitaire: '1000',
  remise: '0', taux_tva: '20.00',
}
const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rendre = (f) => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth: AUTH } })}>
    <FactureForm facture={f} onClose={() => {}} onSaved={() => {}} />
  </Provider>,
)
const enregistrer = () => fireEvent.click(screen.getByRole('button', { name: /Mettre à jour/ }))
const cellule = (libelle) => document.querySelector(`td[data-label="${libelle}"] input`)

beforeEach(() => {
  base.lignes = new Map([[1, { ...LIGNE }]])
  base.facture = {
    id: 77, reference: 'FAC-202610-0077', client: 1, statut: 'emise', taux_tva: '20.00',
    remise_globale: '0', statut_teledeclaration: 'non_soumise', note: '',
    updated_at: '2026-10-01T10:00:00Z', montant_ht: '10000.00', montant_tva: '2000.00',
    montant_ttc: '12000.00', montant_du: '12000.00', lignes: [{ ...LIGNE }],
  }
})

describe('AFAC71 — FactureForm hors brouillon', () => {
  it('facture émise soldée dans un autre onglet : « Mettre à jour » garde statut payee, montants et lignes', async () => {
    const ouverte = { ...base.facture, lignes: [{ ...LIGNE }] } // vue du Kanban : statut emise
    // Entre-temps, autre onglet : facture soldée côté serveur.
    base.facture.statut = 'payee'
    base.facture.montant_du = '0.00'
    rendre(ouverte)

    expect(screen.queryByLabelText('Statut')).toBeNull()
    expect(screen.queryByLabelText(/Télédéclaration DGI/)).toBeNull()
    for (const champ of ['Qté', 'Prix HT (DH)', 'Rem. %', 'TVA %']) {
      expect(cellule(champ).disabled).toBe(true)
    }
    expect(document.getElementById('fc-tva').disabled).toBe(true)
    expect(document.getElementById('fc-remise').disabled).toBe(true)

    fireEvent.change(document.getElementById('fc-note'), { target: { value: 'relance faite' } })
    enregistrer()
    await waitFor(() => expect(base.facture.note).toBe('relance faite'))

    // Relecture serveur.
    expect(base.facture.statut).toBe('payee')
    expect(base.facture.montant_du).toBe('0.00')
    expect(base.facture.taux_tva).toBe('20.00')
    expect(base.facture.montant_ttc).toBe('12000.00')
    expect(base.lignes.get(1)).toEqual(LIGNE)
  })

  it('brouillon : formulaire complet sans Statut/DGI, aucun statut envoyé', async () => {
    base.facture.statut = 'brouillon'
    rendre({ ...base.facture, lignes: [{ ...LIGNE }] })
    expect(screen.queryByLabelText('Statut')).toBeNull()
    expect(screen.queryByLabelText(/Télédéclaration DGI/)).toBeNull()
    expect(document.getElementById('fc-tva').disabled).toBe(false)

    base.facture.statut = 'emise' // le serveur a émis entre-temps : l'écran ne doit pas le repasser
    fireEvent.change(document.getElementById('fc-remise'), { target: { value: '5' } })
    enregistrer()
    await waitFor(() => expect(base.facture.remise_globale).toBe('5'))
    expect(base.facture.statut).toBe('emise')
    expect(base.facture.statut_teledeclaration).toBe('non_soumise')
  })
})
