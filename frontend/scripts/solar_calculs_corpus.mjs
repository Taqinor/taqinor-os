#!/usr/bin/env node
// QAH-PROP (feature #3 du lot QA) — CORPUS FIGÉ #2 pour le test différentiel
// `solar.js` (écran) <-> Python, sur les CALCULS que le corpus PACT10 laissait
// HORS PÉRIMÈTRE (voir l'en-tête de `solar_corpus.mjs`, points 4 et 6) :
//
//   * `tranche_bill`    — facture d'un volume mensuel de kWh par tranche
//                          (`monthlyBillFromKwh` <-> `pricing._monthly_bill_from_kwh`) ;
//   * `bill_to_kwh`     — facture -> kWh/mois pour CHAQUE branche de distributeur :
//                          aucun, ONEE/Lydec/Redal, SRM, « autre », grille vendeur
//                          (`kwhFromBill` <-> `pricing.kwh_from_bill`) ;
//   * `facture_detail`  — kWh -> facture détaillée, lignes fixes + TPPAN
//                          (`factureMad`/`tppanMad` <-> `bareme.facture_mad`/`tppan_mad`) ;
//   * `conso_annuelle`  — 12 factures -> kWh/an
//                          (`consoAnnuelleDepuisFactures` <-> somme de `kwh_from_bill`,
//                          ET <-> `etude_horaire.serie_kwh_depuis_mad`, l'inversion
//                          que le serveur applique réellement) ;
//   * `two_bills`       — économies « deux factures »
//                          (`twoBillsSavings` <-> `pricing.two_bills_savings`) ;
//   * `roi`             — ROI/économies/payback/autoconsommation
//                          (`computeROI` <-> `pricing.calculate_savings_roi`, branche
//                          « factures » et branche « estimation sans distributeur ») ;
//   (AGR132 — les axes `pompe_debit`, `pompe_select`, `pompe_variateur` sont
//   RETIRÉS avec le moteur pompage JS : le serveur est la seule source,
//   couverte par les tests du noyau `calepinage.services.pompage`.)
//
// GÉNÉRATION. PRNG seedé (mulberry32, aucune dépendance) : mêmes cas à chaque
// exécution. Les générateurs visent exprès les BRANCHES LIMITES : aucun
// distributeur, « autre », SRM, factures nulles / un seul mois / été != hiver /
// énormes, bornes de tranche exactes (100/150/200/210/300/310/500/510 kWh),
// productible par défaut / override, une ou deux options (batterie 0 vs > 0).
//
// RÉGÉNÉRATION (PACT10). Ces fichiers ne se régénèrent QUE par un humain qui a
// tranché une divergence : `node frontend/scripts/solar_calculs_corpus.mjs`
// puis relire le diff. JAMAIS pour faire passer un test rouge.
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  ONEE_TRANCHES, monthlyBillFromKwh, kwhFromBill, consoAnnuelleDepuisFactures,
  factureMad, tppanMad, twoBillsSavings, computeROI,
} from '../src/features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURES_DIR = join(
  HERE, '..', '..', 'backend', 'django_core', 'apps', 'ventes', 'tests',
  'fixtures')
export const CORPUS_PATH = join(FIXTURES_DIR, 'solar_calculs_corpus.json')
export const EXPECTED_PATH = join(FIXTURES_DIR, 'solar_calculs_expected.json')

