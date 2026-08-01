// ODY27 — la recherche globale ne propose que les types d'entités appartenant à
// une app INSTALLÉE pour la société et AUTORISÉE pour le rôle. Le backend gate
// déjà la recherche (ARC29) ; ce filtre est la ceinture côté client — et le seul
// qui connaisse le rôle courant.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../../api/reportingApi', () => ({
  default: { search: vi.fn() },
}))

import reportingApi from '../../api/reportingApi'
import GlobalSearch from './GlobalSearch'

// Le serveur renvoie DEUX groupes : un de l'app Ventes, un de l'app CRM.
const GROUPS = [
  { type: 'devis', label: 'Devis', results: [{ id: 1, label: 'DV-2026-0001' }] },
  { type: 'lead', label: 'Leads', results: [{ id: 2, label: 'Lead Casablanca' }] },
]

function renderSearch({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
  return render(
    <Provider store={store}><MemoryRouter><GlobalSearch /></MemoryRouter></Provider>,
  )
}

async function search(opts) {
  renderSearch(opts)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'casa' } })
  // Débounce ~250 ms puis rendu du panneau : `findBy*` attend pour nous.
  await screen.findByText('Leads')
}

describe('ODY27 — recherche globale filtrée par app installée', () => {
  beforeEach(() => {
    reportingApi.search.mockReset()
    reportingApi.search.mockResolvedValue({ data: { groups: GROUPS } })
  })
  afterEach(() => { cleanup(); vi.clearAllMocks() })

  it('toutes les apps actives : les deux groupes sont proposés', async () => {
    await search()
    expect(screen.getByText('Devis')).toBeInTheDocument()
    expect(screen.getByText('DV-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('Lead Casablanca')).toBeInTheDocument()
  })

  it('app « ventes » désactivée : le groupe Devis disparaît, les Leads restent', async () => {
    await search({ modulesDesactives: ['ventes'] })
    expect(screen.queryByText('Devis')).not.toBeInTheDocument()
    expect(screen.queryByText('DV-2026-0001')).not.toBeInTheDocument()
    expect(screen.getByText('Lead Casablanca')).toBeInTheDocument()
  })
})
