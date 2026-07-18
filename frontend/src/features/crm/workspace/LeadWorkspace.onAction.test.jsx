import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { toast } from 'sonner'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

/* LW16-wire — le contrat `onAction` du rail (IdentityRail/StageControl, lane 2)
   gagne deux cas : 'set-field' (édition rapide responsable/relance) et
   'change-stage' (StageControl, transitions non-SIGNED — passe par le MÊME
   moteur `changeStage` que le raccourci clavier « 1-4 », LW23), avec un toast
   d'erreur unique côté moteur (useLeadDraft.js) sur un recul de funnel (400). */
vi.mock('sonner', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, error: vi.fn(), success: vi.fn() } }
})

vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))

// IdentityRail réel n'est encore qu'un placeholder (LW14-18 pas construit) —
// on l'intercepte pour exposer le contrat `onAction` à des boutons de test,
// EXACTEMENT le patron déjà établi (AssigneePicker/CustomFieldsInput ci-dessus).
vi.mock('./IdentityRail', () => ({
  default: ({ onAction }) => (
    <div data-testid="identity-rail">
      <button type="button" onClick={() => onAction('set-field', { key: 'owner', value: '7' })}>
        set-field-owner
      </button>
      <button type="button" onClick={() => onAction('change-stage', 'CONTACTED')}>
        change-stage-contacted
      </button>
    </div>
  ),
}))

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

describe("LW16-wire — onAction('set-field'/'change-stage')", () => {
  it("'set-field' pousse la valeur dans le draft (autosauvegarde débouncée, comme toute frappe)", () => {
    renderEdit()
    fireEvent.click(screen.getByText('set-field-owner'))
    // Pas de PATCH immédiat (débounce 1.5s) — c'est du SET_FIELD, pas un
    // point-write : la preuve est l'ABSENCE d'appel synchrone à updateLead.
    expect(crmApi.updateLead).not.toHaveBeenCalled()
  })

  it("'change-stage' appelle le même moteur que le raccourci clavier « 2 » (PATCH {stage})", async () => {
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' }))
  })

  it('un recul de funnel refusé (400) surface UN SEUL toast d’erreur, jamais une exception non attrapée', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 400, data: { detail: 'stage backward' } } })
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Retour d'étape non autorisé"))
    expect(toast.error).toHaveBeenCalledTimes(1)
  })

  it('une autre erreur (réseau/500) reste silencieuse (best-effort, pas de toast)', async () => {
    crmApi.updateLead.mockRejectedValueOnce({ response: { status: 500 } })
    renderEdit()
    fireEvent.click(screen.getByText('change-stage-contacted'))
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled())
    expect(toast.error).not.toHaveBeenCalled()
  })
})
