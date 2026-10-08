import { describe, it, expect } from 'vitest'
import { acceptationDejaFaite } from './ventesApi'

// 08/10/2026 — la réponse d'acceptation perdue (timeout) puis re-clic → 409
// « déjà accepté » : c'est un succès (le devis EST accepté), on fête.
describe('acceptationDejaFaite', () => {
  it('409 « déjà accepté » = succès', () => {
    expect(acceptationDejaFaite({ response: { status: 409, data: { detail: 'Ce devis est déjà accepté.' } } })).toBe(true)
  })
  it('autre 409 (devis remplacé) reste une erreur', () => {
    expect(acceptationDejaFaite({ response: { status: 409, data: { detail: 'Cette proposition a été remplacée par DEV-1.' } } })).toBe(false)
  })
  it('timeout / 400 restent des erreurs', () => {
    expect(acceptationDejaFaite({ code: 'ECONNABORTED' })).toBe(false)
    expect(acceptationDejaFaite({ response: { status: 400, data: { detail: 'déjà accepté' } } })).toBe(false)
  })
})
