// PACT10/QF-REAL (fondateur 19/08/2026) — un devis résidentiel auto ne
// stockait que {scenario} dans etude_params : le PDF (builder.py)
// reconstruisait alors les factures « avant » depuis l'économie SUPPOSÉE
// (proxy circulaire — audit du 19/08, la couverture solaire valait toujours
// ≈ le taux d'autoconsommation forfaitaire, jamais une vraie consommation).
//
// autoQuote.js::createAutoQuote sème désormais le contrat convenu avec le
// backend (etude_params.factures_mensuelles_reelles / conso_annuelle /
// distributeur) quand le lead porte une VRAIE facture d'hiver — mêmes
// briques déjà en production (estimerMois pour l'interpolation hiver/été,
// kwhFromBill pour l'inverse EXACT du barème, comme l'écran manuel de
// DevisGenerator QF4).
//
// autoQuote.js ne peut pas être importé tel quel par `node --test` (import
// relatif vers ./store/ventesSlice, dépendance à un `dispatch` Redux réel —
// voir autoQuote.paliers.test.mjs / autoQuote.ordre.test.mjs) : ce test
// rejoue donc EXACTEMENT la même séquence (mêmes fonctions solar.js, mêmes
// gardes) que la branche résidentielle ajoutée à createAutoQuote, puis
// verrouille par lecture de SOURCE que le code réel porte bien cette même
// séquence (protection anti-dérive, même patron que autoQuote.ordre.test.mjs).
//
// Run : node --test src/features/ventes/autoQuote.facturesReelles.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { estimerMois, kwhFromBill } from './solar.js'

const ici = dirname(fileURLToPath(import.meta.url))
const lire = (rel) => readFileSync(join(ici, rel), 'utf-8')

// Rejoue EXACTEMENT le nouveau bloc de createAutoQuote (branche résidentielle,
// mode !== 'agricole', hors industriel/commercial) : mêmes appels, même garde,
// mêmes clés. `mode` est fixé à 'residentiel' ici — les autres modes ne
// passent jamais par cette branche (voir autoQuote.js : le bloc est gardé par
// `mode === 'residentiel' && hiver > 0`).
function seedFacturesReellesLikeAutoQuote(lead) {
  const hiver = parseFloat(lead.facture_hiver) || 0
  if (!(hiver > 0)) return null
  const eteReel = (lead.ete_differente && lead.facture_ete)
    ? parseFloat(lead.facture_ete) : hiver
  const facturesReelles = estimerMois(hiver, eteReel)
  const distributeurLead = ['onee', 'lydec', 'redal'].includes(lead.distributeur)
    ? lead.distributeur : undefined
  const consoAnnuelleReelle = Math.round(facturesReelles.reduce(
    (somme, bill) => somme + (kwhFromBill(bill, distributeurLead).kwhMensuel || 0), 0))
  return {
    factures_mensuelles_reelles: facturesReelles,
    ...(consoAnnuelleReelle > 0 ? { conso_annuelle: consoAnnuelleReelle } : {}),
    ...(distributeurLead ? { distributeur: distributeurLead } : {}),
  }
}

test('lead SANS facture_hiver : aucune clé ajoutée (etude_params reste {scenario} seul)', () => {
  assert.equal(seedFacturesReellesLikeAutoQuote({}), null)
  assert.equal(seedFacturesReellesLikeAutoQuote({ facture_hiver: 0 }), null)
  assert.equal(seedFacturesReellesLikeAutoQuote({ facture_hiver: null }), null)
})

test('lead avec facture d\'hiver flat, sans distributeur connu : 12 vraies factures, conso estimée, PAS de clé distributeur', () => {
  const out = seedFacturesReellesLikeAutoQuote({ facture_hiver: '1500' })
  assert.deepEqual(out.factures_mensuelles_reelles, Array(12).fill(1500))
  assert.ok(out.conso_annuelle > 0)
  assert.equal('distributeur' in out, false,
    'sans distributeur connu, la clé ne doit jamais être fabriquée')
})

