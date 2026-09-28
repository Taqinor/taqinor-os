#!/usr/bin/env node
// QAH3 (plan docs/PLAN.md, GROUPE QAH — « tester comme un humain ») — CORPUS
// FIGÉ pour le test différentiel `solar.js` (écran) ↔ `quote_engine/builder.py`
// (PDF), PACT10 : le contrat partagé entre les deux moitiés.
//
// CE QUE CE SCRIPT FAIT. Génère ~200 entrées de devis (Résidentiel /
// Industriel-Commercial / Agricole-pompage) avec un PRNG SEEDÉ déterministe
// (pas de dépendance `fast-check` — elle n'est pas installée dans ce dépôt et
// la règle CLAUDE.md interdit toute nouvelle dépendance non demandée), puis
// calcule CE QUE `solar.js` calcule sur ces entrées (classification par ligne,
// kWc dérivé des lignes, productible/production PVGIS, total TTC de l'option
// effective). Deux fichiers COMMIS, relus par les deux suites de test :
//
//   * `solar_corpus.json`          — les ~200 entrées D'ENTRÉE, figées.
//   * `solar_corpus_expected.json` — CE QUE `solar.js` calcule sur ces entrées
//     (le contrat que le jumeau Python doit reproduire pour les grandeurs
//     qu'il calcule RÉELLEMENT lui aussi — voir la portée ci-dessous).
//
// RÉGÉNÉRATION — PACT10 : ces deux fichiers ne se régénèrent QUE quand un
// humain a tranché une divergence (jamais par un agent qui voudrait « repasser
// au vert » un test rouge). Régénérer : `node frontend/scripts/solar_corpus.mjs`
// depuis la racine du dépôt, puis relire le diff des deux fichiers commis.
//
// PORTÉE EXACTE DE LA COMPARAISON (ce que les DEUX moteurs calculent
// RÉELLEMENT — jamais une comparaison inventée) :
//
//   1. CLASSIFICATION de chaque ligne — mots-clés réseau/injection, hybride,
//      offgrid, batterie, panneau. `solar.js` (`isBattery`, `isHybridInverter`,
//      `isReseauInverter`, `isOffgridInverter`, `isAnyInverter`, `isPanel`) et
//      `apps/ventes/solar_design.py` (importé tel quel par `builder.py` sous
//      les alias `_is_battery`/`_is_hybrid_inverter`/`_is_reseau_inverter`/
//      `_is_offgrid_inverter`/`_is_inverter`/`_is_panel`) sont VOULUS comme
//      mots-clés identiques (CLAUDE.md règle #4). ATTENTION AU NOM : l'alias
//      JS `isAnyInverter` (« tout onduleur, réseau/hybride/non classé ») est
//      le miroir documenté (solar.js:1052-56) de `builder._is_inverter` — PAS
//      de `solar_design.is_any_inverter`, qui répond à une question DIFFÉRENTE
//      (hybride OU réseau OU offgrid, donc FAUX sur un micro-onduleur non
//      classé alors que `_is_inverter`/`isAnyInverter` répondent VRAI). Le
//      test Python doit comparer contre `_is_inverter`, jamais l'autre.
//
//   2. kWc DÉRIVÉ DES LIGNES — `builder.py panneaux_et_watt_lu(lignes)` compte
//      les lignes panneau (`_is_panel`) et lit leur puissance unitaire
//      (fiche technique, repli regex `_parse_watt`/`WATT_RE` — LA MÊME regex
//      des deux côtés, `core/product_roles.py::WATT_RE`). `solar.js` n'exporte
//      pas de fonction agrégée équivalente (elle vit inline dans plusieurs
//      écrans) : ce script COMPOSE la même agrégation à partir des fonctions
//      RÉELLEMENT exportées (`isPanel` + `parseWatt`), pour comparer les
//      PRÉDICATS/PARSERS eux-mêmes, jamais une réimplémentation cachée.
//
//   3. PRODUCTIBLE PAR VILLE (PVGIS, QX38) — `productibleForCity` (solar.js)
//      et `productible_for_city` (`quote_engine/productible.py`) sont un
//      miroir déclaré EXACT (mêmes villes, même repli, même règle d'override
//      société) : comparé ville par ville, avec et sans override.
//
//   4. PRODUCTION ANNUELLE — `kwc × productible × facteur de perte` : la
//      constante `PRODUCTIBLE_NET_FACTOR` (solar.js) et `PRODUCTION_DERATE`
//      (`quote_engine/pricing.py`) sont la MÊME valeur ((1−0,20)/(1−0,14)),
//      documentées comme miroir l'une de l'autre. Comparé sur ce SEUL calcul
//      fermé — PAS le reste de `computeROI`/`calculate_savings_roi`
//      (tarifs par tranche, décalage batterie horaire, facture réelle…) :
//      cette partie-là n'est PAS un calcul fermé comparable sans reproduire
//      tout un moteur tarifaire des deux côtés, hors périmètre de QAH3.
//
//   5. TOTAUX (« centime equality ») — `solar.js optionTotalsTTC` (l'aperçu
//      ÉCRAN, 100 % TTC — CLAUDE.md : « the screen is 100% TTC ») compare au
//      total CANONIQUE que le backend facture réellement
//      (`apps.ventes.selectors._canonical_totaux`, la même chaîne que
//      `domain.argent.totaux`/`option_totaux`, EXACTEMENT celle que le PDF
//      imprime — builder.py:1786). CE SONT DEUX FORMULES STRUCTURELLEMENT
//      DIFFÉRENTES PAR CONCEPTION : l'écran arrondit la remise sur la somme
//      TTC déjà arrondie ligne à ligne ; le canon arrondit la remise sur le
//      HT brut AVANT la TVA, taux par taux. QAH3 mesure si cette différence de
//      CONCEPTION produit une différence de VALEUR au centime — voir
//      `known_divergences` du test Python pour le verdict mesuré.
//
//   6. HORS PÉRIMÈTRE, VÉRIFIÉ ABSENT CÔTÉ PYTHON — pompe/débit/HMT.
//      `builder.py` ne recalcule RIEN sur le pompage : il relit tel quel
//      `devis.etude_params`/`region`/`pompe_nom` (calculés UNE FOIS par
//      `solar.js` à la création et persistés) — grep confirmé, aucune fonction
//      `_is_pompe`/HMT/débit n'existe dans `builder.py`. Comparer un calcul
//      pompage reviendrait à comparer `solar.js` à lui-même. Le corpus
//      contient quand même des entrées agricoles (panneaux + pompe + variateur
//      + afficheur, JAMAIS d'onduleur ni de batterie — CLAUDE.md) pour exercer
//      la classification sur ce vocabulaire (vérifier que pompe/variateur ne
//      sont RIEN des six prédicats, des deux côtés).
//
// Run : `node frontend/scripts/solar_corpus.mjs` (depuis la racine du dépôt,
// ou n'importe où — les chemins sont résolus depuis ce fichier).
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  isBattery, isHybridInverter, isReseauInverter, isOffgridInverter,
  isAnyInverter, isPanel, parseWatt, productibleForCity,
  PRODUCTIBLE_NET_FACTOR, optionTotalsTTC,
} from '../src/features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const FIXTURES_DIR = join(
  HERE, '..', '..', 'backend', 'django_core', 'apps', 'ventes', 'tests',
  'fixtures')
