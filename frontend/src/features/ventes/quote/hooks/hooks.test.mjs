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
import {
  ecrireChamp, changerProduit, appliquerTarif, suggestionTva, lignesUtilisables,
} from './useDevisLignesPur.js'

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

// ── useDevisLignes : verrou prixManuel, tarif, TVA ───────────────────────────

const LIGNES = [
  { _key: 1, produit: '7', designation: 'Panneau 710 W', quantite: '12',
    prix_unit_ttc: '1200', taux_tva: '10' },
  { _key: 2, produit: '9', designation: 'Onduleur hybride 8 kW', quantite: '1',
    prix_unit_ttc: '14000', taux_tva: '20' },
]

test('taper un prix pose le verrou prixManuel, sur CETTE ligne seulement', () => {
  const ls = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1300')
  assert.equal(ls[0].prixManuel, true)
  assert.equal(ls[0].prix_unit_ttc, '1300')
  assert.equal(ls[1].prixManuel, undefined)
})

test('modifier le taux retire le style « suggéré » de CETTE ligne seulement', () => {
  const ls = ecrireChamp([{ ...LIGNES[0], _tvaSuggested: true },
    { ...LIGNES[1], _tvaSuggested: true }], 1, 'taux_tva', '20')
  assert.equal(ls[0]._tvaSuggested, false)
  assert.equal(ls[1]._tvaSuggested, true)
  assert.equal(ls[0].prixManuel, undefined)   // aucun verrou posé par la TVA
})

test('N2 : la résolution de tarif ne réécrit JAMAIS un prix tapé à la main', () => {
  const verrouillees = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1300')
  const { lignes, badge } = appliquerTarif(verrouillees, 1,
    { prix: 999, source: 'liste', liste_nom: 'Grossistes' })
  assert.equal(lignes[0].prix_unit_ttc, '1300')   // la frappe survit
  assert.equal(badge, 'Grossistes')
})

test('un prix NON verrouillé prend bien le tarif de la liste', () => {
  const { lignes, badge } = appliquerTarif(LIGNES, 1,
    { prix: 999, source: 'liste', liste_nom: 'Grossistes' })
  assert.equal(lignes[0].prix_unit_ttc, '999')
  assert.equal(lignes[1].prix_unit_ttc, '14000')  // les autres lignes intactes
  assert.equal(badge, 'Grossistes')
})

test('tarif standard (ou absent) : aucune écriture, aucun badge', () => {
  for (const t of [{ prix: 999, source: 'standard' }, null, {}]) {
    const { lignes, badge } = appliquerTarif(LIGNES, 1, t)
    assert.equal(lignes[0].prix_unit_ttc, '1200')
    assert.equal(badge, null)
  }
})

test('resélectionner un produit LÈVE le verrou manuel', () => {
  const verrouillees = ecrireChamp(LIGNES, 1, 'prix_unit_ttc', '1300')
  const ls = changerProduit(verrouillees, 1, { id: 42, nom: 'Panneau 550 W' })
  assert.equal(ls[0].prixManuel, false)
  assert.equal(ls[0].produit, '42')
  assert.equal(ls[0].designation, 'Panneau 550 W')
})

test('la TVA est une SUGGESTION : elle signale, elle ne recale pas', () => {
  assert.deepEqual(suggestionTva(LIGNES[0]), { attendu: 10, coherent: true })
  assert.deepEqual(suggestionTva({ ...LIGNES[0], taux_tva: '20' }),
    { attendu: 10, coherent: false })
  assert.deepEqual(suggestionTva(LIGNES[1]), { attendu: 20, coherent: true })
  // Repères société (DC4) : les défauts sont surchargeables.
  assert.equal(suggestionTva(LIGNES[0], { tvaPanneaux: 7 }).attendu, 7)
})

test('lignes utilisables : un produit ET une quantité > 0', () => {
  const ls = [...LIGNES, { _key: 3, produit: '', quantite: '5' },
    { _key: 4, produit: '8', quantite: '0' }]
  assert.deepEqual(lignesUtilisables(ls).map(l => l._key), [1, 2])
  assert.deepEqual(lignesUtilisables(null), [])
})
