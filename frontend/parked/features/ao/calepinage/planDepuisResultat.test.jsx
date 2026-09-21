import { describe, it, expect } from 'vitest'
import planDepuisResultat from './planDepuisResultat'
import resultatReel from './resultatReel.fixture'

/* L'adaptateur de RENDU : il traduit les coins de rectangle que le serveur
   publie (`plans[].tables[{x0,x1,y0,y1}]`) en rectangles SVG, et RIEN d'autre.
   La charge utile de référence est capturée du moteur (voir la fixture). */

describe('planDepuisResultat — traduction de rendu, jamais de calcul métier', () => {
  it('pose une table par entrée serveur, aux coordonnées SERVEUR', () => {
    const plan = planDepuisResultat(resultatReel)
    const [groupe] = plan.rangees
    expect(plan.rangees).toHaveLength(1)          // un groupe par SURFACE
    expect(groupe.id).toBe('05H')
    expect(groupe.tables).toHaveLength(resultatReel.plans[0].tables.length)

    const premiere = groupe.tables[0]
    const source = resultatReel.plans[0].tables[0]
    expect(premiere.x).toBe(source.x0)
    expect(premiere.y).toBe(source.y0)
    expect(premiere.largeur_m).toBeCloseTo(source.x1 - source.x0, 6)
    expect(premiere.hauteur_m).toBeCloseTo(source.y1 - source.y0, 6)
    expect(premiere.kit).toBe(source.kit)
  })

  it('AUCUN axe n’est renversé : le y du serveur est le y du dessin', () => {
    const plan = planDepuisResultat(resultatReel)
    const ys = plan.rangees[0].tables.map((table) => table.y)
    expect(Math.min(...ys)).toBe(0.8003)
    expect(plan.cadre.y_min).toBe(0.8003)
  })

  it('le cadre est la FENÊTRE qui contient les tables posées', () => {
    const plan = planDepuisResultat(resultatReel)
    expect(plan.cadre.x_min).toBe(0.35)
    expect(plan.cadre.largeur_m).toBeCloseTo(7.154 - 0.35, 6)
    expect(plan.cadre.hauteur_m).toBeCloseTo(11.65 - 0.8003, 6)
  })

  it('ne fabrique AUCUNE couche que le serveur ne publie pas', () => {
    const plan = planDepuisResultat(resultatReel)
    for (const couche of ['allees', 'rives', 'degagements', 'obstacles', 'zones', 'legende']) {
      expect(plan[couche]).toBeUndefined()
    }
    expect(plan.rangees[0].tables[0].faitage).toBeUndefined()
  })

  it('rend null quand rien n’est posé (jamais un plan vide qui a l’air valide)', () => {
    expect(planDepuisResultat(null)).toBeNull()
    expect(planDepuisResultat({})).toBeNull()
    expect(planDepuisResultat({ plans: [{ surface: 'X', tables: [] }] })).toBeNull()
  })
})
