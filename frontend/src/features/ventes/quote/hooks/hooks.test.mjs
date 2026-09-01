// QJR90 — tests des trois hooks, par leur moitié PURE (patron maison
// `etudeHorairePreview.js` / `etudeHorairePreviewPur.js`). `node --test`
// uniquement : les fichiers `use*.js` importent React et l'API, ils ne sont
// pas exécutables ici — toute la logique testable vit dans les `*Pur.js`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { decisionSizing, motifRefus, REFUS_GENERIQUE } from './useSizingMoteurPur.js'
import {
  resoudreComposition, raisonRepli, RAISON_SERVEUR, RAISON_RIEN,
} from './useCompositionPur.js'

// ── useSizingMoteur : la garde de péremption sur les DEUX branches ───────────

const CLE = '{"kwc":8.52}'
const ANCIENNE = '{"kwc":5}'
const RECO = { dimensionnement: { recommandation: { panneaux: 21, kwc: 14.91 } } }

test('hors attente, la décision ne touche à RIEN', () => {
  assert.deepEqual(decisionSizing({ attente: false, donnees: RECO }), { action: 'rien' })
  assert.deepEqual(decisionSizing(), { action: 'rien' })
})

test('une frappe manuelle gagne toujours : l’attente se referme sans rien poser', () => {
  const d = decisionSizing({ attente: true, toucheNbPanneaux: true, donnees: RECO,
    cleServie: CLE, cleCourante: CLE })
  assert.equal(d.action, 'abandonner')
})

test('réponse EN VOL : on attend, on ne décide rien', () => {
  assert.equal(decisionSizing({ attente: true, chargement: true }).action, 'attendre')
})

test('SUCCÈS FRAIS : la recommandation serveur est appliquée', () => {
  const d = decisionSizing({ attente: true, donnees: RECO, cleServie: CLE, cleCourante: CLE })
  assert.equal(d.action, 'appliquer')
  assert.deepEqual(d.recommandation, { panneaux: 21, kwc: 14.91 })
})

test('SUCCÈS PÉRIMÉ : le drapeau reste OUVERT, rien n’est appliqué', () => {
  const d = decisionSizing({ attente: true, donnees: RECO,
    cleServie: ANCIENNE, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'reponse-perimee')
})

test('ÉCHEC FRAIS : refus, avec le motif FR VERBATIM du serveur', () => {
  const d = decisionSizing({ attente: true, erreur: 'Aperçu indisponible.',
    cleErreur: CLE, cleCourante: CLE })
  assert.equal(d.action, 'refuser')
  assert.equal(d.motif, 'Aperçu indisponible.')
})

test('ÉCHEC PÉRIMÉ : le drapeau reste OUVERT et AUCUN refus obsolète n’est épinglé', () => {
  // C'EST LE CORRECTIF DE LA TÂCHE : aujourd'hui seule la branche SUCCÈS est
  // gardée, et un échec décrivant l'ANCIENNE facture ferme l'attente.
  const d = decisionSizing({ attente: true, erreur: 'Aperçu indisponible.',
    cleErreur: ANCIENNE, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'echec-perime')
})

test('ÉCHEC NON ATTRIBUABLE à un corps : traité comme périmé, jamais comme un refus', () => {
  const d = decisionSizing({ attente: true, erreur: 'Boom', cleErreur: null, cleCourante: CLE })
  assert.equal(d.action, 'attendre')
})

test('réponse fraîche SANS recommandation chiffrée : refus, motif nommé', () => {
  const d = decisionSizing({
    attente: true, cleServie: CLE, cleCourante: CLE,
    donnees: { dimensionnement: { motivation: 'Ville du client manquante.' } },
  })
  assert.equal(d.action, 'refuser')
  assert.equal(d.motif, 'Ville du client manquante.')
})

test('ordre du motif : avertissement, puis motivation, puis erreur, puis générique', () => {
  assert.equal(motifRefus({ avertissements: ['A'], dimensionnement: { motivation: 'B' } }, 'C'), 'A')
  assert.equal(motifRefus({ dimensionnement: { motivation: 'B' } }, 'C'), 'B')
  assert.equal(motifRefus(null, 'C'), 'C')
  assert.equal(motifRefus(null, null), REFUS_GENERIQUE)
})

test('aucune réponse encore arrivée : on attend', () => {
  assert.equal(decisionSizing({ attente: true, cleCourante: CLE }).action, 'attendre')
})

// ── useComposition : `raison` est TOUJOURS rendue ────────────────────────────

const L = [{ designation: 'Panneau 710 W', quantite: 12 }]

test('STRUCTUREL : toute composition porte une source ET une raison non vide', () => {
  const cas = [
    { serveur: { lignes: L } },
    { local: { lignes: L, raison: 'aucun dry-run serveur pour le marché agricole' } },
    { local: { lignes: L }, erreur: 'timeout' },
    { local: { lignes: [] }, marche: 'industriel' },
    { erreur: 'HTTP 500' },
    {},
  ]
  for (const c of cas) {
    const r = resoudreComposition(c)
    assert.ok(['serveur', 'local'].includes(r.source), JSON.stringify(c))
    assert.equal(typeof r.raison, 'string')
    assert.ok(r.raison.length > 0, `raison vide pour ${JSON.stringify(c)}`)
    assert.ok(Array.isArray(r.lignes))
  }
})

test('le serveur gagne quand il a composé', () => {
  const r = resoudreComposition({ serveur: { lignes: L }, local: { lignes: [] } })
  assert.equal(r.source, 'serveur')
  assert.equal(r.raison, RAISON_SERVEUR)
  assert.deepEqual(r.lignes, L)
})

test('le repli local NOMME la cause de l’échec serveur (jamais silencieux)', () => {
  const r = resoudreComposition({ local: { lignes: L }, erreur: 'HTTP 500' })
  assert.equal(r.source, 'local')
  assert.equal(r.raison, raisonRepli('HTTP 500'))
  assert.match(r.raison, /HTTP 500/)
  assert.match(r.raison, /secours/)
})

test('un marché SANS dry-run garde la raison de son module de marché', () => {
  const raison = 'aucun dry-run serveur pour le marché agricole — composition pompage locale'
  const r = resoudreComposition({ local: { lignes: L, raison }, marche: 'agricole' })
  assert.equal(r.source, 'local')
  assert.equal(r.raison, raison)
})

test('rien à composer : lignes vides ET une raison qui le dit', () => {
  assert.equal(resoudreComposition({}).raison, RAISON_RIEN)
  assert.equal(resoudreComposition({ local: { lignes: [], motif: 'renseignez les CV' } }).raison,
    'renseignez les CV')
})
