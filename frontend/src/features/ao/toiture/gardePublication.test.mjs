import { test } from 'node:test'
import assert from 'node:assert/strict'
import { repereDepuisIndex } from './repereLettre.js'
import {
  PROVENANCE_MESURE,
  PROVENANCE_MESURE_DOUTEUX,
  PROVENANCE_PLAN,
  PROVENANCE_DEVINE,
  PROVENANCE_DECLARE_CLIENT,
  PROVENANCE_ECARTE,
  PROVENANCE_INCONNUE,
  normaliserProvenance,
  provenanceInfo,
  dansLeCompte,
  estEngageable,
  compterProvenances,
  libelleCompteur,
  obstaclesFautifs,
  nommerFautif,
  questionPourFautifs,
  evaluerGardePublication,
  surfaceObstacle,
  trierObstacles,
  filtrerObstacles,
} from './gardePublication.js'

/* AOF90 — version applicative de l'`assert len(OBS) == 28` du script d'origine :
   le compte engagé, le blocage nominatif, et la question au client pré-remplie. */

function obstacle(i, provenance, extra = {}) {
  return {
    id: `o${i}`,
    repere: repereDepuisIndex(i),
    nature: 'edicule',
    designation: `Édicule ${repereDepuisIndex(i)}`,
    provenance,
    x0: 0,
    x1: 2,
    y0: 0,
    y1: 3,
    ...extra,
  }
}

/** Le relevé réel : 28 dans le compte (26 mesurés + 2 à confirmer) + 2 écartés. */
function releveFrdisi() {
  const obs = []
  for (let i = 0; i < 26; i += 1) obs.push(obstacle(i, 'MESURE'))
  obs.push(obstacle(26, 'MESURE_DOUTEUX'))
  obs.push(obstacle(27, 'MESURE_DOUTEUX'))
  obs.push(obstacle(28, 'ECARTE', { decision: 'Démoli au lot gros œuvre — confirmé par le MOA' }))
  obs.push(obstacle(29, 'ECARTE', { decision: 'Hors emprise PV' }))
  return obs
}

test('les deux vocabulaires de provenance convergent vers les mêmes clés', () => {
  assert.equal(normaliserProvenance('mesure'), PROVENANCE_MESURE)
  assert.equal(normaliserProvenance('MESURE'), PROVENANCE_MESURE)
  assert.equal(normaliserProvenance('confirmer'), PROVENANCE_MESURE_DOUTEUX)
  assert.equal(normaliserProvenance('MESURE_DOUTEUX'), PROVENANCE_MESURE_DOUTEUX)
  // « déduit du plan » de l'inspecteur EST la provenance PLAN du moteur.
  assert.equal(normaliserProvenance('deduit'), PROVENANCE_PLAN)
  assert.equal(normaliserProvenance('plan'), PROVENANCE_PLAN)
  assert.equal(normaliserProvenance('devine'), PROVENANCE_DEVINE)
  assert.equal(normaliserProvenance('DECLARE_CLIENT'), PROVENANCE_DECLARE_CLIENT)
  assert.equal(normaliserProvenance('ecarte'), PROVENANCE_ECARTE)
})

test('une provenance vide ou inconnue ne retombe JAMAIS sur « mesuré »', () => {
  assert.equal(normaliserProvenance(undefined), PROVENANCE_INCONNUE)
  assert.equal(normaliserProvenance(''), PROVENANCE_INCONNUE)
  assert.equal(normaliserProvenance('bidon'), PROVENANCE_INCONNUE)
  assert.equal(estEngageable({ provenance: 'bidon' }), false)
  assert.equal(dansLeCompte({ provenance: 'bidon' }), true)
})

test('engageable : mesuré et à confirmer oui, plan / deviné / déclaré client non', () => {
  assert.equal(estEngageable({ provenance: 'MESURE' }), true)
  assert.equal(estEngageable({ provenance: 'MESURE_DOUTEUX' }), true)
  assert.equal(estEngageable({ provenance: 'PLAN' }), false)
  assert.equal(estEngageable({ provenance: 'DEVINE' }), false)
  assert.equal(estEngageable({ provenance: 'DECLARE_CLIENT' }), false)
})

test("un ÉCARTÉ sort du compte mais garde sa géométrie et sa décision", () => {
  const obs = releveFrdisi()
  const c = compterProvenances(obs)
  assert.equal(c.lignes, 30)
  assert.equal(c.total, 28) // les 2 écartés ne pèsent pas sur le calepinage
  assert.equal(c.parProvenance[PROVENANCE_ECARTE], 2)
  const ecarte = obs.at(-1)
  assert.equal(dansLeCompte(ecarte), false)
  assert.equal(surfaceObstacle(ecarte), 6) // géométrie CONSERVÉE
  assert.equal(ecarte.decision, 'Hors emprise PV')
})

test('le compteur écrit la phrase du relevé, « 0 deviné » compris', () => {
  const obs = releveFrdisi()
  assert.equal(
    libelleCompteur(obs),
    '28 obstacles — 26 mesurés, 2 à confirmer, 0 deviné (+ 2 écartés)',
  )
  assert.equal(
    libelleCompteur(obs.filter((o) => o.provenance !== 'ECARTE')),
    '28 obstacles — 26 mesurés, 2 à confirmer, 0 deviné',
  )
})