const CORPUS_PATH = join(FIXTURES_DIR, 'solar_corpus.json')
const EXPECTED_PATH = join(FIXTURES_DIR, 'solar_corpus_expected.json')

// ── PRNG seedé (mulberry32) — déterministe, AUCUNE dépendance nouvelle ───────
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

// Graine FIGÉE : ne JAMAIS changer sans régénérer sciemment le contrat
// (PACT10 — voir l'en-tête). Un changement de graine change les ~200 entrées
// et donc le fichier attendu tout entier.
const SEED = 0x51A5017
const rand = mulberry32(SEED)

function pick(arr) { return arr[Math.floor(rand() * arr.length)] }
function randInt(min, max) { return Math.floor(rand() * (max - min + 1)) + min }
function round2(x) { return Math.round((x + Number.EPSILON) * 100) / 100 }

// ── Vocabulaire — désignations RÉALISTES (catalogue seedé + fixture QJR2) ────
const VILLES = ['Casablanca', 'Rabat', 'Marrakech', 'Agadir', 'Tanger',
  'Kenitra', 'Settat', 'Essaouira', 'VilleInconnuePVGIS']
const PANEL_WATTS = [455, 550, 585, 590, 605, 625, 710]
// Désignation / nom-produit — deux cas QJR2 volontairement inclus (« Module PV
// 550 W », « JA Solar 550 Wc ») pour re-vérifier que le correctif QJR92a tient.
function panelLine(watt) {
  const kind = pick(['panneau', 'module_pv', 'marque_watt'])
  if (kind === 'panneau') {
    const marque = pick(['Canadian Solar', 'JA Solar', 'Trina Solar', 'Longi'])
    return { designation: `Panneau ${marque} ${watt}W`, produit_nom: '' }
  }
  if (kind === 'module_pv') {
    return { designation: `Module PV ${watt} W`, produit_nom: '' }
  }
  return { designation: `JA Solar ${watt} Wc`, produit_nom: '' }
}
const RESEAU_TEMPLATES = [
  (kw) => `Onduleur réseau Huawei SUN2000 ${kw}kW`,
  (kw) => `Onduleur réseau Deye ${kw}kW Triphasé`,
  (kw) => `Onduleur injection Huawei ${kw}kW`,
]
const HYBRIDE_TEMPLATES = [
  (kw) => `Onduleur hybride Deye ${kw}kW Monophasé`,
  (kw) => `Onduleur hybride Huawei ${kw}kW`,
]
const OFFGRID_TEMPLATES = [
  (kw) => `Onduleur autonome Victron ${kw}kW`,
  (kw) => `Deye off-Grid ${kw}kW`,
  (kw) => `Onduleur hors réseau ${kw}kW`,
]
const INVERTER_KW = [3, 5, 6, 8, 10, 15, 20]
function batteryLine() {
  // Un cas QJR2 SANS kWh lisible (« Batterie Deye BOS-B-Pack ») inclus exprès
  // — le correctif QJR92b (contribution 0, jamais 5.0 inventé) est déjà en
  // place des deux côtés ; ce cas re-vérifie que ça tient.
  const kind = pick(['dyness', 'pylontech', 'bos_b_pack'])
  if (kind === 'bos_b_pack') return 'Batterie Deye BOS-B-Pack'
  const kwh = pick([2.2, 5.0, 5.12, 10.0, 10.5, 15.36])
  const marque = kind === 'dyness' ? 'Dyness' : 'Pylontech'
  return `Batterie ${marque} ${kwh} kWh`
}
const STRUCTURE_DESIGNATIONS = [
  'Structure aluminium toiture inclinée', 'Structure acier au sol',
]
const CABLE_DESIGNATIONS = [
  'Câble DC solaire 6mm² (lot)', 'Câble terre 16mm² (lot)',
]
const SMART_METER_DESIGNATION = 'Smart Meter Huawei DTSU666'
const WIFI_DONGLE_DESIGNATIONS = ['Clé Wi-Fi Huawei SmartLogger', 'Passerelle Wi-Fi Deye']
const PUMP_DESIGNATIONS = [
  'Pompe immergée OSP 30-8 3HP', 'Pompe immergée OSP 30-14 5HP',
  'Pompe immergée OSP 30-22 7.5HP',
]
const VARIATEUR_DESIGNATIONS = [
  'Variateur VEICHI SVF3 5.5kW', 'Variateur VEICHI SVF3 7.5kW',
  'Variateur VEICHI SVF3 11kW',
]
const AFFICHEUR_DESIGNATION = 'Afficheur SI22'