test('lead avec distributeur ONEE connu : la clé distributeur est semée, tranche de barème réel', () => {
  // Facture hiver = 235 MAD/mois, un point de repère EXACT du barème ONEE
  // (verrouillé par solar.test.mjs QF4 : kwhFromBill(235, 'onee').kwhMensuel
  // === 210, un vrai « trou » de la grille sélective résolu à la borne basse).
  const out = seedFacturesReellesLikeAutoQuote({
    facture_hiver: '235', distributeur: 'onee',
  })
  assert.deepEqual(out.factures_mensuelles_reelles, Array(12).fill(235))
  assert.equal(out.distributeur, 'onee')
  assert.equal(out.conso_annuelle, Math.round(12 * 210))
})

test('distributeur "autre" (connu du lead mais hors barème) : jamais semé comme distributeur', () => {
  const out = seedFacturesReellesLikeAutoQuote({
    facture_hiver: '1500', distributeur: 'autre',
  })
  assert.equal('distributeur' in out, false)
})

test('lead avec été différent : les 12 factures suivent l\'interpolation hiver/été (même formule que le dimensionnement)', () => {
  const out = seedFacturesReellesLikeAutoQuote({
    facture_hiver: '900', facture_ete: '1800', ete_differente: true,
  })
  assert.deepEqual(out.factures_mensuelles_reelles, estimerMois(900, 1800))
  // Vraie saisonnalité : pas un plat à 900 partout.
  assert.ok(out.factures_mensuelles_reelles.some((v) => v !== 900))
})

test('ete_differente=false : l\'été ne change rien, comme le dimensionnement existant', () => {
  const out = seedFacturesReellesLikeAutoQuote({
    facture_hiver: '900', facture_ete: '1800', ete_differente: false,
  })
  assert.deepEqual(out.factures_mensuelles_reelles, Array(12).fill(900))
})

// ── Verrou anti-dérive : le SOURCE réel porte bien cette même séquence ──────
// U3 (fondateur 20/08/2026) — le bloc PACT10 a MIGRÉ : il vit désormais dans
// la branche résidentielle qui part au SERVEUR (`if (mode === 'residentiel')`),
// et ses trois clés voyagent en `etude_params` de POST /ventes/devis/auto/ au
// lieu d'accompagner des lignes composées ici. La séquence de calcul, elle,
// est inchangée — c'est tout l'objet des tests de valeurs ci-dessus.
test('createAutoQuote : la garde résidentielle du contrat PACT10 est `hiver > 0`', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  assert.match(src.slice(debut, debut + 1600), /if \(hiver > 0\) \{/)
})

test('createAutoQuote : les trois clés du contrat PACT10 sont écrites dans ce bloc', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  const bloc = src.slice(debut, debut + 1800)
  assert.match(bloc, /etudeExtra\.factures_mensuelles_reelles = facturesReelles/)
  assert.match(bloc, /etudeExtra\.conso_annuelle = consoAnnuelleReelle/)
  assert.match(bloc, /etudeExtra\.distributeur = distributeurLead/)
})

test('createAutoQuote : le bloc résidentiel vit AVANT la branche industriel/commercial', () => {
  const src = lire('./autoQuote.js')
  const residentiel = src.indexOf("if (mode === 'residentiel') {")
  const industriel = src.indexOf("mode === 'industriel' || mode === 'commercial'")
  assert.ok(residentiel > 0 && industriel > residentiel,
    'ordre attendu : branche résidentielle (serveur) → branche industriel/commercial')
})

// ── U3 — LE TEST DE NON-DIVERGENCE, côté écran ──────────────────────────────
// La moitié frontend de « une seule source de vérité » : le résidentiel ne
// compose plus AUCUNE ligne ici. S'il repassait un jour par `autoFillLines`,
// une deuxième composition renaîtrait sans que rien d'autre ne le signale.
test('U3 — le résidentiel délègue la composition au serveur, sans jamais composer de lignes', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel') {")
  assert.ok(debut > 0, 'branche résidentielle introuvable')
  // La branche s'arrête à son `return id` : au-delà commence le code
  // industriel/commercial, qui lui compose encore à l'écran (hors périmètre).
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

test('createAutoQuote : kwhFromBill est importé de ./solar (même inverse de barème que l\'écran manuel)', () => {
  const src = lire('./autoQuote.js')
  assert.match(src, /kwhFromBill,?\s*\n?\} from '\.\/solar'/)
})
