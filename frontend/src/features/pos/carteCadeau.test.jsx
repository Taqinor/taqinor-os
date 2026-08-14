import { describe, it, expect } from 'vitest'
import {
  MODE_CARTE_CADEAU, paiementCarteCadeau, paiementCarteCadeauValide,
  libelleSoldeCarteCadeau,
} from './carteCadeau'

/* NTRET15 — tests de la logique PURE carte cadeau (écran caisse). */

describe('paiementCarteCadeau', () => {
  it('construit un paiement avec le mode carte_cadeau et le code normalisé', () => {
    const p = paiementCarteCadeau('abc-123', '150')
    expect(p).toEqual({ mode: MODE_CARTE_CADEAU, montant: '150', carte_code: 'ABC-123' })
  })

  it('trim + majuscule le code saisi', () => {
    const p = paiementCarteCadeau('  xyz999  ', 50)
    expect(p.carte_code).toBe('XYZ999')
  })
})

describe('paiementCarteCadeauValide', () => {
  it('valide un code non vide et un montant positif', () => {
    expect(paiementCarteCadeauValide('ABC123', '100')).toBe(true)
  })

  it('refuse un code vide', () => {
    expect(paiementCarteCadeauValide('', '100')).toBe(false)
    expect(paiementCarteCadeauValide('   ', '100')).toBe(false)
  })

  it('refuse un montant nul, négatif ou non numérique', () => {
    expect(paiementCarteCadeauValide('ABC123', '0')).toBe(false)
    expect(paiementCarteCadeauValide('ABC123', '-10')).toBe(false)
    expect(paiementCarteCadeauValide('ABC123', 'abc')).toBe(false)
  })
})

describe('libelleSoldeCarteCadeau', () => {
  it('formate le libellé avec le solde', () => {
    expect(libelleSoldeCarteCadeau({ code: 'ABC123', solde: '42.5' }))
      .toBe('Carte ABC123 — solde disponible : 42.50 DH')
  })

  it('renvoie une chaîne vide sans code', () => {
    expect(libelleSoldeCarteCadeau()).toBe('')
    expect(libelleSoldeCarteCadeau({ solde: '10' })).toBe('')
  })
})
