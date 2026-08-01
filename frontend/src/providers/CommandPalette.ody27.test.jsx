// ODY27 — la palette ⌘K ne propose JAMAIS une destination appartenant à une app
// non installée pour la société (ou interdite au rôle) : elle interroge la
// source UNIQUE des apps visibles (`useInstalledApps`, ODY1) au lieu de lister
// ses routes statiques telles quelles.
//
// Le harnais reprend EXACTEMENT celui de CommandPalette.quickcreate.test.jsx
// (mêmes mocks) ; seul le store change d'un test à l'autre.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('../lib/search/entityRoutes', () => ({
  ROUTE: {}, TYPE_LABEL: {}, TYPE_ACCENT: {},
  pathForType: () => '',
  useEntitySearch: () => ({ groups: [], loading: false, failed: false }),
}))

import { CommandPalette } from './CommandPalette'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function openPalette({ role = 'admin', permissions = [], modulesDesactives = [] } = {}) {
  const store = configureStore({
    reducer: { auth: (s = { role, permissions, modulesDesactives, user: null }) => s },
  })
  render(
    <Provider store={store}><MemoryRouter><CommandPalette /></MemoryRouter></Provider>,
  )
  act(() => { window.dispatchEvent(new Event('taqinor:command-palette')) })
}

describe('ODY27 — la palette ⌘K masque les apps non installées', () => {
  it('toutes les apps actives : les commandes Ventes ET CRM sont proposées', () => {
    openPalette()
    expect(screen.getByText('Aller aux devis')).toBeInTheDocument()
    expect(screen.getByText('Créer un devis')).toBeInTheDocument()
    expect(screen.getByText('Aller aux leads')).toBeInTheDocument()
  })

  it('app « ventes » désactivée : ses commandes de navigation ET de création disparaissent', () => {
    openPalette({ modulesDesactives: ['ventes'] })
    expect(screen.queryByText('Aller aux devis')).not.toBeInTheDocument()
    expect(screen.queryByText('Aller aux factures')).not.toBeInTheDocument()
    expect(screen.queryByText('Créer un devis')).not.toBeInTheDocument()
    // …et les autres apps ne sont pas touchées.
    expect(screen.getByText('Aller aux leads')).toBeInTheDocument()
  })

  it('app « crm » désactivée : ses commandes disparaissent, Ventes reste', () => {
    openPalette({ modulesDesactives: ['crm'] })
    expect(screen.queryByText('Aller aux leads')).not.toBeInTheDocument()
    expect(screen.queryByText('Aller aux clients')).not.toBeInTheDocument()
    expect(screen.getByText('Aller aux devis')).toBeInTheDocument()
  })

  it('la sortie vers le Menu d’accueil (transverse) survit à TOUTES les désactivations', () => {
    openPalette({ modulesDesactives: ['crm', 'ventes', 'stock', 'sav', 'installations'] })
    expect(screen.getByText(/Menu d’accueil/)).toBeInTheDocument()
  })
})
