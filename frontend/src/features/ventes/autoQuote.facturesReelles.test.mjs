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
// EXTRAIT et EXÉCUTE le vrai bloc `if (hiver > 0)` de la branche résidentielle
// (COUV-HOR, 29/09/2026 — plus aucune copie rejouée), puis verrouille par
// lecture de SOURCE les clés écrites (même patron que autoQuote.ordre.test.mjs).
//
// Run : node --test src/features/ventes/autoQuote.facturesReelles.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { estimerMois, consoAnnuelleDepuisFactures } from './solar.js'

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
  return new Function('lead', 'hiver', 'etudeExtra', 'estimerMois',
    'consoAnnuelleDepuisFactures', m[2])
}
const blocFacturesReelles = extraireBlocFacturesReelles()

function seedFacturesReellesLikeAutoQuote(lead) {
  const hiver = parseFloat(lead.facture_hiver) || 0
  if (!(hiver > 0)) return null
  const etudeExtra = {}
  blocFacturesReelles(lead, hiver, etudeExtra, estimerMois,
    consoAnnuelleDepuisFactures)
  return etudeExtra
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
  // ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — 235 MAD est une facture TOTALE :
  // lignes fixes + TPPAN retirées, elle vaut 161,2 kWh/mois (le serveur,
  // `bareme.kwh_depuis_facture_mad`, rend le même chiffre), plus les 210 kWh
  // de l'inversion énergie seule.
  assert.equal(out.conso_annuelle, 1934)
})

test('COUV-HOR — DEV-202609-0113 : sans distributeur, la conso suit le barème national, jamais factures ÷ 1,20', () => {
  // Lead 1524 (Mohammedia) : distributeur NULL côté lead (le SRM n'est déduit
  // de la ville que côté serveur). Avant : 198 000 MAD ÷ 1,20 = 165 000 kWh,
  // donut « 28 % » face au « −37 % » de la même page.
  for (const distributeur of [null, undefined, 'srm_casablanca', 'autre']) {
    const out = seedFacturesReellesLikeAutoQuote({
      facture_hiver: '11000', facture_ete: '22000', ete_differente: true, distributeur,
    })
    assert.equal(out.factures_mensuelles_reelles.reduce((a, b) => a + b, 0), 198000)
    assert.equal(out.conso_annuelle,
      consoAnnuelleDepuisFactures(out.factures_mensuelles_reelles, 'onee'))
    // ERR-QAH-PROP-JS-CONSO-FACTURE-TOTALE — inverse de la facture COMPLÈTE :
    // 120 972 kWh/an, le chiffre de `etude_horaire.serie_kwh_depuis_mad`
    // (122 007 avec l'ancienne inversion énergie seule).
    assert.equal(out.conso_annuelle, 120972, `distributeur ${distributeur}`)
    assert.equal('distributeur' in out, false,
      'le libellé du distributeur n\'est jamais fabriqué')
  }
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
  const bloc = src.slice(debut, src.indexOf('return id', debut))
  assert.match(bloc, /etudeExtra\.factures_mensuelles_reelles = facturesReelles/)
  assert.match(bloc, /etudeExtra\.conso_annuelle = consoAnnuelleReelle/)
  assert.match(bloc, /etudeExtra\.distributeur = distributeurLead/)
})

test('CIQ127 — createAutoQuote : le bloc résidentiel vit AVANT l’appel serveur des autres marchés', () => {
  const src = lire('./autoQuote.js')
  const residentiel = src.indexOf("if (mode === 'residentiel') {")
  const autres = src.indexOf('return creerDevisServeur({ lead, discountStr, onAlertes, targetKwc, marche: mode })')
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

test('createAutoQuote : la conso annuelle vient de ./solar (même inverse de barème que l\'écran manuel)', () => {
  // FINDING 25/08 — la dérivation « 12 factures → kWh/an par le barème » est
  // désormais une aide PARTAGÉE (`consoAnnuelleDepuisFactures`, qui appelle
  // `kwhFromBill`) : le balayage de dimensionnement en a besoin AVANT
  // l'appel serveur (sans consommation, son modèle d'économie ne sature pas
  // et l'ascension marginale sur-vend). Une seule formule, donc aucun risque
  // de divergence entre la taille retenue et l'étude envoyée.
  const src = lire('./autoQuote.js')
  assert.match(src, /consoAnnuelleDepuisFactures,?\s*\n?\} from '\.\/solar'/)
  assert.doesNotMatch(src, /kwhFromBill\(/,
    'plus aucune inversion de barème recopiée sur place — tout passe par l\'aide partagée')
})
