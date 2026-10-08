import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* APAR38 — l'écran Paramètres reflète le droit `parametres_modifier` (garde
   serveur ASEC31) : un Admin RH (palier responsable, sans le droit) voit la
   page en LECTURE SEULE (« Enregistrer » inerte) ; un Directeur écrit. */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

const { PROFIL, apiProxy } = vi.hoisted(() => {
  const PROFIL = {
    id: 1, nom: 'Démo', rib: 'RIB', tva_standard: 20, tva_panneaux: 10,
    updated_at: '2026-10-08T10:00:00Z',
  }
  const vide = () => Promise.resolve({ data: [] })
  const apiProxy = (overrides = {}) => new Proxy(overrides, {
    get: (t, k) => (k in t ? t[k] : (k === 'then' ? undefined : vi.fn(vide))),
  })
  return { PROFIL, apiProxy }
})
vi.mock('../../api/parametresApi', () => ({
  default: apiProxy({ getProfile: () => Promise.resolve({ data: PROFIL }) }),
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

function rendre(auth) {
  const store = configureStore({
    reducer: {
      parametres: parametresReducer,
      stock: (s = { categories: [], fournisseurs: [] }) => s,
      auth: (s = { user: { company_est_demo: false }, ...auth }) => s,
    },
  })
  return render(
    <Provider store={store}><MemoryRouter><ParametresEntreprise /></MemoryRouter></Provider>,
  )
}

describe('APAR38 — droit parametres_modifier', () => {
  afterEach(cleanup)

  it('Admin RH : lecture seule, Enregistrer désactivé, champs inertes', async () => {
    const { container } = rendre({
      role: 'responsable', role_nom: 'Admin RH', permissions: ['rh_voir'],
    })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.getByTestId('parametres-lecture-seule')).toHaveTextContent(/Lecture seule/)
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeDisabled()
    expect(container.querySelector('input[name="nom"]')).toBeDisabled()
  })

  it('Directeur : écriture inchangée', async () => {
    const { container } = rendre({
      role: 'admin', role_nom: 'Directeur', permissions: ['parametres_modifier'],
    })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.queryByTestId('parametres-lecture-seule')).toBeNull()
    expect(screen.getByRole('button', { name: /Enregistrer/ })).not.toBeDisabled()
    expect(container.querySelector('input[name="nom"]')).not.toBeDisabled()
  })

  it('compte hérité sans rôle fin (palier responsable) : comportement historique du serveur', async () => {
    const { container } = rendre({ role: 'responsable', role_nom: null, permissions: [] })
    await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
    expect(screen.queryByTestId('parametres-lecture-seule')).toBeNull()
  })
})
