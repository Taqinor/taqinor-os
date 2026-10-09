import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* Harnais PARTAGÉ des tests de l'écran Paramètres › profil société
   (APAR16 diff, APAR38 droit d'écrire, APAR39 valeurs tapées) : les doubles de
   module et le rendu vivent ici une seule fois au lieu d'être recopiés dans
   chaque fichier de test (check_duplicats_litteraux).

   À importer AVANT tout autre module applicatif dans le fichier de test : les
   `vi.mock` ci-dessous sont enregistrés à l'évaluation de ce module. Toute API
   appelée au montage répond vide ; seul le profil (`definirProfil`) est réel,
   et `updateProfile` est un `vi.fn` dont chaque test fixe l'implémentation. */

const h = vi.hoisted(() => {
  const etat = { profil: {} }
  const updateProfile = vi.fn()
  const vide = () => Promise.resolve({ data: [] })
  const apiProxy = (overrides = {}) => new Proxy(overrides, {
    get: (t, k) => (k in t ? t[k] : (k === 'then' ? undefined : vi.fn(vide))),
  })
  return { etat, updateProfile, apiProxy }
})

vi.mock('../lib/monitoring', () => ({
  isMonitoringEnabled: () => false,
  initMonitoring: () => Promise.resolve(false),
  captureException: () => {},
  bindCompany: () => {},
}))
vi.mock('../api/parametresApi', () => ({
  default: h.apiProxy({
    getProfile: () => Promise.resolve({ data: h.etat.profil }),
    updateProfile: (d) => h.updateProfile(d),
  }),
}))
vi.mock('../api/crmApi', () => ({ default: h.apiProxy() }))
vi.mock('../api/ventesApi', () => ({ default: h.apiProxy() }))
vi.mock('../api/installationsApi', () => ({ default: h.apiProxy() }))
vi.mock('../api/stockApi', () => ({ default: h.apiProxy() }))
vi.mock('../api/customFieldsApi', () => ({ default: h.apiProxy() }))
vi.mock('../features/stock/store/stockSlice', () => ({
  fetchCategories: () => ({ type: 'noop' }),
  fetchFournisseurs: () => ({ type: 'noop' }),
}))

import parametresReducer from '../features/parametres/store/parametresSlice'
import ParametresEntreprise from '../pages/parametres/ParametresEntreprise'

export const updateProfile = h.updateProfile

export function definirProfil(profil) {
  h.etat.profil = profil
}

// `auth` : tranche auth du store (rôle, role_nom, permissions) ; par défaut un
// admin hérité (palier admin, aucune permission fine servie).
export function rendreParametresEntreprise(auth = { role: 'admin', permissions: [] }) {
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
