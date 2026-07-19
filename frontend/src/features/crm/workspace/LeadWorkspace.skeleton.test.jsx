import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, cleanup, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* LW25 — squelette d'ouverture, EN FORME de la vraie grille (rail identité /
   centre / rail contexte), piloté par useDelayedLoading + FadeSwap. Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx. */
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: {} })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    mergeLeads: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    archiverLead: vi.fn(() => Promise.resolve({ data: {} })),
    restaurerLead: vi.fn(() => Promise.resolve({ data: {} })),
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

const LEAD_A = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false }

beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  crmApi.getLead.mockImplementation(() => Promise.resolve({ data: {} }))
})

function renderEdit(lead = LEAD_A) {
  const store = configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace lead={lead} onClose={vi.fn()} onSaved={vi.fn()} />
      </MemoryRouter>
    </Provider>,
  )
}

// FadeSwap garde TOUJOURS les deux couches (squelette/contenu) montées — seul
// `aria-hidden` bascule (crossfade CSS). La visibilité RÉELLE se lit donc là,
// jamais par simple présence DOM de `.lw-skeleton-pane` (toujours présente).
function skeletonVisible() {
  const layer = document.querySelector('.lw-skeleton-swap > div')
  return layer?.getAttribute('aria-hidden') === 'false'
}

describe('LW25 — squelette d’ouverture en forme de grille', () => {
  it('un chargement qui dépasse 500ms affiche le squelette (rail/centre/droite), jamais un spinner nu', async () => {
    vi.useFakeTimers()
    try {
      let resolveGet
      crmApi.getLead.mockImplementation(() => new Promise((resolve) => { resolveGet = resolve }))
      renderEdit()
      await act(async () => { await vi.advanceTimersByTimeAsync(500) })
      expect(skeletonVisible()).toBe(true)
      expect(document.querySelectorAll('.lw-skeleton-pane').length).toBeGreaterThanOrEqual(3)
      // Le GET systématique (LW25) résout et REMPLACE le squelette par la
      // grille réelle — c'est aussi le mécanisme de re-fetch d'arrière-plan
      // requis par LW24 après une navigation vers un voisin pré-chargé.
      await act(async () => { resolveGet({ data: LEAD_A }) })
      expect(skeletonVisible()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('une ouverture rapide (<300ms) ne montre jamais le squelette', async () => {
    vi.useFakeTimers()
    try {
      crmApi.getLead.mockResolvedValue({ data: LEAD_A })
      renderEdit()
      await act(async () => { await vi.advanceTimersByTimeAsync(200) })
      expect(skeletonVisible()).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })
})
