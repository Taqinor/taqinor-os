import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import { readRecentEntities } from '../../../providers/commandActions'
import LeadWorkspace from './LeadWorkspace'

/* LW26 — actions contextuelles ⌘K (taqinor:lead-workspace-actions) + Récents.
   Mêmes neutralisations que LeadWorkspaceCreate.test.jsx, sauf LeadDevisPanel
   (exposé pour vérifier le mode passé par « Devis automatique »). */
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../../../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../../../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({
  default: (props) => <div data-testid="devis-panel" data-mode={props.mode} />,
}))
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

describe('LW26 — actions contextuelles ⌘K + Récents', () => {
  it('poste taqinor:lead-workspace-actions au montage avec les actions attendues, le retire au démontage', () => {
    const onEvt = vi.fn()
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    const { unmount } = renderEdit()
    expect(onEvt).toHaveBeenCalled()
    const actions = onEvt.mock.calls[onEvt.mock.calls.length - 1][0].detail.actions
    const ids = actions.map((a) => a.id)
    expect(ids).toEqual(expect.arrayContaining([
      'lw-wa-devis', 'lw-devis-auto', 'lw-archive', 'lw-convert', 'lw-note', 'lw-goto-toiture',
    ]))
    unmount()
    const lastCall = onEvt.mock.calls[onEvt.mock.calls.length - 1][0]
    expect(lastCall.detail.actions).toEqual([])
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
  })

  it('pousse le lead dans les Récents à l’ouverture', () => {
    renderEdit()
    const recent = readRecentEntities()
    expect(recent[0]).toMatchObject({ type: 'lead', id: 1 })
  })

  it('l’action « Devis automatique » ouvre le panneau devis en mode auto', () => {
    let captured = null
    const onEvt = (e) => { captured = e.detail.actions }
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    renderEdit()
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
    const devisAuto = captured.find((a) => a.id === 'lw-devis-auto')
    expect(devisAuto).toBeDefined()
    act(() => { devisAuto.run() })
    expect(screen.getByTestId('devis-panel')).toHaveAttribute('data-mode', 'auto')
  })

  it('l’action « Aller à : Toiture & site » fait défiler jusqu’à la section', () => {
    let captured = null
    const onEvt = (e) => { captured = e.detail.actions }
    window.addEventListener('taqinor:lead-workspace-actions', onEvt)
    renderEdit()
    window.removeEventListener('taqinor:lead-workspace-actions', onEvt)
    const goToToiture = captured.find((a) => a.id === 'lw-goto-toiture')
    expect(goToToiture).toBeDefined()
    const section = document.querySelector('[data-nav-id="toiture"]')
    expect(section).not.toBeNull()
    const scrollSpy = vi.fn()
    section.scrollIntoView = scrollSpy
    act(() => { goToToiture.run() })
    expect(scrollSpy).toHaveBeenCalled()
  })
})
