import { describe, it, expect } from 'vitest'
import {
  soldeRestant, estEnAttenteSolde, marchandiseBloquee, arrhesValides,
  libelleEtatArrhes,
} from './arrhes'

/* NTRET5 — tests de la logique PURE arrhes/solde (calculs écran caisse). */

describe('soldeRestant', () => {
  it('calcule le solde restant = total - arrhes', () => {
    expect(soldeRestant({ total_ttc: '500', montant_arrhes: '150' })).toBe(350)
  })

  it('renvoie 0 quand aucune arrhe n’a été encaissée', () => {
    expect(soldeRestant({ total_ttc: '500', montant_arrhes: null })).toBe(0)
  })
})

describe('estEnAttenteSolde', () => {
  it('vrai uniquement pour le statut en_attente_solde', () => {
    expect(estEnAttenteSolde({ statut: 'en_attente_solde' })).toBe(true)
    expect(estEnAttenteSolde({ statut: 'validee' })).toBe(false)
    expect(estEnAttenteSolde({ statut: 'brouillon' })).toBe(false)
    expect(estEnAttenteSolde(null)).toBe(false)
  })
})

describe('marchandiseBloquee', () => {
  it('bloquée tant que en attente de solde ET marchandise_remise est faux', () => {
    expect(marchandiseBloquee({
      statut: 'en_attente_solde', marchandise_remise: false,
    })).toBe(true)
  })

  it('débloquée une fois marchandise_remise vrai (solde réglé ou override)', () => {
    expect(marchandiseBloquee({
      statut: 'en_attente_solde', marchandise_remise: true,
    })).toBe(false)
  })

  it('jamais bloquée hors du statut en_attente_solde', () => {
    expect(marchandiseBloquee({
      statut: 'validee', marchandise_remise: false,
    })).toBe(false)
  })
})

describe('arrhesValides', () => {
  it('accepte un montant positif strictement inférieur au total', () => {
    expect(arrhesValides(500, 150)).toBe(true)
  })

  it('refuse un montant nul, négatif, ou >= au total', () => {
    expect(arrhesValides(500, 0)).toBe(false)
    expect(arrhesValides(500, -10)).toBe(false)
    expect(arrhesValides(500, 500)).toBe(false)
    expect(arrhesValides(500, 600)).toBe(false)
  })
})

describe('libelleEtatArrhes', () => {
  it('null hors attente de solde', () => {
    expect(libelleEtatArrhes({ statut: 'validee' })).toBeNull()
  })

  it('mentionne le solde restant tant que la marchandise n’est pas remise', () => {
    const libelle = libelleEtatArrhes({
      statut: 'en_attente_solde', total_ttc: '500', montant_arrhes: '150',
      marchandise_remise: false,
    })
    expect(libelle).toMatch(/350\.00 DH restant/)
  })

  it('mentionne la remise déjà faite quand marchandise_remise est vrai', () => {
    const libelle = libelleEtatArrhes({
      statut: 'en_attente_solde', total_ttc: '500', montant_arrhes: '150',
      marchandise_remise: true,
    })
    expect(libelle).toMatch(/Marchandise remise/)
  })
})
