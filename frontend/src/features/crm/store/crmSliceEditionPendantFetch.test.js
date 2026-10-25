import { describe, it, expect, vi, beforeEach } from 'vitest'
import { configureStore } from '@reduxjs/toolkit'
import reducer, {
  fetchLeads, updateLead, createLead, leadsChunkReceived,
} from './crmSlice'
import crmApi from '../../../api/crmApi'
import { NEW_STAGE, CONTACTED_STAGE } from '../stages'

/* ALEA21 — `crmSlice` fusionne les pages de `fetchLeads` sans écraser un lead
   modifié localement APRÈS le départ du fetch. Réducteur RÉEL, séquence
   d'actions horodatées (les créateurs d'actions de RTK), on lit l'état produit.
   (Nommé .test.js : un .test.mjs n'est exécuté que par node:test, qui ne sait
   pas résoudre les imports sans extension du slice.) */

// LB7 / PERF-CRM — seul le transport réseau est simulé ; le thunk, la
// pagination parallèle (`fetchAllPages`) et le réducteur sont les VRAIS.
vi.mock('../../../api/crmApi', () => ({ default: { getLeads: vi.fn() } }))

const lead = (id, stage = NEW_STAGE) => ({ id, nom: `L${id}`, stage })

function etatInitial() {
  return reducer(undefined, { type: '@@init' })
}

describe('ALEA21 — édition pendant un fetch de liste', () => {
  it('un déplacement d’étape fait pendant le chargement reste affiché', () => {
    let st = etatInitial()
    // t0 : le fetch part (la liste locale a déjà X en NEW)
    st = reducer(st, fetchLeads.pending('fetch-1', {}))
    st = reducer(st, leadsChunkReceived({
      requestId: 'fetch-1', results: [lead(1), lead(2)], first: true,
    }))
    // t1 > t0 : updateLead de X (stage NEW -> CONTACTED) réussit
    st = reducer(st, updateLead.pending('upd-1', { id: 1, data: { stage: CONTACTED_STAGE } }))
    st = reducer(st, updateLead.fulfilled(lead(1, CONTACTED_STAGE), 'upd-1', { id: 1, data: {} }))
    expect(st.leads.find((l) => l.id === 1).stage).toBe(CONTACTED_STAGE)
    // la page suivante puis le fulfilled arrivent avec X encore en NEW
    st = reducer(st, leadsChunkReceived({
      requestId: 'fetch-1', results: [lead(3)], first: false,
    }))
    st = reducer(st, fetchLeads.fulfilled(
      { results: [lead(1), lead(2), lead(3)] }, 'fetch-1', {},
    ))
    expect(st.leads.find((l) => l.id === 1).stage).toBe(CONTACTED_STAGE)
    // les autres leads sont remplacés par la réponse
    expect(st.leads.map((l) => l.id).sort()).toEqual([1, 2, 3])
    expect(st.leads.find((l) => l.id === 2).stage).toBe(NEW_STAGE)
  })

  it('la première page elle-même (leadsChunkReceived) ne ramène pas X en NEW', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('fetch-2', {}))
    st = reducer(st, updateLead.pending('upd-2', { id: 1, data: {} }))
    st = reducer(st, updateLead.fulfilled(lead(1, CONTACTED_STAGE), 'upd-2', { id: 1, data: {} }))
    st = reducer(st, leadsChunkReceived({
      requestId: 'fetch-2', results: [lead(1), lead(2)], first: true,
    }))
    expect(st.leads.find((l) => l.id === 1).stage).toBe(CONTACTED_STAGE)
  })

  it('un lead créé pendant le fetch n’apparaît pas en double', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('fetch-3', {}))
    st = reducer(st, leadsChunkReceived({
      requestId: 'fetch-3', results: [lead(1)], first: true,
    }))
    st = reducer(st, createLead.fulfilled(lead(9), 'crea-1', {}))
    // le serveur renvoie 9 dans la liste finale : une seule occurrence
    st = reducer(st, fetchLeads.fulfilled(
      { results: [lead(1), lead(9)] }, 'fetch-3', {},
    ))
    expect(st.leads.filter((l) => l.id === 9)).toHaveLength(1)
    // et s’il n’y figure pas (fetch parti avant la création), il est conservé
    let st2 = etatInitial()
    st2 = reducer(st2, fetchLeads.pending('fetch-4', {}))
    st2 = reducer(st2, createLead.fulfilled(lead(9), 'crea-2', {}))
    st2 = reducer(st2, fetchLeads.fulfilled({ results: [lead(1)] }, 'fetch-4', {}))
    expect(st2.leads.map((l) => l.id).sort()).toEqual([1, 9])
  })

  it('après le fetch, une édition ultérieure suit le chemin habituel (plus d’overlay)', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('fetch-5', {}))
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(1)] }, 'fetch-5', {}))
    expect(st.fetchLeadsInFlight).toBe(false)
    st = reducer(st, updateLead.pending('upd-5', { id: 1, data: {} }))
    st = reducer(st, updateLead.fulfilled(lead(1, CONTACTED_STAGE), 'upd-5', { id: 1, data: {} }))
    expect(st.leads[0].stage).toBe(CONTACTED_STAGE)
    expect(st.leadsEditedDuringFetch).toEqual({})
  })
})

/* LB7 — garde d'obsolescence de `fetchLeads` (bug recon2-03 #10) : un
   `fulfilled` dont le requestId n'est plus celui du DERNIER fetch dispatché est
   ignoré (même motif que `leadUpdateSeq` pour `updateLead`). Réducteur réel,
   séquences d'actions dans l'ordre inverse de leur départ. */
