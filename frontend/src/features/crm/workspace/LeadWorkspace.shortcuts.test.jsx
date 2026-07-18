import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* LW23 — mode ÉDITION : registre de raccourcis propre (a/d/n/1-4). Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx (les satellites/rails ne
   sont PAS encore construits par les autres lanes — on teste le CÂBLAGE de
   cette lane, pas leur contenu). */
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
afterEach(() => { cleanup(); vi.clearAllMocks() })

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

describe('LW23 — raccourcis propres (a/d/n/1-4)', () => {
  it('« a » archive le lead (leaveGuard, sans clic)', async () => {
    renderEdit()
    fireEvent.keyDown(document, { key: 'a' })
    await waitFor(() => expect(crmApi.archiverLead).toHaveBeenCalledWith(1))
  })

  it('« d » focus le picker Responsable (hook DOM stable .ap-trigger, une autre lane)', () => {
    renderEdit()
    // Simule le hook DOM que l'IdentityRail (LW14-18, autre lane) posera —
    // cette lane ne dépend QUE de la classe stable, jamais de son contenu.
    // Posé DANS le contenu du Dialog (le focus-trap Radix refuse de sortir
    // du contenu de la boîte de dialogue — un nœud posé hors de celle-ci ne
    // pourrait de toute façon jamais recevoir le focus réel).
    const trigger = document.createElement('button')
    trigger.className = 'ap-trigger'
    document.querySelector('[role="dialog"]').appendChild(trigger)
    fireEvent.keyDown(document, { key: 'd' })
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it('« n » émet lw:open-note-composer avec le leadId (ContextRail — LW19-21 — doit écouter)', () => {
    renderEdit()
    const onEvt = vi.fn()
    window.addEventListener('lw:open-note-composer', onEvt)
    fireEvent.keyDown(document, { key: 'n' })
    expect(onEvt).toHaveBeenCalledTimes(1)
    expect(onEvt.mock.calls[0][0].detail).toEqual({ leadId: 1 })
    window.removeEventListener('lw:open-note-composer', onEvt)
  })

  it('« 2 » change l’étape vers CONTACTED (jamais SIGNED/COLD à une touche)', async () => {
    renderEdit()
    fireEvent.keyDown(document, { key: '2' })
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' }))
  })

  it('mode création (pas de lead) : les raccourcis sont désactivés (enabled=false)', async () => {
    renderEdit(null)
    fireEvent.keyDown(document, { key: 'a' })
    await new Promise((r) => setTimeout(r, 0))
    expect(crmApi.archiverLead).not.toHaveBeenCalled()
  })
})
