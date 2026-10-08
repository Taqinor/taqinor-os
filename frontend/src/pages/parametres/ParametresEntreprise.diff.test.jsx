import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* APAR16 — l'écran Paramètres (profil société) n'envoie que le SEUL diff des
   champs modifiés + l'`updated_at` lu au chargement (verrou optimiste). Avant :
   `{...form}` complet → l'enregistrement de A réécrivait le RIB que B venait
   de changer. */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

const { PROFIL, updateProfile, apiProxy } = vi.hoisted(() => {
  const PROFIL = {
    id: 1, nom: 'Démo', rib: 'RIB-B', tva_standard: 20, tva_panneaux: 10,
    ice: '', email: '', telephone: '', updated_at: '2026-10-08T10:00:00.123456Z',
  }
  const updateProfile = vi.fn((data) => Promise.resolve({ data: { ...PROFIL, ...data } }))
  // Toute API appelée au montage répond vide ; seul le profil est réel.
  const vide = () => Promise.resolve({ data: [] })
  const apiProxy = (overrides = {}) => new Proxy(overrides, {
    get: (t, k) => (k in t ? t[k] : (k === 'then' ? undefined : vi.fn(vide))),
  })
  return { PROFIL, updateProfile, apiProxy }
})
vi.mock('../../api/parametresApi', () => ({
  default: apiProxy({
    getProfile: () => Promise.resolve({ data: PROFIL }),
    updateProfile: (d) => updateProfile(d),
  }),
}))
vi.mock('../../api/crmApi', () => ({ default: apiProxy() }))
vi.mock('../../api/ventesApi', () => ({ default: apiProxy() }))
vi.mock('../../api/installationsApi', () => ({ default: apiProxy() }))
vi.mock('../../api/stockApi', () => ({ default: apiProxy() }))
vi.mock('../../api/customFieldsApi', () => ({ default: apiProxy() }))
vi.mock('../../features/stock/store/stockSlice', () => ({
  fetchCategories: () => ({ type: 'noop' }),
  fetchFournisseurs: () => ({ type: 'noop' }),
}))

import parametresReducer from '../../features/parametres/store/parametresSlice'
import ParametresEntreprise from './ParametresEntreprise'
import { diffProfilePayload } from './peConstants'

describe('APAR16 — diffProfilePayload', () => {
  it('ne garde que les clés modifiées + updated_at', () => {
    const base = { rib: 'B', tva_standard: 20, payment_terms: { r: [1, 2] } }
    const next = { rib: 'B', tva_standard: 14, payment_terms: { r: [1, 2] } }
    expect(diffProfilePayload(base, next, 'T0')).toEqual({ tva_standard: 14, updated_at: 'T0' })
  })
  it('objets imbriqués comparés par valeur', () => {
    const base = { payment_terms: { r: [1, 2] } }
    const next = { payment_terms: { r: [1, 3] } }
    expect(diffProfilePayload(base, next, 'T')).toEqual({ payment_terms: { r: [1, 3] }, updated_at: 'T' })
  })
})

describe('APAR16 — Enregistrer envoie le seul champ modifié', () => {
  afterEach(() => { cleanup(); updateProfile.mockClear() })

  it('seul le champ modifié part (avec updated_at), jamais le RIB', async () => {
    const store = configureStore({
      reducer: {
        parametres: parametresReducer,
        stock: (s = { categories: [], fournisseurs: [] }) => s,
        auth: (s = { role: 'admin', permissions: [], user: { company_est_demo: false } }) => s,
      },
    })
    const { container } = render(
      <Provider store={store}><MemoryRouter><ParametresEntreprise /></MemoryRouter></Provider>,
    )
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    const nom = container.querySelector('input[name="nom"]')
    fireEvent.change(nom, { target: { name: 'nom', value: 'Démo SARL' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    const envoye = updateProfile.mock.calls[0][0]
    expect(envoye).toEqual({ nom: 'Démo SARL', updated_at: PROFIL.updated_at })
    expect(envoye).not.toHaveProperty('rib')
  })
})