test('le relevé complet est publiable : aucun fautif, message affirmatif', () => {
  const garde = evaluerGardePublication(releveFrdisi())
  assert.equal(garde.pretAPublier, true)
  assert.deepEqual(garde.fautifs, [])
  assert.equal(garde.question, null)
  assert.match(garde.message, /publiable/i)
  assert.match(garde.message, /28 obstacles/)
})

test('un obstacle PLAN ou DEVINE bloque la publication et est NOMMÉ', () => {
  const obs = releveFrdisi()
  obs[5] = obstacle(5, 'PLAN', { nature: 'cage_escalier', designation: "Cage d'escalier" })
  obs[9] = obstacle(9, 'DEVINE', { nature: 'cheminee', designation: 'Souche' })

  const garde = evaluerGardePublication(obs)
  assert.equal(garde.pretAPublier, false)
  assert.equal(garde.fautifs.length, 2)
  assert.match(garde.message, /Publication bloquée/)
  // NOMINATIF : repère + désignation + provenance, pour chacun.
  assert.match(garde.message, /F \(Cage d'escalier — relevé sur plan\)/)
  assert.match(garde.message, /J \(Souche — deviné\)/)
  // Le compte total n'a pas bougé : ils pèsent toujours sur le calepinage.
  assert.equal(garde.compte.total, 28)
  assert.equal(garde.compte.engages, 26)
  assert.equal(garde.compte.nonEngageables, 2)
})

test('un obstacle DÉCLARÉ PAR LE CLIENT ou sans provenance bloque aussi', () => {
  const declare = evaluerGardePublication([obstacle(0, 'DECLARE_CLIENT')])
  assert.equal(declare.pretAPublier, false)
  const vide = evaluerGardePublication([obstacle(0, undefined)])
  assert.equal(vide.pretAPublier, false)
  assert.equal(obstaclesFautifs([obstacle(0, undefined)]).length, 1)
})

test('le blocage propose une question au client PRÉ-REMPLIE', () => {
  const fautifs = [
    obstacle(5, 'PLAN', { nature: 'cage_escalier', designation: "Cage d'escalier" }),
    obstacle(9, 'DEVINE', { nature: 'cheminee', designation: 'Souche' }),
  ]
  const q = questionPourFautifs(fautifs)
  assert.deepEqual(q.reperes, ['F', 'J'])
  assert.match(q.objet, /F, J/)
  assert.match(q.corps, /Cage d'escalier/)
  assert.match(q.corps, /Souche/)
  assert.match(q.corps, /confirmer leurs dimensions/i)

  // Un seul fautif : l'objet reste au singulier.
  assert.match(questionPourFautifs([fautifs[0]]).objet, /^Emprise de l'obstacle F/)

  // La garde rend exactement cette question.
  assert.deepEqual(evaluerGardePublication(fautifs).question.reperes, ['F', 'J'])
  assert.equal(nommerFautif(fautifs[0]), "F (Cage d'escalier — relevé sur plan)")
})

test('le tri par repère suit la numérotation de tableur (Z avant AA)', () => {
  const obs = [obstacle(26, 'MESURE'), obstacle(0, 'MESURE'), obstacle(25, 'MESURE')]
  assert.deepEqual(
    trierObstacles(obs, 'repere', 'asc').map((o) => o.repere),
    ['A', 'Z', 'AA'],
  )
  assert.deepEqual(
    trierObstacles(obs, 'repere', 'desc').map((o) => o.repere),
    ['AA', 'Z', 'A'],
  )
})

test('le tri par surface est numérique et stable à égalité', () => {
  const obs = [
    obstacle(0, 'MESURE', { x1: 1, y1: 1 }), // 1 m²
    obstacle(1, 'MESURE'), // 6 m²
    obstacle(2, 'MESURE', { sommets: [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 1 }, { x: 0, y: 1 }] }),
    obstacle(3, 'MESURE', { x1: 1, y1: 1 }), // 1 m² — égalité avec le premier
  ]
  assert.deepEqual(
    trierObstacles(obs, 'surface', 'asc').map((o) => o.repere),
    ['A', 'D', 'B', 'C'],
  )
})

test('le filtre inclut les écartés par défaut et les retrouve par leur décision', () => {
  const obs = releveFrdisi()
  assert.equal(filtrerObstacles(obs).length, 30)
  assert.equal(filtrerObstacles(obs, { inclureEcartes: false }).length, 28)
  assert.equal(filtrerObstacles(obs, { provenance: PROVENANCE_ECARTE }).length, 2)
  const parDecision = filtrerObstacles(obs, { recherche: 'gros œuvre' })
  assert.equal(parDecision.length, 1)
  assert.equal(parDecision[0].provenance, 'ECARTE')
  // Le vocabulaire court de l'inspecteur passe aussi par le filtre.
  assert.equal(filtrerObstacles(obs, { provenance: 'confirmer' }).length, 2)
})

test("provenanceInfo donne le jeton de couleur consommé par l'écran", () => {
  assert.equal(provenanceInfo('MESURE').jeton, 'mesure')
  assert.equal(provenanceInfo('MESURE_DOUTEUX').jeton, 'confirmer')
  assert.equal(provenanceInfo('PLAN').jeton, 'deduit')
  assert.equal(provenanceInfo('DEVINE').jeton, 'devine')
})
