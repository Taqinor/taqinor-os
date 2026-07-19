import { describe, it, expect } from 'vitest'
import { normalizeAdFullStory } from './adFullStory'

/* PUB44 — fiche « histoire complète » d'une ad : logique pure. */

describe('normalizeAdFullStory', () => {
  it('normalise une réponse complète', () => {
    const s = normalizeAdFullStory({
      ad: { id: 1, meta_id: 'ad-1', nom: 'Reel toiture', statut: 'ACTIVE', statut_display: 'Active' },
      creatif: { title: 'Toiture' },
      metriques: { depense_mad: '30.00' },
      actions: [{ id: 1 }],
      commentaires: [{ id: 1 }],
      regles: [{ id: 1 }],
      experiences: [{ id: 1 }],
      breakdowns: [{ id: 1 }],
    })
    expect(s.ad.meta_id).toBe('ad-1')
    expect(s.creatif.title).toBe('Toiture')
    expect(s.metriques.depense_mad).toBe('30.00')
    expect(s.actions).toHaveLength(1)
    expect(s.commentaires).toHaveLength(1)
    expect(s.regles).toHaveLength(1)
    expect(s.experiences).toHaveLength(1)
    expect(s.breakdowns).toHaveLength(1)
  })

  it('réponse absente/malformée -> repli sûr, listes vides (jamais une erreur)', () => {
    for (const raw of [null, undefined, {}]) {
      const s = normalizeAdFullStory(raw)
      expect(s.ad.nom).toBe('—')
      expect(s.creatif).toBeNull()
      expect(s.metriques).toBeNull()
      expect(s.actions).toEqual([])
      expect(s.commentaires).toEqual([])
      expect(s.regles).toEqual([])
      expect(s.experiences).toEqual([])
      expect(s.breakdowns).toEqual([])
    }
  })

  it('filtre les entrées vides des listes', () => {
    const s = normalizeAdFullStory({ actions: [null, { id: 1 }, undefined] })
    expect(s.actions).toHaveLength(1)
  })
})