function buildLigne(designation, produitNom, quantite, prixUnitaireHt, tauxTva) {
  prixUnitaireHt = round2(prixUnitaireHt)
  return {
    designation,
    produit_nom: produitNom || '',
    quantite,
    prix_unitaire_ht: prixUnitaireHt,
    taux_tva: tauxTva,
    // Prix TTC ligne, arrondi UNE fois — même formule et même arrondi que
    // `builder.py _line_to_item` (`pu_ht × (1 + taux/100)`, round 2 déc.) :
    // c'est la valeur PARTAGÉE que les deux moteurs lisent telle quelle,
    // jamais recalculée séparément (ce serait une 8e chaîne monétaire —
    // exactement ce que `domain/argent.py` QJR49 documente comme le défaut
    // historique de ce dépôt).
    prix_unit_ttc: round2(prixUnitaireHt * (1 + tauxTva / 100)),
  }
}

function genResidentielOuIndustriel(id, marche) {
  const watt = pick(PANEL_WATTS)
  const kwcCible = round2(randInt(30, 200) / 10) // 3.0 .. 20.0 kWc (pas de 0,1)
  const nbPanneaux = Math.max(1, Math.round((kwcCible * 1000) / watt))
  const avecBatterie = rand() < 0.5
  const ville = pick(VILLES)
  const productibleOverride = rand() < 0.15
    ? pick([1450, 1600, 1750]) // 1600 = défaut historique société -> no-op
    : null

  const panel = panelLine(watt)
  const lines = [
    buildLigne(panel.designation, panel.produit_nom, nbPanneaux,
      randInt(1100, 1900), 10),
  ]

  let batteryKwh = null
  if (avecBatterie) {
    const useOffgrid = rand() < 0.25
    const kw = pick(INVERTER_KW)
    const tmpl = pick(useOffgrid ? OFFGRID_TEMPLATES : HYBRIDE_TEMPLATES)
    lines.push(buildLigne(tmpl(kw), '', 1, randInt(6000, 28000), 20))
    const battDes = batteryLine()
    const nBatt = randInt(1, 3)
    lines.push(buildLigne(battDes, '', nBatt, randInt(8000, 24000), 20))
    const m = /([\d.]+)\s*kWh/.exec(battDes)
    batteryKwh = m ? parseFloat(m[1]) * nBatt : 0
  } else {
    const kw = pick(INVERTER_KW)
    const tmpl = pick(RESEAU_TEMPLATES)
    const designation = tmpl(kw)
    lines.push(buildLigne(designation, '', 1, randInt(6000, 28000), 20))
    // QF9 — accessoires Huawei : présents SEULEMENT si l'onduleur du panier
    // est Huawei (sinon ils doivent être des orphelins retirés — hors
    // périmètre de ce test, non exercé ici, seulement leur CLASSIFICATION).
    if (/huawei/i.test(designation) && rand() < 0.6) {
      lines.push(buildLigne(SMART_METER_DESIGNATION, '', 1, randInt(300, 900), 20))
      lines.push(buildLigne(pick(WIFI_DONGLE_DESIGNATIONS), '', 1, randInt(150, 400), 20))
    }
  }
  lines.push(buildLigne(pick(STRUCTURE_DESIGNATIONS), '', 1, randInt(2000, 9000), 20))
  lines.push(buildLigne(pick(CABLE_DESIGNATIONS), '', 1, randInt(500, 2500), 20))

  const discountPct = pick([0, 0, 2, 2.5, 3, 3.5, 5, 5.5, 7, 7.5, 8, 10, 12])

  return {
    id, marche, ville, productible_override: productibleOverride,
    kwc: kwcCible, panel_w: watt, nb_panneaux: nbPanneaux,
    avec_batterie: avecBatterie, battery_kwh: batteryKwh,
    discount_pct: discountPct, hmt: null, debit: null, heures_pompage: null,
    lines,
  }
}

