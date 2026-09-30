import { describe, it, expect } from 'vitest'
import { frError } from './TicketsPage'

describe('frError — ERR-QAH-SAV-ERREUR-OBJECT-OBJECT', () => {
  it("n'affiche jamais l'enveloppe error comme [object Object]", () => {
    const err = { response: { data: {
      cout: ['Un nombre valide est requis.'],
      error: { code: 'validation_error', message: 'x' },
    } } }
    const msg = frError(err, 'Échec de la mise à jour.')
    expect(msg).toBe('Échec : Coût — Un nombre valide est requis.')
    expect(msg).not.toMatch(/object/i)
  })
  it("retombe sur le message par défaut si seule l'enveloppe est présente", () => {
    const err = { response: { data: { error: { code: 'x' } } } }
    expect(frError(err, 'Échec.')).toBe('Échec.')
  })
})
