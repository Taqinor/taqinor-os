import { describe, it, expect } from 'vitest'
import { messageRefus, refusServeur } from './refusServeur'

/* ACAL279 — les formes RÉELLES de core/exceptions.taqinor_exception_handler. */
const enveloppe = (code, message, fields = {}) => ({ code, message, fields, request_id: 'r-1' })
const refus = (data, status = 400) => ({ response: { status, data } })

describe('refusServeur — formes du handler', () => {
  it('400 {approbation:[…], error:{…}} : le motif du champ, `error` jamais un champ', () => {
    const r = refusServeur(refus({
      approbation: ['Approbation exigée avant de retenir cette variante.'],
      error: enveloppe('validation_error', 'Requête invalide.', { approbation: ['…'] }),
    }))
    expect(r.message).toBe('Approbation exigée avant de retenir cette variante.')
    expect(r.champs).toEqual({ approbation: 'Approbation exigée avant de retenir cette variante.' })
    expect('error' in r.champs).toBe(false)
  })

  it('403/404 {detail, error} : detail, aucun champ', () => {
    const r = refusServeur(refus({ detail: 'Vous n’avez pas la permission.', error: enveloppe('permission_denied', 'x') }, 403))
    expect(r).toEqual({ message: 'Vous n’avez pas la permission.', champs: {} })
  })

  it('409 {roof_layout:[…]} et 400 {releve_le:"…"} : texte et chaîne simple', () => {
    expect(refusServeur(refus({ roof_layout: ['Ce calepinage est verrouillé.'] }, 409)).message)
      .toBe('Ce calepinage est verrouillé.')
    const r = refusServeur(refus({ releve_le: 'La date du relevé est obligatoire.' }))
    expect(r.champs.releve_le).toBe('La date du relevé est obligatoire.')
  })

  it('seule l’enveloppe : error.message ; rien du tout : message vide, repli de l’appelant', () => {
    expect(refusServeur(refus({ error: enveloppe('x', 'Erreur serveur.') })).message).toBe('Erreur serveur.')
    expect(refusServeur(new Error('réseau'))).toEqual({ message: '', champs: {} })
    expect(messageRefus(new Error('réseau'), 'Impossible.')).toBe('Impossible.')
  })
})
