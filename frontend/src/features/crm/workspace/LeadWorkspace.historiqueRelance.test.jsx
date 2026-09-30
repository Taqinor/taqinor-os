import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, cleanup, waitFor, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'
import LeadWorkspace from './LeadWorkspace'

// ERR-QAH-CRM-HISTORIQUE-VIDE-RELANCE — après l'autosave de « Relance le », le
// panneau « Historique » affichait « Aucune activité pour le moment. » : la
// réponse du PATCH (sérialiseur d'écriture) n'embarque pas `chatter_recent`,
// qui était donc EFFACÉ de `state.server`, et `/historique/` n'était jamais
// relu. On prouve : (1) après un autosave réussi, `/historique/` est relu ;
// (2) `chatter_recent` survit à la réponse du PATCH.

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
// Le rail capture `onAction` : c'est par lui que « Relance le » écrit
// (onAction('set-field', { key: 'relance_date', … })).
let railOnAction = null
let railServer = null
vi.mock('./IdentityRail', () => ({
  default: ({ onAction, state }) => {
    railOnAction = onAction
    railServer = state?.server
    return <div data-testid="identity-rail" />
  },
}))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    getTags: vi.fn(() => Promise.resolve({ data: [] })),
    getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    // Sérialiseur d'ÉCRITURE : PAS de `chatter_recent` dans la réponse.
    updateLead: vi.fn((id, corps) => Promise.resolve({ data: { id, nom: 'Ali', stage: 'NEW', ...corps } })),
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

describe('ERR-QAH-CRM-HISTORIQUE-VIDE-RELANCE — l’historique survit à l’autosave', () => {
  it('« Relance le » enregistré → /historique/ relu et chatter_recent conservé', async () => {
    const ancienne = { id: 9, kind: 'note', body: 'Déjà là', user_nom: 'Sami', created_at: new Date().toISOString() }
    const lead = {
      id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false,
      chatter_recent: [ancienne],
    }
    renderEdit(lead)
    await waitFor(() => expect(railOnAction).toBeTypeOf('function'))
    expect(api.get).not.toHaveBeenCalledWith('/crm/leads/1/historique/')

    act(() => { railOnAction('set-field', { key: 'relance_date', value: '2026-10-15T09:00' }) })

    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalled(), { timeout: 5000 })
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/crm/leads/1/historique/'), { timeout: 5000 })
    expect(railServer?.chatter_recent).toEqual([ancienne])
  })
})
