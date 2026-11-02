import { describe, it, expect } from 'vitest'
import { fusionnerLignes } from './fusionSuivi'

/* La fusion du « Suivi des relances », en FONCTION PURE : c'est elle qui tient
   la promesse « les compteurs restent ceux du serveur » sans relire la
   période. Testée sans écran (aucun rendu à dérouler pour une règle de
   calcul). */
describe('fusionnerLignes (SUIVI-RELOAD)', () => {
  const BORNES = { date_debut: '2026-09-01', date_fin: '2026-09-30' }
  const TODAY = '2026-09-15'
  const ligne = (p) => ({ due_at: null, ordre: 1, statut: 'a_faire', ...p })
  const donnees = (results, resume) => ({ count: results.length, results, resume })

  it('une touche faite quitte « à faire » (et « en retard ») et entre dans « faites »', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 4, en_retard: 2, fait: 1, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10', statut: 'fait' })],
      BORNES, TODAY,
    )
    // La ligne était ouverte et échue (10/09 < 15/09) : les deux seaux baissent.
    expect(apres.resume).toEqual({ a_faire: 3, en_retard: 1, fait: 2, sautee: 0, annulee: 0 })
    expect(apres.results.map((e) => e.statut)).toEqual(['fait'])
    // Jamais de doublon d'id, et le compte suit la liste.
    expect(apres.count).toBe(1)
  })

  it('une touche reportée HORS de la fenêtre servie quitte la liste ET les compteurs', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 1, en_retard: 1, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [ligne({ id: 1, lead: 7, due_date: '2026-10-20' })],
      BORNES, TODAY,
    )
    expect(apres.results).toEqual([])
    expect(apres.resume).toEqual({ a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 })
  })

  it('une touche qui NAÎT se range à sa place (jour, puis heure NULLS LAST, puis ordre)', () => {
    const avant = donnees(
      [
        ligne({ id: 1, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T08:00:00Z' }),
        ligne({ id: 2, lead: 9, due_date: '2026-09-12' }),
      ],
      { a_faire: 2, en_retard: 2, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(
      avant, new Set([1]),
      [
        ligne({ id: 1, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T08:00:00Z', statut: 'fait' }),
        ligne({ id: 3, lead: 7, due_date: '2026-09-10', due_at: '2026-09-10T07:00:00Z' }),
      ],
      BORNES, TODAY,
    )
    // 3 (07:00) avant 1 (08:00), tous deux avant la journée du 12.
    expect(apres.results.map((e) => e.id)).toEqual([3, 1, 2])
    expect(apres.resume).toEqual({ a_faire: 2, en_retard: 2, fait: 1, sautee: 0, annulee: 0 })
  })

  it('un compteur ne descend jamais sous zéro, et une liste absente est rendue telle quelle', () => {
    const avant = donnees(
      [ligne({ id: 1, lead: 7, due_date: '2026-09-10' })],
      { a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 },
    )
    const apres = fusionnerLignes(avant, new Set([1]), [], BORNES, TODAY)
    expect(apres.resume.a_faire).toBe(0)
    expect(fusionnerLignes(null, new Set([1]), [], BORNES, TODAY)).toBeNull()
  })
})
