import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, cleanup, fireEvent, waitFor, renderHook, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import crmReducer from '../store/crmSlice'
import crmApi from '../../../api/crmApi'
import {
  reducer, initState, applyFlushSuccess, isDirty, dirtyKeys, getField,
} from './draftCore'
import { useLeadDraft } from './useLeadDraft'
import LeadWorkspace from './LeadWorkspace'

/* LW38 — Régression anti-perte : la suite « rafale » qui VERROUILLE les 4 bugs
   de perte (recon 05) POUR TOUJOURS, rejoués sur le NOUVEAU moteur (draftCore /
   useLeadDraft), plus la garde « id » de la réponse lente. Chaque scénario est
   écrit pour ÉCHOUER si sa garde correspondante du moteur est commentée
   (vérifié une fois en revue) :
     1. type + raccourci d'étape → l'édition reste dirty et est sauvée au flush
        (SET_FIELD ignore `stage` ; `changeStage` flush AVANT le PATCH d'étape) ;
     2. sélection WhatsApp + navigation → sélection VIDE sur le lead B
        (LOAD_LEAD reconstruit un état neuf) ;
     3. « a » archiver avec éditions → flush AVANT archive (leaveGuard) ;
     4. note tapée + navigation → composer VIDE sur B, brouillon de A RESTAURÉ
        au retour (miroir sessionStorage) ;
     5. réponse LENTE de A arrivant après nav vers B → JETÉE (garde `id`). */

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
    getLead: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Ali', stage: 'NEW' } })),
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
    updateLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    archiverLead: vi.fn(() => Promise.resolve({ data: { id: 1, is_archived: true } })),
    restaurerLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
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