describe('LB7 — fetchLeads : un résultat périmé n’écrase jamais le plus récent', () => {
  it('l’état initial n’a encore aucun fetch en référence', () => {
    expect(etatInitial().fetchLeadsRequestId).toBeNull()
  })

  it('chaque fetch dispatché devient la référence (le dernier départ gagne)', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    expect(st.fetchLeadsRequestId).toBe('req-1')
    st = reducer(st, fetchLeads.pending('req-2', {}))
    expect(st.fetchLeadsRequestId).toBe('req-2')
  })

  it('un fulfilled OBSOLÈTE (réponse lente d’un fetch ancien) est ignoré', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    st = reducer(st, fetchLeads.pending('req-2', {}))
    // Le fetch 2 (le plus récent) répond d’abord, puis le fetch 1, plus lent.
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(2)] }, 'req-2', {}))
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(1)] }, 'req-1', {}))
    expect(st.leads.map((l) => l.id)).toEqual([2])
  })

  it('le périmé arrivé EN PREMIER n’écrit rien non plus ; le courant s’applique ensuite', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    st = reducer(st, fetchLeads.pending('req-2', {}))
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(1)] }, 'req-1', {}))
    expect(st.leads).toEqual([])
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(2)] }, 'req-2', {}))
    expect(st.leads.map((l) => l.id)).toEqual([2])
  })

  it('même garde que leadUpdateSeq : deux PATCH du même lead, réponses inversées', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    st = reducer(st, fetchLeads.fulfilled({ results: [lead(1)] }, 'req-1', {}))
    st = reducer(st, updateLead.pending('upd-a', { id: 1, data: {} }))
    st = reducer(st, updateLead.pending('upd-b', { id: 1, data: {} }))
    st = reducer(st, updateLead.fulfilled(lead(1, CONTACTED_STAGE), 'upd-b', { id: 1, data: {} }))
    st = reducer(st, updateLead.fulfilled(lead(1, NEW_STAGE), 'upd-a', { id: 1, data: {} }))
    expect(st.leads[0].stage).toBe(CONTACTED_STAGE)
  })
})

/* PERF-CRM (mesuré à 930 leads en prod) — flux PROGRESSIF de `fetchLeads` : la
   1re page s'affiche dès son arrivée, pages de 200 (plafond serveur), 3 pages
   en parallèle au plus (2 vCPU de prod). Thunk RÉEL dans un store RÉEL. */
describe('PERF-CRM — fetchLeads : flux progressif, pages de 200, 3 en parallèle', () => {
  const nouveauStore = () => configureStore({ reducer: { crm: reducer } })
  const page = (n) => ({ data: { count: 16, results: [lead(n * 10 + 1), lead(n * 10 + 2)] } })
  const attendre = (ms) => new Promise((resolve) => { setTimeout(resolve, ms) })

  beforeEach(() => { vi.clearAllMocks() })

  it('demande des pages de 200, 3 à la fois au plus, jusqu’à la dernière page', async () => {
    let enVol = 0
    let maxEnVol = 0
    crmApi.getLeads.mockImplementation(async (params) => {
      enVol += 1
      maxEnVol = Math.max(maxEnVol, enVol)
      await attendre(5)
      enVol -= 1
      return page(params.page)
    })
    const store = nouveauStore()
    await store.dispatch(fetchLeads({}))
    const appels = crmApi.getLeads.mock.calls.map(([params]) => params)
    expect(appels.every((p) => p.page_size === 200)).toBe(true)
    expect(appels.map((p) => p.page).sort((a, b) => a - b)).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
    expect(maxEnVol).toBe(3)
    expect(store.getState().crm.leads).toHaveLength(16)
  })

  it('la 1re page est affichée (squelette levé) AVANT l’arrivée des suivantes', async () => {
    let liberer
    const suite = new Promise((resolve) => { liberer = resolve })
    crmApi.getLeads.mockImplementation(async (params) => {
      if (params.page === 1) return page(1)
      await suite
      return page(params.page)
    })
    const store = nouveauStore()
    const fin = store.dispatch(fetchLeads({}))
    await vi.waitFor(() => {
      expect(store.getState().crm.leads.map((l) => l.id)).toEqual([11, 12])
    })
    const enCours = store.getState().crm
    expect(enCours.leadsLoading).toBe(false)
    expect(enCours.fetchLeadsInFlight).toBe(true)
    liberer()
    await fin
    const ids = store.getState().crm.leads.map((l) => l.id)
    expect(ids).toHaveLength(16)
    expect(ids.slice(0, 2)).toEqual([11, 12])
    expect(store.getState().crm.fetchLeadsInFlight).toBe(false)
  })

  it('une page d’un fetch PÉRIMÉ (autre requestId) n’est pas affichée', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    st = reducer(st, fetchLeads.pending('req-2', {}))
    st = reducer(st, leadsChunkReceived({ requestId: 'req-1', results: [lead(1)], first: true }))
    expect(st.leads).toEqual([])
    expect(st.leadsLoading).toBe(true)
    st = reducer(st, leadsChunkReceived({ requestId: 'req-2', results: [lead(2)], first: true }))
    expect(st.leads.map((l) => l.id)).toEqual([2])
    expect(st.leadsLoading).toBe(false)
  })

  it('1re page = remplace et lève le squelette ; suivantes = ajout DÉDUPLIQUÉ par id', () => {
    let st = etatInitial()
    st = reducer(st, fetchLeads.pending('req-1', {}))
    expect(st.leadsLoading).toBe(true)
    st = reducer(st, leadsChunkReceived({ requestId: 'req-1', results: [lead(1), lead(2)], first: true }))
    expect(st.leadsLoading).toBe(false)
    st = reducer(st, leadsChunkReceived({ requestId: 'req-1', results: [lead(2), lead(3)], first: false }))
    expect(st.leads.map((l) => l.id)).toEqual([1, 2, 3])
  })
})