function genAgricole(id) {
  const hmt = randInt(15, 80)
  const debit = randInt(5, 40)
  const heures = pick([5, 6, 7, 8])
  const pumpCv = pick([3, 5, 7.5])
  const pumpKw = round2(pumpCv * 0.7355)
  const arrayKwc = round2(pumpKw * 1.4)
  const watt = pick(PANEL_WATTS)
  const nbPanneaux = Math.max(1, Math.round((arrayKwc * 1000) / watt))
  const ville = pick(VILLES)

  const panel = panelLine(watt)
  const lines = [
    buildLigne(panel.designation, panel.produit_nom, nbPanneaux,
      randInt(1100, 1900), 10),
    buildLigne(pick(PUMP_DESIGNATIONS), '', 1, randInt(8000, 22000), 20),
    buildLigne(pick(VARIATEUR_DESIGNATIONS), '', 1, randInt(4000, 12000), 20),
    buildLigne(AFFICHEUR_DESIGNATION, '', 1, randInt(400, 900), 20),
    buildLigne(pick(STRUCTURE_DESIGNATIONS), '', 1, randInt(1500, 6000), 20),
    buildLigne(pick(CABLE_DESIGNATIONS), '', 1, randInt(500, 2000), 20),
  ]
  const discountPct = pick([0, 0, 2, 3, 5, 7.5, 10])

  return {
    id, marche: 'agricole_pompage', ville, productible_override: null,
    kwc: arrayKwc, panel_w: watt, nb_panneaux: nbPanneaux,
    avec_batterie: false, battery_kwh: null,
    discount_pct: discountPct, hmt, debit, heures_pompage: heures,
    lines,
  }
}

