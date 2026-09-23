/* CALX267 — le contrat PARTAGÉ des groupes de batteries, côté écran.

   `backend/django_core/apps/calepinage/contract_samples/calepinage_batterie.json`
   est le résultat RÉEL de `services/batterie.py::simuler_groupes` sur une
   entrée synthétique : le test backend
   (`apps/calepinage/tests/test_calx267_groupes_batteries.py`) le rejoue et
   affirme l'égalité. Ce test-ci l'IMPORTE (PACT10/PACT13 — jamais une charge
   tapée à la main) et fige ce qu'un écran pourra lire sans rien recalculer :
   chaque groupe SÉPARÉMENT avec son couplage, puis l'agrégat, et la mention
   d'approximation quand deux modèles de batterie coexistent. */
import { describe, it, expect } from 'vitest'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

const exemple = () => exempleContrat('calepinage', 'calepinage_batterie')

describe('contrat calepinage_batterie (CALX267)', () => {
  it('publie chaque groupe séparément, chacun avec son couplage déclaré', () => {
    const { groupes } = exemple()
    expect(groupes.length).toBeGreaterThan(1)
    groupes.forEach((groupe) => {
      expect(['ac', 'dc']).toContain(groupe.couplage)
      expect(typeof groupe.groupe).toBe('string')
      expect(groupe.resultat).toBeTruthy()
      // Un groupe couplé côté CONTINU nomme toujours son onduleur hybride.
      if (groupe.couplage === 'dc') expect(groupe.onduleur_ref).toBeTruthy()
    })
  })

  it("l'agrégat porte les mêmes clés que le résultat d'un groupe", () => {
    const { groupes, agregat } = exemple()
    expect(Object.keys(agregat).sort()).toEqual(Object.keys(groupes[0].resultat).sort())
  })

  it('la décharge agrégée est la somme des groupes (au 0,001 kWh près)', () => {
    const { groupes, agregat } = exemple()
    const somme = groupes.reduce((total, g) => total + g.resultat.decharge_batterie_kwh, 0)
    expect(Math.abs(somme - agregat.decharge_batterie_kwh)).toBeLessThanOrEqual(0.001)
  })

  it('deux modèles différents : la mention « agrégat de capacités — approximation »', () => {
    const { groupes, mention_agregat: mention } = exemple()
    const modeles = new Set(groupes.map((g) => g.modele))
    expect(modeles.size).toBeGreaterThan(1)
    expect(mention).toContain('agrégat de capacités — approximation')
  })

  it('aucune clé de prix, de coût ni de marge', () => {
    const texte = JSON.stringify(documentContrat('calepinage', 'calepinage_batterie').exemple)
      .toLowerCase()
    ;['prix', 'cout', 'marge'].forEach((mot) => expect(texte).not.toContain(mot))
  })
})
