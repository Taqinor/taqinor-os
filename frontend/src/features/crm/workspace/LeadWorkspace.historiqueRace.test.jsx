import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import api from '../../../api/axios'
import LeadWorkspace from './LeadWorkspace'

// LW43 — garde d'identité sur `historique` (fetch propre au shell, LW41) :
// une réponse LENTE du lead A ne doit plus jamais peindre le timeline du lead
// B après une navigation rapide (course reproduite en gardant la promesse de
// A EN VOL pendant le rerender vers B). ContextRail/TimelineTab sont RÉELS
// ici (le but est de prouver le RENDU final, pas juste l'appel réseau) —
// seuls les satellites hors-sujet (IdentityRail, dialogues) sont neutralisés.
// Ni A ni B ne portent `chatter_recent` : chacun déclenche donc SON PROPRE
// /historique/ (LW41), ce qui isole proprement la garde d'identité (LW43) de
// la logique « fetch évité » testée ailleurs (LeadWorkspace.historique.test.jsx).

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))
vi.mock('./IdentityRail', () => ({ default: () => <div data-testid="identity-rail" /> }))

vi.mock('../../../api/recordsApi', () => ({
  default: {
    getActivities: vi.fn(() => Promise.resolve({ data: [] })),
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    // loadFresh (LW25) rejoue systématiquement un GET détail ; il ne porte
    // pas non plus chatter_recent ici (délibéré — hors sujet de CE test).
    getLead: vi.fn((id) => Promise.resolve({ data: { id, nom: id === 1 ? 'Ali' : 'Sara', stage: 'NEW', is_archived: false } })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
  },
}))
vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })), post: vi.fn(() => Promise.resolve({ data: {} })) },
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

const LEAD_A = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false }
const LEAD_B = { id: 2, nom: 'Sara', prenom: 'K.', stage: 'NEW', is_archived: false }

function wrap(lead) {
  return (
    <Provider store={makeStore()}>
      <MemoryRouter>
        <LeadWorkspace lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>
  )
}

describe('LW43 — LeadWorkspace : garde d’identité sur le fetch historique', () => {
  it('réponse /historique/ du lead A résolue APRÈS navigation vers B → jamais peinte sur B', async () => {
    let resolveA
    api.get.mockImplementation((url) => {
      if (url === '/crm/leads/1/historique/') {
        return new Promise((res) => { resolveA = res })
      }
      if (url === '/crm/leads/2/historique/') {
        return Promise.resolve({
          data: [{ id: 6, kind: 'note', body: 'Note propre à B', user_nom: 'X', created_at: new Date().toISOString() }],
        })
      }
      return Promise.resolve({ data: [] })
    })
    const { rerender } = render(wrap(LEAD_A))
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'))

    // Navigue vers B AVANT que la réponse de A n'arrive : B déclenche SON
    // PROPRE /historique/, qui se peint normalement.
    rerender(wrap(LEAD_B))
    await screen.findByText(/Note propre à B/)

    // La réponse tardive de A arrive maintenant, avec une entrée qui NE DOIT
    // JAMAIS s'afficher sur le lead désormais ouvert (B).
    resolveA({ data: [{ id: 1, kind: 'note', body: 'FUITE DE A', user_nom: 'Y', created_at: new Date().toISOString() }] })
    await new Promise((r) => { setTimeout(r, 0) })
    expect(screen.queryByText(/FUITE DE A/)).toBeNull()
    expect(screen.getByText(/Note propre à B/)).toBeInTheDocument()
  })
})