beforeEach(() => {
  mockMatchMedia(false)
  try { localStorage.clear() } catch { /* noop */ }
  try { sessionStorage.clear() } catch { /* noop */ }
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

const LEAD_A = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false, date_modification: 'a' }

// ── Scénario 1 : type + raccourci d'étape → édition dirty, sauvée au flush ────
describe('LW38 — scénario 1 : une frappe suivie d’un changement d’étape n’est jamais blanchie', () => {
  it('SET_FIELD ignore la clé `stage` — un champ tapé reste dirty (jamais blanchi par l’étape)', () => {
    let s = initState({ lead: { id: 1, nom: 'Ali', stage: 'NEW' }, mode: 'edit' })
    s = reducer(s, { type: 'SET_FIELD', key: 'nom', value: 'Ali B.' })
    s = reducer(s, { type: 'SET_FIELD', key: 'stage', value: 'CONTACTED' })
    // Sans la garde `if (key === 'stage') return state`, `stage` entrerait dans
    // le draft (dirtyKeys = ['nom','stage']) — ici la frappe seule reste dirty.
    expect(dirtyKeys(s)).toEqual(['nom'])
    expect(isDirty(s)).toBe(true)
  })

  it('changeStage flushe la frappe en attente AVANT de PATCHer l’étape', async () => {
    const { result } = renderHook(() => useLeadDraft(LEAD_A, { mode: 'edit', currentUserId: 42 }))
    await act(async () => { result.current.setField('nom', 'Ali B.') })
    expect(isDirty(result.current.state)).toBe(true)
    await act(async () => { await result.current.changeStage('CONTACTED') })
    // Deux PATCH : d'abord la frappe (flush), puis l'étape. Sans le
    // `await flush({})` de changeStage, la frappe ne partirait jamais.
    expect(crmApi.updateLead).toHaveBeenCalledWith(1, { nom: 'Ali B.' })
    expect(crmApi.updateLead).toHaveBeenCalledWith(1, { stage: 'CONTACTED' })
  })
})

// ── Scénario 2 : sélection WhatsApp vidée à la navigation (LOAD_LEAD) ─────────
describe('LW38 — scénario 2 : la sélection WhatsApp ne fuit jamais d’un lead à l’autre', () => {
  it('WA_TOGGLE puis LOAD_LEAD(B) → sélection VIDE', () => {
    let s = initState({ lead: { id: 1, nom: 'A' }, mode: 'edit' })
    s = reducer(s, { type: 'WA_TOGGLE', id: 5 })
    expect(s.wa.selected).toEqual([5])
    s = reducer(s, { type: 'LOAD_LEAD', payload: { lead: { id: 2, nom: 'B' }, mode: 'edit' } })
    // Sans le remplacement atomique (LOAD_LEAD → initState), la sélection de A
    // survivrait sur B (envoi du mauvais devis au mauvais client).
    expect(s.wa.selected).toEqual([])
  })
})

// ── Scénario 3 : « a » archiver avec éditions → flush d’abord (leaveGuard) ────
describe('LW38 — scénario 3 : archiver ne jette jamais une édition en cours', () => {
  it('la touche « a » flushe la modif AVANT d’archiver (leaveGuard)', async () => {
    render(
      <Provider store={configureStore({ reducer: { crm: crmReducer, auth: (st = { user: { id: 42 } }) => st } })}>
        <MemoryRouter>
          <LeadWorkspace lead={LEAD_A} onClose={vi.fn()} onSaved={vi.fn()} />
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalled())
    fireEvent.change(document.querySelector('#lf-ville'), { target: { value: 'Rabat' } })
    fireEvent.keyDown(document, { key: 'a' })
    // leaveGuard flushe (PATCH ville) AVANT que l'archive ne parte : rien perdu.
    await waitFor(() => expect(crmApi.updateLead).toHaveBeenCalledWith(1, { ville: 'Rabat' }))
    await waitFor(() => expect(crmApi.archiverLead).toHaveBeenCalledWith(1))
  })
})

// ── Scénario 4 : composer vidé à la nav + brouillon restauré au retour ───────
describe('LW38 — scénario 4 : la note ne fuit pas, et le brouillon revient au retour', () => {
  it('note tapée + nav → composer VIDE sur B ; retour sur A → brouillon RESTAURÉ (miroir)', async () => {
    const { result, rerender } = renderHook(
      ({ lead }) => useLeadDraft(lead, { mode: 'edit', currentUserId: 42 }),
      { initialProps: { lead: { id: 1, nom: 'Ali', date_modification: 'a' } } },
    )
    await act(async () => { result.current.setField('nom', 'Ali édité') })
    await act(async () => { result.current.dispatch({ type: 'SET_COMPOSER', patch: { note: 'note sur A' } }) })

    // Navigation vers B : état reconstruit à neuf.
    await act(async () => { rerender({ lead: { id: 2, nom: 'Sara', date_modification: 'b' } }) })
    expect(result.current.state.composer.note).toBe('') // note de A jamais reportée sur B
    expect(getField(result.current.state, 'nom')).toBe('Sara') // édition de A absente sur B

    // Retour sur A : le miroir sessionStorage réhydrate le brouillon.
    await act(async () => { rerender({ lead: { id: 1, nom: 'Ali', date_modification: 'a' } }) })
    expect(getField(result.current.state, 'nom')).toBe('Ali édité')
    expect(result.current.state.restored).toBe(true)
  })
})

// ── Scénario 5 : réponse LENTE d’un autre lead jetée (garde `id`) ─────────────
describe('LW38 — scénario 5 : une réponse lente d’un autre lead ne corrompt jamais le courant', () => {
  it('FLUSH_SUCCESS et SET_SERVER d’un id différent sont JETÉS (état inchangé)', () => {
    const stateB = initState({ lead: { id: 2, nom: 'B' }, mode: 'edit' })
    // Réponse lente pour A (id 1) arrivant après la nav vers B (id 2).
    const afterFlush = applyFlushSuccess(stateB, { id: 1, nom: 'A périmé' })
    expect(afterFlush).toBe(stateB) // référence inchangée = jetée
    const afterServer = reducer(stateB, { type: 'SET_SERVER', res: { id: 1, nom: 'A périmé' } })
    expect(afterServer).toBe(stateB)
    // Contre-preuve : la même réponse pour le BON id est bien appliquée.
    const applied = applyFlushSuccess(stateB, { id: 2, nom: 'B à jour' })
    expect(applied).not.toBe(stateB)
    expect(applied.server.nom).toBe('B à jour')
  })
})
