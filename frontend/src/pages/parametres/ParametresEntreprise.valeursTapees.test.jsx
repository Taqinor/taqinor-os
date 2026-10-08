import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* APAR39 — le profil société envoie les valeurs TAPÉES telles quelles : vider
   « SLA lead » n'envoie plus 0 (SLA désactivé) en silence, taper 0 dans le
   tarif ONEE n'est plus remplacé par 1.75. Le serveur juge (400 sous le
   champ). */

vi.mock('../../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))

const { PROFIL, updateProfile, apiProxy } = vi.hoisted(() => {
  const PROFIL = {
    id: 1, nom: 'Démo', rib: 'RIB', tva_standard: 20, tva_panneaux: 10,
    lead_sla_hours: 24, onee_tarif_kwh: 1.75, productible_kwh_kwc: 1600,
    updated_at: '2026-10-08T10:00:00Z',
  }
  const updateProfile = vi.fn(() => Promise.reject({ response: { data: {
    lead_sla_hours: ['Un nombre entier valide est requis.'] } } }))
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

function rendre() {
  const store = configureStore({
    reducer: {
      parametres: parametresReducer,
      stock: (s = { categories: [], fournisseurs: [] }) => s,
      auth: (s = { role: 'admin', permissions: [], user: { company_est_demo: false } }) => s,
    },
  })
  return render(
    <Provider store={store}><MemoryRouter><ParametresEntreprise /></MemoryRouter></Provider>,
  )
}

async function ouvrirOnglet(container, libelle, champ) {
  await waitFor(() => expect(container.querySelector('input[name="nom"]')).not.toBeNull())
  fireEvent.click(screen.getAllByRole('button', { name: libelle })[0])
  await waitFor(() => expect(container.querySelector(`input[name="${champ}"]`)).not.toBeNull())
  return container.querySelector(`input[name="${champ}"]`)
}

describe('APAR39 — valeurs tapées telles quelles', () => {
  afterEach(() => { cleanup(); updateProfile.mockClear() })

  it('SLA lead vidé : part vide (jamais 0 en silence)', async () => {
    const { container } = rendre()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0]).toEqual({ lead_sla_hours: '', updated_at: PROFIL.updated_at })
    // Le refus serveur s'affiche (bandeau qui nomme l'erreur).
    expect(await screen.findByText(/nombre entier valide/)).toBeInTheDocument()
  })

  it('SLA 1.5 : part 1.5 (le serveur juge), jamais tronqué', async () => {
    const { container } = rendre()
    const sla = await ouvrirOnglet(container, 'Leads', 'lead_sla_hours')
    fireEvent.change(sla, { target: { name: 'lead_sla_hours', value: '1.5' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0].lead_sla_hours).toBe(1.5)
  })

  it('tarif ONEE 0 : part 0, jamais 1.75', async () => {
    const { container } = rendre()
    const onee = await ouvrirOnglet(container, 'Avancé', 'onee_tarif_kwh')
    fireEvent.change(onee, { target: { name: 'onee_tarif_kwh', value: '0' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(updateProfile).toHaveBeenCalledTimes(1))
    expect(updateProfile.mock.calls[0][0].onee_tarif_kwh).toBe(0)
  })
})
