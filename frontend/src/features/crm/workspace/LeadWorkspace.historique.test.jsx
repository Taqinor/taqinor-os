import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

// LW41 — `chatter_recent` doit vraiment économiser la requête historique. Avant
// ce fix, le shell appelait TOUJOURS `/historique/` au montage même si le GET
// détail embarquait déjà `chatter_recent` (LW30) — l'ouverture coûtait PLUS
// cher qu'avant, pas moins.

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))
vi.mock('./ContextRail', () => ({ default: () => null }))
vi.mock('./IdentityRail', () => ({ default: () => <div data-testid="identity-rail" /> }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))
vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore() {
  return configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
}

function renderEdit(lead) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <LeadWorkspace lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

describe('LW41 — pas de double requête historique quand chatter_recent est déjà là', () => {
  it('lead ouvert avec chatter_recent non-vide → AUCUN GET /historique/', async () => {
    const lead = {
      id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false,
      chatter_recent: [{ id: 9, kind: 'note', body: 'Déjà là', user_nom: 'Sami', created_at: new Date().toISOString() }],
    }
    renderEdit(lead)
    // Laisse les effets/microtasks s'écouler.
    await waitFor(() => expect(crmApi.getAssignableUsers).toHaveBeenCalled())
    expect(api.get).not.toHaveBeenCalledWith('/crm/leads/1/historique/')
  })

  it('lead ouvert SANS chatter_recent (absent/vide) → le GET /historique/ part toujours', async () => {
    const lead = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, chatter_recent: [] }
    renderEdit(lead)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))
  })
})
