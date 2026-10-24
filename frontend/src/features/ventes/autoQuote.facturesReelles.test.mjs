// PACT10/QF-REAL (fondateur 19/08/2026) puis AGNR34 (D-AGNR-1 option (a),
// 08/10/2026) — le devis résidentiel auto semait douze mois DÉRIVÉS de
// hiver / été (une rampe) sous `factures_mensuelles_reelles` et une conso
// calculée au barème JS : une estimation présentée comme « réelle ». Le
// serveur lit désormais les deux factures du lead (`lead_bills_for_devis`) et
// dérive lui-même les marches (source `facture_hiver_ete`) ; l'écran n'envoie
// plus que le distributeur DÉCLARÉ du lead.
//
// autoQuote.js ne peut pas être importé tel quel par `node --test` (voir
// autoQuote.paliers.test.mjs / autoQuote.ordre.test.mjs) : ce test EXTRAIT et
// EXÉCUTE le vrai bloc `if (hiver > 0)` de la branche résidentielle. Le corps
// complet envoyé au serveur est joué par `autoQuote.tailleExplicite.test.jsx`.
//
// Run : node --test src/features/ventes/autoQuote.facturesReelles.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const ici = dirname(fileURLToPath(import.meta.url))
const lire = (rel) => readFileSync(join(ici, rel), 'utf-8')

// COUV-HOR — exécute le bloc `if (hiver > 0) { … }` RÉEL de la branche
// résidentielle de createAutoQuote (extrait du source, jamais une copie —
// même patron que noticePalierKwc dans autoQuote.test.mjs) : un test qui
// rejoue une copie reste vert quoi que devienne le vrai code.
function extraireBlocFacturesReelles() {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  const m = src.slice(debut).match(/\n( *)if \(hiver > 0\) \{([\s\S]*?)\n\1\}/)
  assert.ok(m, 'bloc `if (hiver > 0)` introuvable dans la branche résidentielle')
  return new Function('lead', 'hiver', 'etudeExtra', m[2])
}
const blocFacturesReelles = extraireBlocFacturesReelles()

function seedFacturesReellesLikeAutoQuote(lead) {
  const hiver = parseFloat(lead.facture_hiver) || 0
  if (!(hiver > 0)) return null
  const etudeExtra = {}
  blocFacturesReelles(lead, hiver, etudeExtra)
  return etudeExtra
}

test('lead SANS facture_hiver : aucune clé ajoutée', () => {
  assert.equal(seedFacturesReellesLikeAutoQuote({}), null)
  assert.equal(seedFacturesReellesLikeAutoQuote({ facture_hiver: 0 }), null)
  assert.equal(seedFacturesReellesLikeAutoQuote({ facture_hiver: null }), null)
})

test('AGNR34 — été différent : ni série de douze mois ni conso calculée au navigateur', () => {
  const out = seedFacturesReellesLikeAutoQuote({
    facture_hiver: '800', facture_ete: '1600', ete_differente: true, distributeur: 'onee',
  })
  assert.deepEqual(out, { distributeur: 'onee' })
})

test('distributeur inconnu ou hors barème : jamais semé', () => {
  for (const distributeur of [null, undefined, 'srm_casablanca', 'autre']) {
    assert.deepEqual(seedFacturesReellesLikeAutoQuote({ facture_hiver: '1500', distributeur }), {})
  }
})

// ── Verrou anti-dérive : le SOURCE réel porte bien cette même séquence ──────
// U3 (fondateur 20/08/2026) — le bloc vit dans la branche résidentielle qui
// part au SERVEUR (`if (mode === 'residentiel')`).
test('createAutoQuote : la garde résidentielle du contrat PACT10 est `hiver > 0`', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  assert.match(src.slice(debut, debut + 1600), /if \(hiver > 0\) \{/)
})

test('CIQ127 — createAutoQuote : le bloc résidentiel vit AVANT l’appel serveur des autres marchés', () => {
  const src = lire('./autoQuote.js')
  const residentiel = src.indexOf("if (mode === 'residentiel') {")
  // AGQ23 — la signature porte aussi `idempotencyKey` ; ALEA51 — et `onResultat`.
  const autres = src.indexOf('return creerDevisServeur({ lead, discountStr, onAlertes, onResultat, targetKwc, marche: mode, idempotencyKey })')
  assert.ok(residentiel > 0 && autres > residentiel,
    'ordre attendu : branche résidentielle (serveur) → agricole / C&I (serveur)')
})

// ── U3 — LE TEST DE NON-DIVERGENCE, côté écran ──────────────────────────────
// La moitié frontend de « une seule source de vérité » : le résidentiel ne
// compose plus AUCUNE ligne ici. S'il repassait un jour par `autoFillLines`,
// une deuxième composition renaîtrait sans que rien d'autre ne le signale.
test('U3 — le résidentiel délègue la composition au serveur, sans jamais composer de lignes', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  // La branche s'arrête à son `return id` : au-delà, les autres marchés
  // partent eux aussi au serveur (CIQ127).
  const bloc = src.slice(debut, src.indexOf('return id', debut))
  assert.doesNotMatch(bloc, /autoFillLines/,
    'le résidentiel ne doit plus composer de lignes à l\'écran')
  assert.doesNotMatch(bloc, /addLigneDevis/,
    'le résidentiel ne doit plus créer de lignes une par une')
  assert.match(bloc, /ventesApi\.creerDevisAuto\(/,
    'le résidentiel doit passer par POST /ventes/devis/auto/')
  // Ce que l'écran envoie : la puissance cible, la remise et l'étude — jamais
  // une ligne, un prix ou une marque (tout cela vit côté serveur).
  assert.match(bloc, /target_kwc:\s*kwpAuto/)
  assert.doesNotMatch(bloc, /prix_unitaire|marques:/,
    'aucun prix ni aucune marque ne doit remonter de l\'écran')
})
