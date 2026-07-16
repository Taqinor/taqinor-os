import { describe, it, expect } from 'vitest'
import { computeAbComparatif } from './campagneDetail'

describe('computeAbComparatif (NTMKT3)', () => {
  it('répartit les envois en 3 lots (A/B/reste) avec taux corrects', () => {
    const envois = [
      { variante_ab: 'a', statut: 'ouvert' },
      { variante_ab: 'a', statut: 'queued' },
      { variante_ab: 'b', statut: 'clique' },
      { variante_ab: 'b', statut: 'clique' },
      { variante_ab: '', statut: 'envoye' },
    ]
    const result = computeAbComparatif(envois)
    expect(result.a.total).toBe(2)
    expect(result.a.ouverts).toBe(1)
    expect(result.a.taux_ouverture_pct).toBe(50)
    expect(result.b.total).toBe(2)
    expect(result.b.cliques).toBe(2)
    expect(result.b.taux_clic_pct).toBe(100)
    expect(result.reste.total).toBe(1)
  })

  it('renvoie des lots à 0 sans division par zéro pour un tableau vide', () => {
    const result = computeAbComparatif([])
    expect(result.a).toEqual({
      total: 0, ouverts: 0, cliques: 0, taux_ouverture_pct: 0, taux_clic_pct: 0,
    })
    expect(result.b.total).toBe(0)
    expect(result.reste.total).toBe(0)
  })

  it('accepte null/undefined en entrée', () => {
    expect(computeAbComparatif(null).a.total).toBe(0)
    expect(computeAbComparatif(undefined).reste.total).toBe(0)
  })

  it('un envoi ouvert_le sans statut ouvert compte quand même comme ouvert', () => {
    const envois = [{ variante_ab: 'a', statut: 'envoye', ouvert_le: '2026-07-10T00:00:00Z' }]
    const result = computeAbComparatif(envois)
    expect(result.a.ouverts).toBe(1)
  })
})
