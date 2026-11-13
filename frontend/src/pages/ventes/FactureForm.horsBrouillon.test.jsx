// AFAC71 — FactureForm : une facture hors BROUILLON s'ouvre en lecture seule pour
// l'argent et les lignes ; enregistrer ne peut plus réécrire un statut ni un montant.
// Test COMPORTEMENTAL : faux serveur en mémoire qui applique le corps reçu à la
// facture, puis relecture (aucune assertion sur les arguments d'appel).
// Run : npx vitest run src/pages/ventes/FactureForm.horsBrouillon.test.jsx
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

beforeAll(polyfillResizeObserver)

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
    // Comme le vrai PUT, une mise à jour COMPLÈTE sans client est refusée (400).
    updateFacture: vi.fn((id, data) => {
      if (!data.client) {
        return Promise.reject({ response: { status: 400, data: { client: ['Ce champ est obligatoire.'] } } })
      }
      Object.assign(base.facture, data)
      return Promise.resolve({ data: { ...base.facture } })
    }),
    // PATCH : mise à jour partielle (facture hors brouillon, AFAC71).
    patchFacture: vi.fn((id, data) => {
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
import { polyfillResizeObserver } from '../../test/selectNatif'

const LIGNE = {
  id: 1, produit: 3, designation: 'Panneau 550 Wc', quantite: '10', prix_unitaire: '1000',
  remise: '0', taux_tva: '20.00',
}
const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rendre = (f, auth = AUTH) => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth } })}>
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
  it('rejeu AARG50 : les pièces jointes visent la cible servie (facturation.facture), jamais un 400', async () => {
    rendre({ ...base.facture, lignes: [{ ...LIGNE }] })
    const { default: api } = await import('../../api/axios')
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/records/attachments/',
      expect.objectContaining({ params: expect.objectContaining({ model: 'facturation.facture' }) })))
  })

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

  it('400 date_echeance : message sous Date d\'échéance', async () => {
    // AERR6 (C-AERR-006) — mutant : remettre `setFromResponse(err)` ⇒ échec.
    const { default: ventesApi } = await import('../../api/ventesApi')
    const axiosErr = Object.assign(new Error('Request failed with status code 400'), {
      isAxiosError: true, name: 'AxiosError', code: 'ERR_BAD_REQUEST',
      response: { status: 400, data: { date_echeance: ['Période verrouillée.'], champ_inconnu: ['Refusé.'] } },
    })
    ventesApi.patchFacture.mockImplementationOnce(() => Promise.reject(axiosErr))
    // ADRG108 — l'échéance d'une émise n'est saisissable qu'avec `encaisser`.
    rendre({ ...base.facture, lignes: [{ ...LIGNE }] }, { ...AUTH, permissions: ['encaisser'] })
    fireEvent.change(document.getElementById('fc-echeance'), { target: { value: '2026-01-31' } })
    enregistrer()
    expect(await screen.findByText('Période verrouillée.')).toBeInTheDocument()
    expect(document.getElementById('fc-echeance')).toHaveAttribute('aria-invalid', 'true')
    expect(document.getElementById('fc-echeance').value).toBe('2026-01-31')
    expect(screen.getByText(/champ_inconnu : Refusé\./)).toBeInTheDocument()
    expect(screen.queryByText(/Request failed/)).toBeNull()
  })

  it("émise : l'échéance suit `encaisser` (grisée et absente du PATCH sans le code, modifiable et envoyée avec)", async () => {
    // ADRG108 (C-ADRG-VER1-003) — mutant : retirer `!peutEncaisser` du `disabled` ⇒ échec.
    const ouverte = { ...base.facture, date_echeance: '2026-11-30', lignes: [{ ...LIGNE }] }
    const adminVentes = { ...AUTH, role_nom: 'Admin Ventes', permissions: ['ventes_voir', 'ventes_creer', 'ventes_modifier'] }
    const { unmount } = rendre(ouverte, adminVentes)
    expect(document.getElementById('fc-echeance').disabled).toBe(true)
    fireEvent.change(document.getElementById('fc-note'), { target: { value: 'note admin ventes' } })
    enregistrer()
    await waitFor(() => expect(base.facture.note).toBe('note admin ventes'))
    // Relecture serveur : le corps reçu n'a jamais porté l'échéance.
    expect('date_echeance' in base.facture).toBe(false)
    unmount()

    const commercialResp = { ...AUTH, role_nom: 'Commercial responsable', permissions: ['ventes_voir', 'ventes_modifier', 'encaisser'] }
    rendre({ ...ouverte, note: base.facture.note, updated_at: base.facture.updated_at }, commercialResp)
    const echeance = document.getElementById('fc-echeance')
    expect(echeance.disabled).toBe(false)
    fireEvent.change(echeance, { target: { value: '2026-12-31' } })
    enregistrer()
    await waitFor(() => expect(base.facture.date_echeance).toBe('2026-12-31'))
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
