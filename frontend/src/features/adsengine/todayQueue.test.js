import { describe, it, expect } from 'vitest'
import { normalizeTodayQueue, categoryTone } from './todayQueue'

/* PUB42 — file « Aujourd'hui » unifiée : logique pure. */

describe('normalizeTodayQueue', () => {
  it('normalise une réponse {items, total}', () => {
    const q = normalizeTodayQueue({
      items: [
        { id: 'garde_fou-1', categorie: 'garde_fou', categorie_label: 'Garde-fou',
          titre: 'Violation', detail: 'Plafond dépassé', lien: '/publicite/tableau-de-bord',
          quand: '2026-07-19T08:00:00Z' },
      ],
      total: 1,
    })
    expect(q.items).toHaveLength(1)
    expect(q.total).toBe(1)
    expect(q.items[0].categorie).toBe('garde_fou')
  })

  it('accepte un tableau brut (repli)', () => {
    const q = normalizeTodayQueue([{ id: 1, categorie: 'digest' }])
    expect(q.items).toHaveLength(1)
    expect(q.total).toBe(1)
  })

  it('réponse absente/malformée -> liste vide, jamais une erreur', () => {
    expect(normalizeTodayQueue(null)).toEqual({ items: [], total: 0 })
    expect(normalizeTodayQueue(undefined)).toEqual({ items: [], total: 0 })
    expect(normalizeTodayQueue({})).toEqual({ items: [], total: 0 })
  })

  it('filtre les entrées vides et ne retrie JAMAIS (ordre backend préservé)', () => {
    const q = normalizeTodayQueue({
      items: [
        { id: 1, categorie: 'commentaire' },
        null,
        { id: 2, categorie: 'garde_fou' },
      ],
    })
    expect(q.items.map(it => it.categorie)).toEqual(['commentaire', 'garde_fou'])
  })

  it('repli sur des valeurs par défaut sûres', () => {
    const q = normalizeTodayQueue({ items: [{}] })
    expect(q.items[0]).toMatchObject({
      categorie: 'digest', titre: '—', detail: '', lien: '',
    })
  })
})

describe('categoryTone', () => {
  it('retourne un ton par catégorie connue', () => {
    expect(categoryTone('garde_fou').color).toBeTruthy()
    expect(categoryTone('digest').color).toBeTruthy()
  })
  it('catégorie inconnue -> ton neutre (jamais une erreur)', () => {
    expect(categoryTone('nope')).toEqual({ bg: '#f1f5f9', color: '#475569' })
  })
})
