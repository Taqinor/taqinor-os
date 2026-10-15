import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { LEAD_A, mockMatchMedia } from '../../../test/leadWorkspaceMocks'
import { render, screen, cleanup, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import { resetPrefetchCache, getPrefetched } from './leadPrefetch'
import LeadWorkspace from './LeadWorkspace'

/* LW24 — pré-chargement en idle des voisins de file (J/K instantané). Mêmes
   neutralisations que LeadWorkspaceCreate.test.jsx. Le RE-FETCH en
   arrière-plan après un rendu-cache (garde res.id===leadId) est le même
   mécanisme que le GET systématique d'ouverture de LW25 — vérifié dans
   LeadWorkspace.skeleton.test.jsx une fois ce mécanisme construit ; ici on
   couvre la partie propre à CETTE tâche : alimentation du cache + premier
   rendu instantané depuis le cache. */
vi.mock('../../../pages/crm/leads/LeadDevisPanel', () => ({ default: () => null }))
vi.mock('../../../pages/crm/leads/SigneDialog', () => ({ default: () => null }))

vi.mock('../../../api/crmApi', async () => (await import('../../../test/leadWorkspaceMocks')).crmApiLeadWorkspace())

const LEAD_B_ROW = { id: 2, nom: 'Karim', stage: 'NEW' } // ligne PARTIELLE de liste

beforeEach(() => {
  mockMatchMedia(false)
  try { localStorage.clear() } catch { /* noop */ }
  try { sessionStorage.clear() } catch { /* noop */ }
  resetPrefetchCache()
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  crmApi.getLead.mockImplementation(() => Promise.resolve({ data: {} }))
})

function makeStore() {
  return configureStore({ reducer: { crm: crmReducer, auth: (s = { user: { id: 42 } }) => s } })
}
function tree(store, { lead, leadsQueue, onNavigateLead, onClose, onSaved }) {
  return (
    <Provider store={store}>
      <MemoryRouter>
        <LeadWorkspace
          lead={lead} leadsQueue={leadsQueue} onNavigateLead={onNavigateLead} onClose={onClose} onSaved={onSaved}
        />
      </MemoryRouter>
    </Provider>
  )
}
function renderEdit({ lead = LEAD_A, leadsQueue = null, onNavigateLead = vi.fn(), onClose = vi.fn(), onSaved = vi.fn() } = {}) {
  const store = makeStore()
  const props = { lead, leadsQueue, onNavigateLead, onClose, onSaved }
  const utils = render(tree(store, props))
  const rerenderWith = (nextProps) => utils.rerender(tree(store, { ...props, ...nextProps }))
  return { ...utils, rerenderWith }
}

describe('LW24 — pré-chargement en idle des voisins de file', () => {
  it('après ouverture de A avec file [A,B], getLead(B) est appelé en idle et peuple le cache', async () => {
    vi.useFakeTimers()
    try {
      renderEdit({ lead: LEAD_A, leadsQueue: [LEAD_A, LEAD_B_ROW] })
      await act(async () => { await vi.advanceTimersByTimeAsync(300) })
      // `advanceTimersByTimeAsync` flushe déjà les micro-tâches à chaque pas
      // — pas besoin de `waitFor` (dont le polling utiliserait les MÊMES
      // horloges factices, sans jamais avancer tout seul → faux timeout).
      expect(crmApi.getLead).toHaveBeenCalledWith(2)
      expect(getPrefetched(2)).not.toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('pas de file (leadsQueue=null) : aucun pré-chargement de voisin', async () => {
    vi.useFakeTimers()
    try {
      renderEdit({ lead: LEAD_A, leadsQueue: null })
      await act(async () => { await vi.advanceTimersByTimeAsync(500) })
      const calledIds = crmApi.getLead.mock.calls.map((c) => c[0])
      expect(calledIds).not.toContain(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('naviguer vers un voisin déjà pré-chargé rend INSTANTANÉMENT la donnée complète du cache', async () => {
    vi.useFakeTimers()
    try {
      const fullB = { id: 2, nom: 'Karim', prenom: 'Fadel', stage: 'CONTACTED', ville: 'Rabat' }
      crmApi.getLead.mockImplementation((id) => (id === 2
        ? Promise.resolve({ data: fullB })
        : new Promise(() => {}))) // jamais résolu pour les autres ids — non pertinent ici

      const { rerenderWith } = renderEdit({ lead: LEAD_A, leadsQueue: [LEAD_A, LEAD_B_ROW] })
      // Idle → pré-chargement de B, résolu avec la donnée COMPLÈTE.
      await act(async () => { await vi.advanceTimersByTimeAsync(300) })
      expect(getPrefetched(2)).toEqual(fullB)

      // Navigation vers B (ligne PARTIELLE, sans prénom) — le rendu doit
      // afficher IMMÉDIATEMENT le prénom du CACHE.
      await act(async () => { rerenderWith({ lead: LEAD_B_ROW }) })
      expect(screen.getAllByText(/Karim Fadel/).length).toBeGreaterThan(0)
    } finally {
      vi.useRealTimers()
    }
  })
})
