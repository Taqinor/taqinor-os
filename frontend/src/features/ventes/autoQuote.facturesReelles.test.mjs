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
test('createAutoQuote : la garde résidentielle est mode === "residentiel" && hiver > 0', () => {
  const src = lire('./autoQuote.js')
  assert.match(src, /if \(mode === 'residentiel' && hiver > 0\)/)
})

test('createAutoQuote : les trois clés du contrat PACT10 sont écrites dans ce bloc', () => {
  const src = lire('./autoQuote.js')
  const debut = src.indexOf("if (mode === 'residentiel' && hiver > 0)")
  assert.ok(debut > 0, 'garde résidentielle introuvable')
  const bloc = src.slice(debut, debut + 900)
  assert.match(bloc, /factures_mensuelles_reelles:\s*facturesReelles/)
  assert.match(bloc, /conso_annuelle:\s*consoAnnuelleReelle/)
  assert.match(bloc, /distributeur:\s*distributeurLead/)
})

test('createAutoQuote : le bloc résidentiel vit APRÈS le scénario batterie et AVANT la branche industriel/commercial', () => {
  const src = lire('./autoQuote.js')
  const scenario = src.indexOf('Les deux (Sans + Avec)')
  const residentiel = src.indexOf("if (mode === 'residentiel' && hiver > 0)")
  const industriel = src.indexOf("mode === 'industriel' || mode === 'commercial'")
  assert.ok(scenario > 0 && residentiel > scenario && industriel > residentiel,
    'ordre attendu : scénario batterie → contrat résidentiel → branche industriel/commercial')
})

test('createAutoQuote : kwhFromBill est importé de ./solar (même inverse de barème que l\'écran manuel)', () => {
  const src = lire('./autoQuote.js')
  assert.match(src, /kwhFromBill,?\s*\n?\} from '\.\/solar'/)
})