function mulberry32(seed) {
  let a = seed >>> 0
  return function rand() {
    a |= 0
    a = (a + 0x6D2B79F5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
// Graine FIGÉE — ne jamais la changer sans régénérer sciemment le contrat.
export const SEED = 0x0AB3D1F
const rand = mulberry32(SEED)
const pick = (arr) => arr[Math.floor(rand() * arr.length)]
const randInt = (min, max) => Math.floor(rand() * (max - min + 1)) + min
const randFloat = (min, max) => min + rand() * (max - min)
const logFloat = (min, max) => Math.exp(Math.log(min) + rand() * (Math.log(max) - Math.log(min)))
const round2 = (x) => Math.round(x * 100) / 100

// Distributeurs : chaque branche de `resolveTranches` / `_resolve_tranches`.
// `null` = aucun ; '' et blancs = aucun ; les trois nommés ; SRM ; « autre ».
const UTILITIES = [null, '', '   ', 'onee', 'ONEE', 'lydec', 'redal', 'autre',
  'srm-casablanca-settat', 'SRM Souss-Massa', 'Amendis']
const NOMMES = UTILITIES.filter((u) => u && u.trim())

// Grille vendeur PROGRESSIVE aléatoire (barème collé à la main) : la forme JSON
// est celle que le backend reçoit dans `etude_params` : [[plafond|null, prix], …].
function genGrilleVendeur() {
  const n = randInt(1, 6)
  let plafond = 0
  let prix = randFloat(0.5, 1.2)
  const table = []
  for (let i = 0; i < n; i++) {
    plafond += randInt(30, 250)
    prix += randFloat(0, 0.4)
    table.push([i === n - 1 && rand() < 0.7 ? null : plafond, Math.round(prix * 1e4) / 1e4])
  }
  return table
}

// Tables : 'onee' (la grille sélective du barème) ou une grille vendeur.
const genTable = (pOnee = 0.6) => (rand() < pOnee ? 'onee' : genGrilleVendeur())

const BORNES_KWH = [0, 0.1, 1, 50, 50.1, 99.9, 100, 100.1, 149.9, 150, 150.01,
  199.9, 200, 209.9, 210, 210.1, 250, 299.9, 300, 309.9, 310, 310.1, 499.9, 500,
  509.9, 510, 510.1, 700, 1000, 5000, 100000]

function genFactures() {
  const forme = pick(['plate', 'hiver_ete', 'aleatoire', 'un_mois', 'zeros', 'enorme', 'dix_mois'])
  const base = Math.round(logFloat(30, 6000))
  switch (forme) {
    case 'plate': return Array(12).fill(base)
    case 'hiver_ete': {
      const ete = Math.round(base * randFloat(1.2, 3))
      return Array.from({ length: 12 }, (_, i) => (i >= 5 && i <= 8 ? ete : base))
    }
    case 'un_mois': {
      const f = Array(12).fill(0)
      f[randInt(0, 11)] = base
      return f
    }
    case 'zeros': return Array(12).fill(0)
    case 'enorme': return Array.from({ length: 12 }, () => Math.round(logFloat(1e4, 4e5)))
    case 'dix_mois': return Array.from({ length: 10 }, () => Math.round(logFloat(30, 6000)))
    default: return Array.from({ length: 12 }, () => Math.round(logFloat(30, 6000)))
  }
}

// ── Génération ───────────────────────────────────────────────────────────────
function genCorpus() {
  const entries = []
  let n = 0
  const push = (axe, e) => { entries.push({ id: `QAHP-${String(n++).padStart(4, '0')}`, axe, ...e }) }

  // tranche_bill : chaque borne × la grille ONEE, puis des cas aléatoires.
  for (const kwh of BORNES_KWH) push('tranche_bill', { table: 'onee', kwh })
  for (let i = 0; i < 60; i++) {
    push('tranche_bill', { table: genTable(0.4), kwh: rand() < 0.5 ? round2(logFloat(0.5, 4000)) : randInt(0, 1500) })
  }

  // bill_to_kwh : chaque distributeur × factures aux bornes / aléatoires / énormes.
  const BILLS_TYPES = [0, -5, 1, 30, 100, 225.37, 235, 245.2, 300, 496.03, 500, 1000, 5000, 25000, 250000]
  for (const utility of UTILITIES) {
    for (const bill of BILLS_TYPES) push('bill_to_kwh', { utility, bill, table: null })
  }
  for (let i = 0; i < 90; i++) {
    push('bill_to_kwh', { utility: pick(UTILITIES), bill: Math.round(logFloat(1, 60000) * 100) / 100, table: rand() < 0.25 ? genGrilleVendeur() : null })
  }
  // HORS PLAGE inversable (> ~1,6 M MAD/mois) : la garde QJR158(e) n'existe que côté Python.
  for (const bill of [2e6, 5e6, 1e8]) push('bill_to_kwh', { utility: 'onee', bill, table: null })

  // facture_detail : kWh -> facture complète (énergie + lignes fixes + TPPAN).
  for (const kwh of BORNES_KWH) push('facture_detail', { kwh, jours: 30, table: 'onee' })
  for (let i = 0; i < 60; i++) {
    push('facture_detail', { kwh: round2(logFloat(0.5, 4000)), jours: pick([28, 30, 31, 60]), table: genTable(0.5) })
  }

  // conso_annuelle : 12 factures (nulles / un mois / été != hiver / énormes / dix mois).
  for (let i = 0; i < 80; i++) {
    push('conso_annuelle', { factures: genFactures(), utility: pick(UTILITIES) })
  }

  // two_bills : production, conso, taux, distributeur, grille éventuelle.
  for (let i = 0; i < 100; i++) {
    push('two_bills', {
      production: Math.round(logFloat(200, 300000)),
      conso: Math.round(logFloat(200, 500000)),
      ratio: pick([0.05, 0.3, 0.6, 0.85, 1, 1.5]) * randFloat(0.9, 1.1),
      utility: pick(rand() < 0.8 ? NOMMES : UTILITIES),
      table: rand() < 0.2 ? genGrilleVendeur() : null,
    })
  }
  // Cas dégénérés (null des deux côtés).
  push('two_bills', { production: 5000, conso: 0, ratio: 0.6, utility: 'onee', table: null })
  push('two_bills', { production: 0, conso: 5000, ratio: 0.6, utility: 'onee', table: null })
  push('two_bills', { production: 5000, conso: 5000, ratio: 0, utility: 'onee', table: null })
  push('two_bills', { production: 5000, conso: 5000, ratio: 0.6, utility: null, table: null })

  // roi : une ou deux options (batterie 0 vs > 0), avec/sans consommation, tous distributeurs.
  for (let i = 0; i < 120; i++) {
    const kwp = round2(pick([1, 3, 5, 8, 10, 20, 50, 200]) * randFloat(0.8, 1.2))
    push('roi', {
      kwp,
      utility: pick(rand() < 0.75 ? NOMMES : UTILITIES),
      conso: rand() < 0.75 ? Math.round(logFloat(500, 400000)) : null,
      batteryKwh: pick([0, 0, 5, 10, 15.36]),
      productible: pick([null, 1550, 1651, 1687]),
      totalSans: Math.round(kwp * randFloat(6000, 14000)),
      facteurAvec: round2(randFloat(1.05, 1.5)),
    })
  }

  return entries
}

const tableJs = (t) => (t === 'onee' ? ONEE_TRANCHES : t)

// ── CE QUE `solar.js` CALCULE sur une entrée — LE contrat ────────────────────
// Exportée pour que `solar.calculs.corpus.test.mjs` réutilise EXACTEMENT cette
// composition (aucune réimplémentation dupliquée côté test).
export function computeExpectedForEntry(e) {
  switch (e.axe) {
    case 'tranche_bill':
      return { bill: monthlyBillFromKwh(e.kwh, tableJs(e.table)) }
    case 'bill_to_kwh': {
      const r = kwhFromBill(e.bill, e.utility ?? undefined, e.table ?? undefined)
      return { kwh: r.kwhMensuel, approximatif: r.approximatif, estimation: r.estimation }
    }
    case 'facture_detail': {
      const f = factureMad(e.kwh, tableJs(e.table), e.jours)
      return {
        energie: f.energieMad, fixes: f.locationEntretienMad, tppan: f.tppanMad,
        total: f.totalMad, tppan_seul: tppanMad(e.kwh, e.jours),
      }
    }
    case 'conso_annuelle':
      return { conso: consoAnnuelleDepuisFactures(e.factures, e.utility ?? undefined) }
    case 'two_bills': {
      const r = twoBillsSavings(e.production, e.conso, e.ratio, e.utility ?? undefined, e.table ?? undefined)
      return r === null ? { null: true } : {
        facture_sans: r.factureSans, facture_avec: r.factureAvec,
        economie: r.economie, autoconso_kwh: r.autoconsoKwh,
      }
    }
    case 'roi': {
      const r = computeROI({
        kwp: e.kwp, factures: undefined, dayUsagePct: undefined,
        totalSans: e.totalSans, totalAvec: Math.round(e.totalSans * e.facteurAvec),
        batteryKwh: e.batteryKwh, consoAnnuelleKwh: e.conso ?? undefined,
        utility: e.utility ?? undefined, productible: e.productible ?? undefined,
      })
      return {
        modele: r.savings_model,
        production: r.production_annuelle_kwh,
        eco_sans: r.eco_annuelle_sans, eco_avec: r.eco_annuelle_avec,
        payback_sans: r.payback_sans, payback_avec: r.payback_avec,
        autoconso_sans: r.autoconso_sans, autoconso_avec: r.autoconso_avec,
        facture_sans: r.facture_sans, facture_avec_sans: r.facture_avec_sans,
        facture_avec_avec: r.facture_avec_avec,
        net_gain_sans: r.net_gain_sans, net_gain_avec: r.net_gain_avec,
      }
    }
    default:
      throw new Error(`axe inconnu : ${e.axe}`)
  }
}

function main() {
  const entries = genCorpus()
  const expected = entries.map((e) => ({ id: e.id, axe: e.axe, ...computeExpectedForEntry(e) }))
  mkdirSync(FIXTURES_DIR, { recursive: true })
  const entete = {
    pact: 'PACT10',
    genere_par: 'frontend/scripts/solar_calculs_corpus.mjs',
    regeneration: "UNIQUEMENT par un humain qui a tranché une divergence — "
      + "jamais par un agent pour repasser un test au vert (voir l'en-tête du script).",
    seed: SEED,
    count: entries.length,
  }
  writeFileSync(CORPUS_PATH, `${JSON.stringify({ ...entete, entries }, null, 1)}\n`)
  writeFileSync(EXPECTED_PATH, `${JSON.stringify({ ...entete, entries: expected }, null, 1)}\n`)
  console.log(`solar_calculs: ${entries.length} entrées écrites dans\n  ${CORPUS_PATH}\n  ${EXPECTED_PATH}`)
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
if (isMain) main()
