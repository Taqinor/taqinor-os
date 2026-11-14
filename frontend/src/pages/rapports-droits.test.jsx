import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* ADRG118 / ADRG119 — `/rapports` ne charge ni n'affiche une carte dont la
   route serveur refuse le compte (403 + console.error + « Rapport
   indisponible ») : coût de revient, commissions, rentabilité au palier admin
   (IsAdminRole) ; Service (chantiers + SAV) à la lecture des chantiers. */

const { apiGet, reporting } = vi.hoisted(() => {
  const refus = () => Promise.reject(new Error('hors test'))
  const fns = {}
  return {
    apiGet: vi.fn(refus),
    reporting: new Proxy(fns, { get: (t, k) => (t[k] ??= vi.fn(refus)) }),
  }
})

vi.mock('../api/axios', () => ({ default: { get: apiGet } }))
vi.mock('../api/reportingApi', () => ({ default: reporting }))
vi.mock('../api/crmApi', () => ({
  default: { getAttributionLeads: vi.fn(() => Promise.reject(new Error('hors test'))) },
}))
vi.mock('../utils/fetchAllPages', () => ({ default: vi.fn(() => Promise.resolve([])) }))

import { Component as Rapports } from './Rapports'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function monter(auth) {
  const store = configureStore({
    reducer: { auth: (state = { permissions: [], role: null, ...auth }) => state },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><Rapports /></MemoryRouter>
    </Provider>,
  )
}

const CARTES_ADMIN = ['Coût de revient par chantier', 'Commissions commerciales', 'Rentabilité par segment']

async function ouvrir(onglet) {
  await userEvent.setup().click(screen.getByRole('tab', { name: onglet }))
}

describe('Rapports — cartes selon le droit de leur route', () => {
  it('hors palier admin : ni coût de revient, ni commissions, ni rentabilité', async () => {
    for (const auth of [
      { role: 'normal', permissions: ['ventes_voir', 'crm_voir'] },
      { role: 'responsable', permissions: ['ventes_voir', 'crm_voir'] },
    ]) {
      monter(auth)
      await waitFor(() => expect(reporting.analytics).toHaveBeenCalled())
      expect(reporting.jobCosting).not.toHaveBeenCalled()
      expect(reporting.commissions).not.toHaveBeenCalled()
      expect(reporting.profitability).not.toHaveBeenCalled()
      await ouvrir('Insights')
      await screen.findByText('Analytics (délais & kWc installés)')
      for (const titre of CARTES_ADMIN) expect(screen.queryByText(titre)).toBeNull()
      cleanup(); vi.clearAllMocks()
    }
  })

  it('palier admin : les trois cartes chargées et rendues', async () => {
    monter({ role: 'admin', permissions: [] })
    await waitFor(() => expect(reporting.jobCosting).toHaveBeenCalled())
    expect(reporting.commissions).toHaveBeenCalled()
    expect(reporting.profitability).toHaveBeenCalled()
    await ouvrir('Insights')
    for (const titre of CARTES_ADMIN) expect(await screen.findByText(titre)).toBeInTheDocument()
  })

  const SERVICE = '/reporting/reports/service/'
  const demandes = () => apiGet.mock.calls.map(([url]) => url)

  it('sans lecture des chantiers : ni requête ni carte Service', async () => {
    monter({ role: 'normal', permissions: ['ventes_voir', 'crm_voir', 'stock_voir'] })
    await waitFor(() => expect(demandes()).toContain('/reporting/reports/sales/'))
    expect(demandes()).not.toContain(SERVICE)
    await ouvrir('Service')
    expect(screen.queryByText('Service (chantiers + SAV)')).toBeNull()
    expect(screen.queryByText('Rapport indisponible')).toBeNull()
  })

  it('Technicien responsable (installation_voir) : Service demandé, carte rendue', async () => {
    monter({ role: 'responsable', permissions: ['installation_voir', 'sav_voir'] })
    await waitFor(() => expect(demandes()).toContain(SERVICE))
    await ouvrir('Service')
    expect(await screen.findByText('Service (chantiers + SAV)')).toBeInTheDocument()
  })
})
