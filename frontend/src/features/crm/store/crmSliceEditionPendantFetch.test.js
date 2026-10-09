import { describe, it, expect } from 'vitest'
import reducer, {
  fetchLeads, updateLead, createLead, leadsChunkReceived,
} from './crmSlice'
import { NEW_STAGE, CONTACTED_STAGE } from '../stages'

/* ALEA21 — `crmSlice` fusionne les pages de `fetchLeads` sans écraser un lead
   modifié localement APRÈS le départ du fetch. Réducteur RÉEL, séquence
   d'actions horodatées (les créateurs d'actions de RTK), on lit l'état produit.
   (Nommé .test.js : un .test.mjs n'est exécuté que par node:test, qui ne sait
   pas résoudre les imports sans extension du slice.) */

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