function genCorpus(n) {
  const entries = []
  for (let i = 0; i < n; i += 1) {
    const id = `QAH3-${String(i).padStart(4, '0')}`
    const roll = rand()
    let entry
    if (roll < 0.50) entry = genResidentielOuIndustriel(id, 'residentiel')
    else if (roll < 0.75) entry = genResidentielOuIndustriel(id, 'industriel_commercial')
    else entry = genAgricole(id)
    entries.push(entry)
  }
  return entries
}

// ── CE QUE `solar.js` CALCULE sur une entrée — LE contrat (voir l'en-tête) ───
// Exportée pour que `solar.corpus.test.js` réutilise EXACTEMENT cette
// composition (aucune réimplémentation dupliquée du côté test).
export function computeExpectedForEntry(entry) {
  const classifications = entry.lines.map((l) => ({
    designation: l.designation,
    is_battery: isBattery(l.designation),
    is_hybrid_inverter: isHybridInverter(l.designation),
    is_reseau_inverter: isReseauInverter(l.designation),
    is_offgrid_inverter: isOffgridInverter(l.designation),
    is_any_inverter: isAnyInverter(l.designation),
    is_panel: isPanel(l.designation, l.produit_nom),
  }))

  // kWc dérivé des lignes — MÊME composition que `builder.py
  // panneaux_et_watt_lu` (voir l'en-tête, point 2) : premier panneau qui rend
  // un watt lisible fixe le watt, chaque ligne panneau compte dans nb_panneaux.
  let nbPanneaux = 0
  let watt = null
  for (const l of entry.lines) {
    if (isPanel(l.designation, l.produit_nom)) {
      nbPanneaux += Math.round(l.quantite)
      if (watt == null) {
        watt = parseWatt(l.designation) ?? parseWatt(l.produit_nom || '')
      }
    }
  }
  const kwcDesLignes = (nbPanneaux > 0 && watt)
    ? round2((nbPanneaux * watt) / 1000)
    : null

  const productible = productibleForCity(entry.ville, entry.productible_override)
  const productionAnnuelle = entry.kwc
    ? Math.round(entry.kwc * productible * PRODUCTIBLE_NET_FACTOR)
    : null

  const totals = optionTotalsTTC(entry.lines, entry.discount_pct)
  const totalTtc = entry.avec_batterie ? totals.totalAvec : totals.totalSans

  return {
    id: entry.id,
    classifications,
    nb_panneaux: nbPanneaux,
    watt,
    kwc_des_lignes: kwcDesLignes,
    productible,
    production_annuelle: productionAnnuelle,
    total_ttc: totalTtc,
  }
}

function main() {
  const entries = genCorpus(200)
  const expected = entries.map(computeExpectedForEntry)

  mkdirSync(FIXTURES_DIR, { recursive: true })
  writeFileSync(CORPUS_PATH, `${JSON.stringify({
    pact: 'PACT10',
    genere_par: 'frontend/scripts/solar_corpus.mjs',
    regeneration: "UNIQUEMENT par un humain qui a tranché une divergence — "
      + 'jamais par un agent pour repasser un test au vert (voir l\'en-tête '
      + 'du script).',
    seed: SEED,
    count: entries.length,
    entries,
  }, null, 2)}\n`)
  writeFileSync(EXPECTED_PATH, `${JSON.stringify({
    pact: 'PACT10',
    genere_par: 'frontend/scripts/solar_corpus.mjs (fonctions solar.js réelles)',
    regeneration: "UNIQUEMENT par un humain qui a tranché une divergence — "
      + 'jamais par un agent pour repasser un test au vert (voir l\'en-tête '
      + 'du script).',
    seed: SEED,
    count: expected.length,
    entries: expected,
  }, null, 2)}\n`)
  console.log(`solar_corpus: ${entries.length} entrées écrites dans\n  ${CORPUS_PATH}\n  ${EXPECTED_PATH}`)
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
if (isMain) {
  main()
}
