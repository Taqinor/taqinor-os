import { describe, it, expect } from 'vitest'
import reducer, {
  saveProfile, uploadLogo, deleteLogo,
} from './parametresSlice'

/* APAR42 — après un enregistrement refusé puis un enregistrement valide,
   l'ancienne erreur ne revient plus (le bandeau rouge `{error && !saved}` se
   rallumait 3 s après « Profil enregistré »). */

const ERREUR = { tva_standard: ['Requis'] }

describe('APAR42 — erreur du profil acquittée', () => {
  it('échec puis succès : error remise à null', () => {
    let state = reducer(undefined, { type: '@@init' })
    state = reducer(state, { type: saveProfile.rejected.type, payload: ERREUR })
    expect(state.error).toEqual(ERREUR)
    state = reducer(state, { type: saveProfile.pending.type })
    expect(state.error).toBeNull()
    state = reducer(state, { type: saveProfile.rejected.type, payload: ERREUR })
    state = reducer(state, { type: saveProfile.fulfilled.type, payload: { id: 1 } })
    expect(state.error).toBeNull()
    expect(state.saveSuccess).toBe(true)
  })

  it('upload / suppression du logo acquittent aussi l’erreur', () => {
    let state = reducer(undefined, { type: '@@init' })
    state = reducer(state, { type: uploadLogo.rejected.type, payload: 'Trop lourd' })
    state = reducer(state, { type: uploadLogo.fulfilled.type, payload: { id: 1 } })
    expect(state.error).toBeNull()
    state = reducer(state, { type: saveProfile.rejected.type, payload: ERREUR })
    state = reducer(state, { type: deleteLogo.fulfilled.type, payload: { id: 1 } })
    expect(state.error).toBeNull()
  })
})
