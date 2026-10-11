// QJR574 (D-QJR5-8) — le panneau brut « Surcharges (registre) » (sélecteur de
// chemin + valeur JSON libre) est réservé aux ADMINISTRATEURS : il doublait
// Scénario, Option recommandée, nombre de panneaux et Structure, qui portent
// désormais la surcharge et le retour à l'automatique (QJR572). L'endpoint
// reste IsResponsableOrAdmin ; seule l'affordance de l'écran change.
//
// Monte réellement DevisGenerator (`?edit=7`) — garde QJR239 respectée.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorRegistreAdmin.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

// APIs mockées (aucun appel réseau réel au montage).
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { DEVIS_VIDE_ROUVERT as DEVIS_ROUVERT, declarerBeforeEachDevis } from './devisGenerator.testHelpers.jsx'

function makeStore(role) {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: role === 'admin' ? 'Directeur' : 'Commercial responsable', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

// Un brouillon déjà enregistré : le panneau « Surcharges (registre) »
// n'existe QUE sur un devis avec editDevis?.id (QJR215).

function renderGenerator(role) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: [] })
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS_ROUVERT })
  return render(
    <Provider store={makeStore(role)}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=7']}>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

declarerBeforeEachDevis({ stockApi, crmApi, ventesApi })

describe('QJR574 — le panneau brut du registre est réservé aux administrateurs', () => {
  it('absent pour un responsable (le registre est quand même lu)', async () => {
    renderGenerator('responsable')
    await waitFor(() => expect(ventesApi.lireOverrides).toHaveBeenCalledWith(7))
    await waitFor(() => expect(document.getElementById('gen-scenario')).toBeTruthy())
    expect(screen.queryByTestId('overrides-panel')).toBeNull()
  })

  it('présent pour un administrateur', async () => {
    renderGenerator('admin')
    await waitFor(() => expect(screen.getByTestId('overrides-panel')).toBeInTheDocument())
  })
})
