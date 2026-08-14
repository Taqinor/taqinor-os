import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import CrmCockpit from './CrmCockpit'

/* ODY15 — rendu smoke du cockpit CRM (ModuleHero + actions rapides + KPI).
   Aucun appel réseau réel : `fetchClients`/`fetchLeads` sont mockés en no-op
   (même patron que ClientList.test.jsx) et `CrmInsightsPanel` (VX219/WR9, son
   propre appel réseau) est mocké en stub — ce test vérifie SEULEMENT que le
   cockpit assemble correctement ModuleHero + actions + KPI + le panneau
   d'insights, pas le comportement interne du panneau (déjà couvert
   ailleurs). */

vi.mock('../../features/crm/store/crmSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchClients: () => ({ type: 'crm/fetchClients/noop' }),
    fetchLeads: () => ({ type: 'crm/fetchLeads/noop' }),
  }
})

vi.mock('./leads/CrmInsightsPanel', () => ({
  default: () => <div data-testid="crm-insights-stub" />,
}))

// NTCRM15 — le widget comptes dormants a son propre appel réseau (couvert
// par son propre test) ; ce smoke test ne vérifie que l'assemblage cockpit.
vi.mock('./DormantAccountsWidget', () => ({
  default: () => <div data-testid="dormant-accounts-stub" />,
}))

// NTCRM29 — même patron : le widget portefeuille a son propre appel réseau
// (couvert par son propre test), stubé ici pour ce smoke test d'assemblage.
vi.mock('./dashboard/PortfolioWidget', () => ({
  default: () => <div data-testid="portfolio-widget-stub" />,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore({ clients = [], leads = [] } = {}) {
  return configureStore({
    reducer: {
      crm: (state = { clients, leads, loading: false, error: null }) => state,
    },
  })
}

function mount(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/crm/cockpit']}>
        <ThemeProvider>
          <CrmCockpit />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('CrmCockpit — rendu smoke (ODY15)', () => {
  it('affiche le titre CRM (ModuleHero) et les actions rapides', () => {
    mount()
    expect(screen.getByRole('heading', { name: 'CRM' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nouveau lead/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nouveau client/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Carte/ })).toBeInTheDocument()
  })

  it('affiche les compteurs KPI dérivés des clients/leads chargés', () => {
    mount({
      clients: [{ id: 1 }, { id: 2 }],
      leads: [
        { id: 1, is_archived: false, perdu: false },
        { id: 2, is_archived: true, perdu: false },
      ],
    })
    const stats = screen.getByTestId('crm-cockpit-stats')
    expect(stats).toHaveTextContent('Clients')
    expect(stats).toHaveTextContent('2')
    expect(stats).toHaveTextContent('Leads actifs')
    expect(stats).toHaveTextContent('1')
  })

  it('rend le panneau d’insights CRM existant (VX219/WR9), aucune deuxième implémentation', () => {
    mount()
    expect(screen.getByTestId('crm-insights-stub')).toBeInTheDocument()
  })
})
