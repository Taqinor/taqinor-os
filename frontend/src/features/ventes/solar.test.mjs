// Parity tests for the solar generator math against the devis-simulator
// (source of truth). Run with: node --test src/features/ventes/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  DEFAULT_MONTHLY_BILLS, estimerMois, estimerPanneaux, formatMoney,
  computeROI, ttcFromHt, htFromTtc, optionTotalsTTC, autoFillLines, GHI,
  groupProduitsByCategory,
  KWH_PRICE, FALLBACK_KWH_PRICE, kwhFromBill, twoBillsSavings, monthlyBillFromKwh,
  ONEE_TRANCHES, AUTOCONSO_SANS, AUTOCONSO_AVEC, buildEtudeParamsChoice,
  multiPropertyPreviewTTC,
  productibleForCity, PRODUCTIBLE_PAR_VILLE, DEFAULT_PRODUCTIBLE,
  computeCashflowPayback,
} from './solar.js'

// Reflet du catalogue seedé (prix HT = TTC simulateur / 1.2, 2 décimales)
const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc) => ({ id: ++_id, nom, prix_vente: ht(ttc) })
const SEEDED = [
  P('Onduleur réseau Huawei 5kW Monophasé', 14000),
  P('Onduleur réseau Huawei 10kW Monophasé', 18000),
  P('Onduleur réseau Huawei 10kW Triphasé', 20000),
  P('Onduleur réseau Huawei 12kW Monophasé', 20000),
  P('Onduleur réseau Huawei 15kW Triphasé', 23000),
  P('Onduleur réseau Huawei 20kW Triphasé', 28000),
  P('Onduleur réseau Huawei 25kW Triphasé', 35000),
  P('Onduleur réseau Huawei 50kW Triphasé', 55000),
  P('Onduleur réseau Huawei 100kW Triphasé', 78000),
  P('Onduleur réseau Huawei 150kW Triphasé', 123000),
  P('Onduleur hybride Deye 5kW Monophasé', 17000),
  P('Onduleur hybride Deye 10kW Monophasé', 28000),
  P('Onduleur hybride Deye 10kW Triphasé', 28000),
  P('Onduleur hybride Deye 15kW Triphasé', 36000),
  P('Onduleur hybride Deye 20kW Triphasé', 48000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Panneau Jinko 710W', 1400),
  P('Batterie Deyness 5 kWh', 17000),
  P('Batterie Deyness 10 kWh', 30000),
  P('Batterie Lithium 5 kWh', 15500),
  P('Batterie Gel 2.2 kWh', 5000),
  P('Structures acier', 500),
  P('Structures aluminium', 850),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

const CLEAN_INT = (v) => Number.isInteger(v)

test('estimateur de factures : valeurs entières, mêmes que le simulateur', () => {
  const months = estimerMois(600, 400)
  assert.equal(months.length, 12)
  months.forEach(v => assert.ok(CLEAN_INT(v), `mois non entier: ${v}`))
  assert.deepEqual(months, [600, 567, 533, 500, 467, 433, 400, 400, 450, 500, 550, 600])
})

test('estimateur : été vide → 12 mois plats', () => {
  assert.deepEqual(estimerMois(500, 0), Array(12).fill(500))
})

test('factures par défaut : la série saisonnière du simulateur', () => {
  assert.deepEqual(DEFAULT_MONTHLY_BILLS,
    [500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480])
  DEFAULT_MONTHLY_BILLS.forEach(v => assert.ok(CLEAN_INT(v)))
})

test('suggestion panneaux : 8 par tranche de 900 MAD hiver', () => {
  assert.equal(estimerPanneaux(600), 0)
  assert.equal(estimerPanneaux(900), 8)
  assert.equal(estimerPanneaux(1900), 16)
})

test('D5 — ratio de dimensionnement éditable, défaut inchangé', () => {
  // Sans argument : exactement le comportement historique (8 par tranche).
  assert.equal(estimerPanneaux(1900), 16)
  // Ratio personnalisé : 10 par tranche de 900 MAD.
  assert.equal(estimerPanneaux(900, 10), 10)
  assert.equal(estimerPanneaux(1900, 10), 20)
  // Valeur invalide → repli sur 8 (jamais 0/NaN panneaux).
  assert.equal(estimerPanneaux(900, 0), 8)
  assert.equal(estimerPanneaux(900, undefined), 8)
})

test('formatMoney : toujours arrondi à l\'entier (jamais de partie fractionnaire)', () => {
  // Le séparateur de milliers dépend de l'ICU (espace ou point) — ce qui
  // compte est que la valeur formatée soit l'entier arrondi, sans fraction.
  for (const v of [0, 833.333, 19600.056, 1400.004, 121224]) {
    const s = formatMoney(v)
    assert.ok(s.endsWith(' MAD'))
    assert.equal(s.replace(/\D/g, ''), String(Math.round(v)),
      `valeur fractionnaire dans ${s}`)
  }
  assert.equal(formatMoney(null), '0 MAD')
})

test('prix TTC depuis le HT du stock : retombe sur le TTC catalogue exact', () => {
  for (const ttc of [1400, 14000, 20000, 17000, 500, 80, 1000, 4800, 5000]) {
    assert.equal(ttcFromHt(ht(ttc)), ttc)
  }
})

test('prix saisi librement : aller-retour TTC → HT stocké → TTC sans dérive', () => {
  // Un prix arbitraire tapé par l'utilisateur (pas un multiple de 10/100)
  // doit revenir exactement après enregistrement HT et réaffichage TTC.
  for (const typed of [1453, 999, 1, 7, 123457, 2849, 18351]) {
    const stockedHt = htFromTtc(typed)            // ce que la base enregistre
    assert.match(stockedHt, /^\d+\.\d{2}$/)        // 2 décimales (modèle)
    assert.equal(ttcFromHt(stockedHt), typed,
      `TTC ${typed} a dérivé via HT ${stockedHt}`)
  }
  // TVA non standard : même garantie
  assert.equal(Math.round(parseFloat(htFromTtc(1453, 10)) * 1.10), 1453)
})

test('factures saisies librement : utilisées telles quelles dans la simulation', () => {
  const typed = [517, 433.5, 601, 380, 360, 502, 707, 681, 580, 480, 430, 480]
  const roi = computeROI({
    kwp: 5, factures: typed, dayUsagePct: 60,
    totalSans: 50000, totalAvec: 80000, batteryKwh: 5,
  })
  // Aucune retouche : le graphique reçoit exactement les montants saisis
  assert.deepEqual(roi.monthly_detail.map(d => d.facture), typed)
})

test('remise saisie librement (ex. 12.5 %) : appliquée exactement', () => {
  const lines = [{ designation: 'Transport', quantite: '1', prix_unit_ttc: '1000' }]
  const { totalSans } = optionTotalsTTC(lines, '12.5')
  assert.equal(totalSans, 875) // 1000 × (1 − 0.125), arrondi simulateur
})

test('sélecteur produits : groupé selon les catégories du catalogue simulateur', () => {
  const groups = groupProduitsByCategory(
    [...SEEDED, { id: 999, nom: 'Câble solaire 6mm² (100m)', prix_vente: '850' }])
  const labels = groups.map(g => g.label)
  assert.deepEqual(labels, [
    'Onduleur Injection', 'Onduleur Hybride', 'Panneaux', 'Batterie',
    'Structures acier', 'Structures aluminium', 'Socles', 'Smart Meter',
    'Wifi Dongle', 'Accessoires', 'Tableau De Protection AC/DC',
    'Installation', 'Transport',
    'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 'Autres',
  ])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Onduleur Injection').items.length, 10)
  assert.equal(by('Onduleur Hybride').items.length, 5)
  assert.equal(by('Panneaux').items.length, 2)
  assert.equal(by('Batterie').items.length, 4)
  assert.equal(by('Structures acier').items.length, 1)
  assert.equal(by('Structures aluminium').items.length, 1)
  // produit non solaire → groupe Autres
  assert.equal(by('Autres').items[0].nom, 'Câble solaire 6mm² (100m)')
})

test('garde-fou : plus aucune contrainte step restrictive sur l\'écran', () => {
  const jsx = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '../../pages/ventes/DevisGenerator.jsx'),
    'utf-8',
  )
  assert.ok(jsx.includes('noValidate'),
    'le formulaire doit être noValidate (aucun rejet navigateur)')
  for (const bad of ['step="100"', 'step="10"', 'step="1"', 'step="0.01"']) {
    assert.ok(!jsx.includes(bad), `contrainte de saisie restrictive trouvée : ${bad}`)
  }
  // Seul le curseur (type="range") garde un pas ; aucun champ nombre n'en a.
  const numberSteps = jsx.split('type="number"').slice(1)
    .map(chunk => /step="([^"]+)"/.exec(chunk)?.[1])
  numberSteps.forEach(s => assert.equal(s, 'any'))
})

test('garde-fou : choisir un lead ne réinitialise JAMAIS le mode choisi', () => {
  const jsx = readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '../../pages/ventes/DevisGenerator.jsx'),
    'utf-8',
  )
  // Le pré-réglage du mode depuis le lead doit être conditionné au fait que
  // l'utilisateur n'a PAS déjà touché le mode (modeTouched).
  assert.ok(/!modeTouched\.current[\s\S]{0,120}LEAD_TYPE_TO_MODE/.test(jsx),
    'applyLead doit vérifier modeTouched avant de changer le mode')
  assert.ok(jsx.includes('modeTouched.current = true'),
    'le sélecteur de mode doit marquer le choix utilisateur')
  // Et l'échec de création ne montre jamais de JSON brut
  assert.ok(!jsx.includes('JSON.stringify(err)'),
    'plus de JSON brut affiché à l\'utilisateur en cas d\'échec')
})

test('ROI : production GHI × kWc × 0.8', () => {
  const roi = computeROI({
    kwp: 9.94, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 65040, totalAvec: 103040, batteryKwh: 10,
  })
  const sumGhi = GHI.reduce((a, b) => a + b, 0)
  assert.ok(Math.abs(roi.production_annuelle_kwh - sumGhi * 9.94 * 0.8) < 0.1)
  // économies avec batterie = sans + 60 MAD/kWh/mois
  for (let i = 0; i < 12; i++) {
    assert.ok(Math.abs(roi.eco_avec_monthly[i] - roi.eco_sans_monthly[i] - 600) < 0.001)
  }
  assert.ok(roi.payback_sans > 0 && roi.payback_avec > 0)
})

test('D5 — tarif ONEE et rendement éditables, défaut strictement inchangé', () => {
  const base = {
    kwp: 9.94, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 65040, totalAvec: 103040, batteryKwh: 0,
  }
  // Sans override : identique à la version historique (parité).
  const def = computeROI(base)
  const sumGhi = GHI.reduce((a, b) => a + b, 0)
  assert.ok(Math.abs(def.production_annuelle_kwh - sumGhi * 9.94 * 0.8) < 0.1)
  // Tarif ONEE doublé → économies (sans batterie) doublées exactement.
  const dbl = computeROI({ ...base, kwhPrice: 3.5 })
  assert.ok(Math.abs(dbl.eco_annuelle_sans - def.eco_annuelle_sans * 2) < 1)
  // Rendement réduit de moitié → production de moitié.
  const half = computeROI({ ...base, efficiency: 0.4 })
  assert.ok(Math.abs(half.production_annuelle_kwh - def.production_annuelle_kwh / 2) < 0.2)
  // Override invalide (0/NaN) → repli sur les constantes (parité).
  const fallback = computeROI({ ...base, kwhPrice: 0, efficiency: -1 })
  assert.equal(fallback.production_annuelle_kwh, def.production_annuelle_kwh)
})

test('auto-fill 14 panneaux × 710 W : équipements et prix identiques au simulateur', () => {
  const kwp = 14 * 710 / 1000 // 9.94
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))

  // Onduleur réseau : plus petit ≥ 80 % de 9.94 → 10 kW, Triphasé préféré (≥10 kW)
  const reseau = rows.find(r => r.designation.includes('réseau'))
  assert.equal(reseau.designation, 'Onduleur réseau Huawei 10kW Triphasé')
  assert.equal(reseau.quantite, 1)
  assert.equal(reseau.prix_unit_ttc, 20000)

  // Onduleur hybride : Deye 10 kW Triphasé
  const hyb = rows.find(r => r.designation.includes('hybride'))
  assert.equal(hyb.designation, 'Onduleur hybride Deye 10kW Triphasé')
  assert.equal(hyb.prix_unit_ttc, 28000)

  // Smart Meter + Wifi Dongle : qté 1 dès qu'un onduleur réseau est retenu
  assert.equal(by('Smart Meter').quantite, 1)
  assert.equal(by('Smart Meter').prix_unit_ttc, 1800)
  assert.equal(by('Wifi').quantite, 1)
  assert.equal(by('Wifi').prix_unit_ttc, 1200)

  // Panneaux : Canadien Solar 710 W × 14 à 1 400 MAD
  const pan = rows.find(r => r.designation.includes('Panneau'))
  assert.equal(pan.designation, 'Panneau Canadien Solar 710W')
  assert.equal(pan.quantite, 14)
  assert.equal(pan.prix_unit_ttc, 1400)

  // Batteries : cible 10 kWh → 1 × Deyness 10 kWh, 0 × 5 kWh
  assert.equal(by('Deyness 10').quantite, 1)
  assert.equal(by('Deyness 10').prix_unit_ttc, 30000)
  assert.equal(by('Deyness 5').quantite, 0)

  // Structures acier ×14 (500), aluminium 0 ; Socles ×28 (80)
  assert.equal(by('acier').quantite, 14)
  assert.equal(by('acier').prix_unit_ttc, 500)
  assert.equal(by('aluminium').quantite, 0)
  assert.equal(by('Socles').quantite, 28)
  assert.equal(by('Socles').prix_unit_ttc, 80)

  // Prix indexés sur la puissance : blocs de 5 kWc → 2 blocs
  assert.equal(by('Accessoires').prix_unit_ttc, 2000)
  assert.equal(by('Tableau').prix_unit_ttc, 3000)
  assert.equal(by('Installation').prix_unit_ttc, 7200)
  assert.equal(by('Transport').prix_unit_ttc, 1000)
  assert.equal(by('Suivi').quantite, 0)

  // Tous les prix de la table sont des entiers (aucune décimale à l'écran)
  rows.forEach(r => assert.ok(CLEAN_INT(r.prix_unit_ttc), `prix non entier: ${r.designation} ${r.prix_unit_ttc}`))

  // Totaux par option, exactement comme updateTotals du simulateur
  const totals = optionTotalsTTC(rows, 0)
  assert.equal(totals.totalSansBrut, 65040)
  assert.equal(totals.totalAvecBrut, 103040)
})

test('auto-fill 24 panneaux × 710 W : batterie composée 10+5, structures alu', () => {
  const kwp = 24 * 710 / 1000 // 17.04 → cible batterie 15 kWh
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'aluminium' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Deyness 10').quantite, 1)
  assert.equal(by('Deyness 5').quantite, 1)
  assert.equal(by('aluminium').quantite, 24)
  assert.equal(by('aluminium').prix_unit_ttc, 850)
  assert.equal(by('acier').quantite, 0)
  // blocs = round(17.04/5) = 3
  assert.equal(by('Accessoires').prix_unit_ttc, 3000)
  assert.equal(by('Tableau').prix_unit_ttc, 4500)
  assert.equal(by('Installation').prix_unit_ttc, 9600)
  // réseau : plus petit ≥ 13.63 → Huawei 15kW Triphasé
  assert.equal(rows.find(r => r.designation.includes('réseau')).designation,
    'Onduleur réseau Huawei 15kW Triphasé')
})

test('auto-fill petit système 5 panneaux : onduleur 5 kW Monophasé préféré', () => {
  const kwp = 5 * 710 / 1000 // 3.55 → seuil 2.84
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'acier' })
  assert.equal(rows.find(r => r.designation.includes('réseau')).designation,
    'Onduleur réseau Huawei 5kW Monophasé')
  assert.equal(rows.find(r => r.designation.includes('hybride')).designation,
    'Onduleur hybride Deye 5kW Monophasé')
  // cible batterie : max(5, round(3.55/5)*5) = 5 → 1 × Deyness 5 kWh
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Deyness 5').quantite, 1)
  assert.equal(by('Deyness 10').quantite, 0)
})

// ── QX19 — autoFillLines surface le wattage RÉEL + nb panneaux (anti-mismatch)
test('QX19 — autoFillLines expose actualPanelW / nbPanneaux / kwcReel', () => {
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'acier' })
  assert.equal(rows.actualPanelW, 710)     // catalogue a le 710 W demandé
  assert.equal(rows.nbPanneaux, 14)
  assert.equal(rows.kwcReel, Math.round(14 * 710 / 10) / 100)
})

test('QX19 — nbPanneaux override (taille souhaitée kWc) pilote le nb de panneaux', () => {
  // taille souhaitée 7.1 kWc → panneauxPourKwc(7.1,710) = 10 panneaux
  const rows = autoFillLines(SEEDED, { kwp: 7.1, panelW: 710, structureType: 'acier', nbPanneaux: 10 })
  assert.equal(rows.nbPanneaux, 10)
  // la ligne panneau (nom catalogue contient « Panneau ») porte la qté override
  const panelRow = rows.find(r => /panneau/i.test(r.designation))
  assert.equal(panelRow.quantite, 10)
})

test('QX19 — substitution de wattage : actualPanelW reflète le panneau retenu', () => {
  // catalogue SANS panneau 710 W → substitution vers le plus proche (550 W)
  const CAT550 = SEEDED.filter(p => !/710/.test(p.nom))
    .concat([{ id: 9001, nom: 'Panneau mono 550W', prix_vente: ht(1400) }])
  const rows = autoFillLines(CAT550, { kwp: 7.1, panelW: 710, structureType: 'acier' })
  assert.equal(rows.actualPanelW, 550)     // wattage RÉEL du panneau substitué
  assert.notEqual(rows.actualPanelW, 710)  // divergence détectable côté écran
})

// ── QF8 — Smart Meter + Clé Wifi UNIQUEMENT sur onduleur Huawei ─────────────
test('QF8 — catalogue 100% Deye (réseau + hybride) : Smart Meter et Wifi Dongle qté 0', () => {
  const DEYE_ONLY = [
    P('Onduleur réseau Deye 10kW Triphasé', 18000),
    P('Onduleur hybride Deye 10kW Triphasé', 28000),
    P('Panneau Jinko 710W', 1400),
    P('Batterie Deyness 10 kWh', 30000),
    P('Structures acier', 500),
    P('Socles', 80),
    P('Smart Meter', 1800),
    P('Wifi Dongle', 1200),
    P('Accessoires', 2000),
    P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800),
    P('Transport', 1000),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(DEYE_ONLY, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Smart Meter').quantite, 0)
  assert.equal(by('Wifi').quantite, 0)
})

test('QF8 — réseau Huawei mais hybride Deye : Smart Meter/Wifi attachés (réseau Huawei suffit)', () => {
  const MIXED = [
    P('Onduleur réseau Huawei 10kW Triphasé', 20000),
    P('Onduleur hybride Deye 10kW Triphasé', 28000),
    P('Panneau Jinko 710W', 1400),
    P('Smart Meter', 1800),
    P('Wifi Dongle', 1200),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(MIXED, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Smart Meter').quantite, 1)
  assert.equal(by('Wifi').quantite, 1)
})

test('QF8 — réseau Deye mais hybride Huawei : Smart Meter/Wifi attachés (hybride Huawei suffit)', () => {
  const MIXED = [
    P('Onduleur réseau Deye 10kW Triphasé', 18000),
    P('Onduleur hybride Huawei 10kW Triphasé', 30000),
    P('Panneau Jinko 710W', 1400),
    P('Smart Meter', 1800),
    P('Wifi Dongle', 1200),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(MIXED, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Smart Meter').quantite, 1)
  assert.equal(by('Wifi').quantite, 1)
})

// ══ Multi-marchés ═════════════════════════════════════════════════════════════
import {
  computeEtudeIndustrielle, computePompage, autoFillPompage,
  prixParKwc, discountForTarget, computeBuyCost, CV_TO_KW,
  expectedTvaForDesignation,
} from './solar.js'

const POMPAGE_FIXTURE = [
  P('Pompe immergée solaire 3 CV Monophasé', 6500),
  P('Pompe immergée solaire 5.5 CV Triphasé', 11000),
  P('Pompe immergée solaire 7.5 CV Triphasé', 14500),
  P('Pompe de surface solaire 1.5 CV Monophasé', 3000),
  P('Variateur pompage solaire 3 CV Triphasé (coffret complet)', 4800),
  P('Variateur pompage solaire 5.5 CV Triphasé (coffret complet)', 6500),
  P('Variateur pompage solaire 7.5 CV Triphasé (coffret complet)', 8000),
  P('Câble solaire 6mm² (au mètre)', 13),
].map((p, i) => ({
  ...p,
  pompe_cv: ['3', '5.5', '7.5', '1.5', '3', '5.5', '7.5', null][i],
}))

test('étude industrielle : taux autoconsommation / couverture cohérents', () => {
  // 50 kWc, conso 10 000 kWh/mois, 80 % diurne
  const e = computeEtudeIndustrielle({
    kwp: 50, consoMensuelleKwh: 10000, dayUsagePct: 80, totalTtc: 450000,
  })
  const prodA = GHI.reduce((a, b) => a + b, 0) * 50 * 0.8
  assert.ok(Math.abs(e.production_annuelle - Math.round(prodA)) <= 1)
  assert.equal(e.conso_annuelle, 120000)
  // autoconsommé = min(prod, conso×0.8) ; ici conso diurne 96 000 > prod (~62 811)
  // → tout est autoconsommé : taux autoconso 100 %, couverture = prod/conso
  assert.equal(e.taux_autoconso, 100)
  assert.ok(Math.abs(e.taux_couverture - (prodA / 120000 * 100)) < 0.2)
  assert.ok(Math.abs(e.economies_annuelles - Math.round(prodA * 1.75)) <= 2)
  assert.equal(e.prix_kwc, 9000)
  assert.equal(e.prod_mensuelle.length, 12)
  assert.equal(e.conso_mensuelle.length, 12)
})

// ── DC3 — étude industrielle prend kwhPrice/efficiency (comme computeROI) ──────
test('DC3 étude industrielle : kwhPrice/efficiency de la société pilotent le calcul', () => {
  const base = { kwp: 50, consoMensuelleKwh: 10000, dayUsagePct: 80, totalTtc: 450000 }
  const def = computeEtudeIndustrielle(base)
  // Tarif ONEE doublé → économies doublées exactement (autoconsommé inchangé).
  const dbl = computeEtudeIndustrielle({ ...base, kwhPrice: 3.5 })
  assert.ok(Math.abs(dbl.economies_annuelles - def.economies_annuelles * 2) <= 2)
  // Rendement réduit de moitié → production annuelle de moitié.
  const half = computeEtudeIndustrielle({ ...base, efficiency: 0.4 })
  assert.ok(Math.abs(half.production_annuelle - def.production_annuelle / 2) <= 1)
  // Override invalide (0 / NaN) → repli sur les constantes historiques.
  const fb = computeEtudeIndustrielle({ ...base, kwhPrice: 0, efficiency: -1 })
  assert.equal(fb.production_annuelle, def.production_annuelle)
  assert.equal(fb.economies_annuelles, def.economies_annuelles)
})

test('pompage : 5.5 CV tri → variateur 5.5 tri + champ ≈1.4× pompe, sans batterie/onduleur', () => {
  const dims = computePompage(5.5)
  assert.ok(Math.abs(dims.kw - 5.5 * CV_TO_KW) < 0.01)
  // champ 1.4× pompe ∈ [1.3, 1.5] × kW
  assert.ok(dims.champKw >= dims.kw * 1.3 && dims.champKw <= dims.kw * 1.5)
  assert.equal(dims.nbPanneaux, Math.ceil(dims.champKw * 1000 / 710))

  const rows = autoFillPompage(POMPAGE_FIXTURE.concat(SEEDED), {
    cv: '5.5', alim: 'tri', typePompe: 'immergee',
    distance: '35', structureType: 'acier',
  })
  const names = rows.map(r => r.designation)
  assert.ok(names.includes('Pompe immergée solaire 5.5 CV Triphasé'))
  assert.ok(names.includes('Variateur pompage solaire 5.5 CV Triphasé (coffret complet)'))
  // câble à la distance
  const cable = rows.find(r => r.designation.includes('Câble'))
  assert.equal(Number(cable.quantite), 35)
  // ni batterie, ni onduleur réseau/hybride
  assert.ok(!names.some(n => /batterie/i.test(n)))
  assert.ok(!names.some(n => /onduleur/i.test(n)))
  // panneaux 710 du catalogue
  const pan = rows.find(r => /panneau/i.test(r.designation))
  assert.equal(Number(pan.quantite), dims.nbPanneaux)
})

// ══ Courbes de pompe + VEICHI (matériel réel) ════════════════════════════════
import {
  debitAtHmt, selectPompeByCurve, selectVariateurVeichi,
  findAfficheurVariateur, pompageSelection, HEURES_POMPAGE_DEFAUT,
  tensionOf, tensionForAlim, isPompe,
} from './solar.js'

test('QX20 — isPompe classe une pompe, pas un panneau/onduleur', () => {
  assert.equal(isPompe('Pompe immergée OSP 30/8'), true)
  assert.equal(isPompe('Pompe de surface'), true)
  assert.equal(isPompe('Panneau Canadien Solar 710W'), false)
  assert.equal(isPompe('Onduleur réseau Huawei 10kW'), false)
  assert.equal(isPompe(''), false)
})

const OSP_CURVE_30_8 = { debits_m3h: [0, 12, 24, 30, 36, 39], hmt_m: [91, 85, 70, 60, 43, 34] }
const OSP_CURVE_30_13 = { debits_m3h: [0, 12, 24, 30, 36, 39], hmt_m: [148, 138, 114, 98, 70, 55] }

const VEICHI_FIXTURE = [
  { id: 901, nom: 'AFFICHEUR VARIATEUR SI22', prix_vente: '350.00', pompe_kw: null, tension_v: null },
  { id: 902, nom: 'VARIATEUR VEICHI SI22 2.2KW 220V', prix_vente: '1316.67', pompe_kw: '2.2', tension_v: 220 },
  { id: 903, nom: 'VARIATEUR VEICHI SI23 2.2KW 220V', prix_vente: '2108.33', pompe_kw: '2.2', tension_v: 220 },
  { id: 904, nom: 'VARIATEUR VEICHI SI23 5.5KW 380V', prix_vente: '2708.33', pompe_kw: '5.5', tension_v: 380 },
  { id: 905, nom: 'VARIATEUR VEICHI SI23 7.5KW 380V', prix_vente: '3333.33', pompe_kw: '7.5', tension_v: 380 },
  { id: 906, nom: 'VARIATEUR VEICHI SI23 11KW 380V', prix_vente: '4125.00', pompe_kw: '11', tension_v: 380 },
]

const ospPump = (overrides = {}) => ({
  id: 950, nom: 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',
  prix_vente: '12500.00', pompe_cv: '10', pompe_kw: '7.5', tension_v: 380,
  courbe_pompe: OSP_CURVE_30_8, ...overrides,
})
const ospPump13 = (overrides = {}) => ({
  id: 951, nom: 'Pompe immergée OSP 30/13 — 15 CV / 11 kW (3", 380V)',
  prix_vente: '0.00', pompe_cv: '15', pompe_kw: '11', tension_v: 380,
  courbe_pompe: OSP_CURVE_30_13, ...overrides,
})

test('courbe : débit interpolé à la HMT (points exacts, interpolation, bornes)', () => {
  assert.equal(debitAtHmt(OSP_CURVE_30_8, 60), 30)      // point exact
  assert.equal(debitAtHmt(OSP_CURVE_30_8, 65), 27)      // interpolation 70→60
  assert.equal(debitAtHmt(OSP_CURVE_30_8, 91), 0)       // HMT max → débit nul
  assert.equal(debitAtHmt(OSP_CURVE_30_8, 120), 0)      // au-delà de la pompe
  assert.equal(debitAtHmt(OSP_CURVE_30_8, 20), 39)      // borné au dernier point
  assert.equal(debitAtHmt(null, 60), null)              // pas de courbe → null
})

test('sélection pompe : HMT 60 m + débit 30 m³/h → OSP 30/8 (la plus petite qui suffit)', () => {
  const produits = [ospPump(), ospPump13({ prix_vente: '15000.00' })]
  const sel = selectPompeByCurve(produits, { hmt: '60', debit: '30', typePompe: 'immergee' })
  assert.equal(sel.pump.id, 950)
  assert.equal(sel.kw, 7.5)
  assert.equal(sel.debitHmt, 30)
  assert.deepEqual(sel.sansPrix, [])
})

test('pompes sans prix : jamais chiffrées — signalées à la place', () => {
  const produits = [ospPump({ prix_vente: '0.00' }), ospPump13()]
  const sel = selectPompeByCurve(produits, { hmt: '60', debit: '30', typePompe: 'immergee' })
  assert.equal(sel.pump, null)
  assert.ok(sel.sansPrix.length >= 1)
  assert.ok(sel.sansPrix[0].includes('OSP'))
  // …et l'auto-fill n'ajoute AUCUNE ligne pompe dans ce cas
  const rows = autoFillPompage(produits.concat(VEICHI_FIXTURE, SEEDED), {
    cv: '', alim: 'tri', typePompe: 'immergee', distance: '20',
    structureType: 'acier', hmt: '60', debit: '30', heures: '7',
  })
  assert.ok(!rows.some(r => /OSP|pompe/i.test(r.designation)))
})

test('variateur VEICHI : plus petit kW suffisant, tension assortie, jamais l\'afficheur', () => {
  const v = selectVariateurVeichi(VEICHI_FIXTURE, 7.5, 'tri')
  assert.equal(v.nom, 'VARIATEUR VEICHI SI23 7.5KW 380V')
  // pompe mono 1.1 kW → 220 V, le moins cher des 2.2 kW (SI22)
  const v220 = selectVariateurVeichi(VEICHI_FIXTURE, 1.1, 'mono')
  assert.equal(v220.nom, 'VARIATEUR VEICHI SI22 2.2KW 220V')
  // l'afficheur (sans kW) n'est jamais candidat
  assert.ok(!/afficheur/i.test(v.nom) && !/afficheur/i.test(v220.nom))
  assert.equal(findAfficheurVariateur(VEICHI_FIXTURE).id, 901)
})

test('m³/jour = débit à la HMT × heures de pompage (défaut 7 h)', () => {
  assert.equal(HEURES_POMPAGE_DEFAUT, 7)
  const sel = pompageSelection([ospPump()], {
    cv: '', typePompe: 'immergee', hmt: '60', debit: '30', heures: '7',
  })
  assert.equal(sel.mode, 'courbe')
  assert.equal(sel.m3Jour, 210)              // 30 m³/h × 7 h
  // champ PV ≈ 1.4 × kW réels de la pompe
  assert.ok(sel.dims.champKw >= sel.kw * 1.3 && sel.dims.champKw <= sel.kw * 1.5)
  // sans heures valides → pas de m³/jour inventé
  const sel0 = pompageSelection([ospPump()], {
    cv: '', typePompe: 'immergee', hmt: '60', debit: '30', heures: '',
  })
  assert.equal(sel0.m3Jour, null)
})

test('auto-fill courbe complet : pompe OSP + VEICHI assorti + afficheur, sans onduleur', () => {
  const produits = [ospPump()].concat(VEICHI_FIXTURE, SEEDED)
  const rows = autoFillPompage(produits, {
    cv: '', alim: 'tri', typePompe: 'immergee', distance: '40',
    structureType: 'acier', hmt: '60', debit: '30', heures: '7',
  })
  const names = rows.map(r => r.designation)
  assert.ok(names.some(n => n.includes('OSP 30/8')))
  assert.ok(names.includes('VARIATEUR VEICHI SI23 7.5KW 380V'))
  const aff = rows.find(r => /AFFICHEUR/i.test(r.designation))
  assert.equal(Number(aff.quantite), 1)      // afficheur par défaut (supprimable)
  assert.ok(!names.some(n => /onduleur/i.test(n)))
  assert.ok(!names.some(n => /batterie/i.test(n)))
})

// ══ Réforme TVA 2024–2026 : 10 % panneaux PV, 20 % le reste ═════════════════
import { ttcFromHt as _ttc, htFromTtc as _htf, tauxTvaOf } from './solar.js'

test('TVA 10 % panneau : aller-retour TTC↔HT lossless (1 400 ↔ 1 272,73)', () => {
  assert.equal(_htf(1400, 10), '1272.73')
  assert.equal(_ttc('1272.73', 10), 1400)
  // taux du produit : 10 pour un panneau seedé, 20 par défaut
  assert.equal(tauxTvaOf({ tva: '10.00' }), 10)
  assert.equal(tauxTvaOf({ tva: '20.00' }), 20)
  assert.equal(tauxTvaOf({}), 20)
  assert.equal(tauxTvaOf(null), 20)
  // tout TTC tapé à la dirham près reste exact aux deux taux
  for (const ttc of [999, 1400, 13571, 250000]) {
    assert.equal(_ttc(_htf(ttc, 10), 10), ttc)
    assert.equal(_ttc(_htf(ttc, 20), 20), ttc)
  }
})

test('prix/kWc + prix cible appliqué via remise transparente', () => {
  assert.equal(prixParKwc(99400, 9.94), 10000)
  // cible 9 000 MAD/kWc sur un brut de 99 400 → remise ≈ 9.96 %
  const pct = discountForTarget(9000, 9.94, 99400)
  assert.ok(Math.abs(pct - (1 - 9000 * 9.94 / 99400) * 100) < 0.01)
  // le total remisé atteint la cible (à l'arrondi près)
  const totalApres = 99400 * (1 - pct / 100)
  assert.ok(Math.abs(totalApres - 9000 * 9.94) < 1)
})

test('marge : affichée seulement quand des prix d\'achat existent', () => {
  const produits = [
    { id: 1, nom: 'Panneau X', prix_vente: '1166.67', prix_achat: '0' },
    { id: 2, nom: 'Onduleur Y', prix_vente: '16666.67', prix_achat: '0' },
  ]
  const lines = [
    { produit: '1', designation: 'Panneau X', quantite: '10', prix_unit_ttc: '1400' },
    { produit: '2', designation: 'Onduleur Y', quantite: '1', prix_unit_ttc: '20000' },
  ]
  // aucun prix d'achat → null (rien à afficher)
  assert.equal(computeBuyCost(lines, produits), null)
  // un prix d'achat renseigné → coût TTC de cette ligne
  produits[0].prix_achat = '1000'
  assert.equal(computeBuyCost(lines, produits), Math.round(10 * 1000 * 1.2))
})

// ── DC4 — TVA panneaux société surcharge le défaut, sinon 10 %/20 % ───────────
test('DC4 expectedTvaForDesignation : config société surcharge, défauts sinon', () => {
  // Défauts réforme : panneau 10, autre 20
  assert.equal(expectedTvaForDesignation('Panneau 710W'), 10)
  assert.equal(expectedTvaForDesignation('Onduleur réseau'), 20)
  // Config société : panneaux 7, standard 19
  const cfg = { tvaPanneaux: 7, tvaStandard: 19 }
  assert.equal(expectedTvaForDesignation('Panneau 710W', cfg), 7)
  assert.equal(expectedTvaForDesignation('Onduleur', cfg), 19)
  // Config invalide (0/NaN) → repli défauts
  assert.equal(expectedTvaForDesignation('Panneau', { tvaPanneaux: 0 }), 10)
})

// ── DC6/DC7 — tauxTvaOf : produit.tva autoritaire, repli sur standard société ─
test('DC6/DC7 tauxTvaOf : Produit.tva prioritaire, repli standard société', () => {
  // DC7 — produit.tva renseigné = autoritaire, ignore le standard société
  assert.equal(tauxTvaOf({ tva: '10' }, 19), 10)
  assert.equal(tauxTvaOf({ tva: '20' }), 20)
  // DC6 — sans taux produit, repli sur le standard société (défaut 20)
  assert.equal(tauxTvaOf({}, 19), 19)
  assert.equal(tauxTvaOf({}), 20)
  // repli invalide (0) → 20
  assert.equal(tauxTvaOf({}, 0), 20)
})

// ── QF4/QF5 — miroir JS du modèle « deux factures » par tranche ─────────────
// Valeurs de référence calculées directement avec le module Python réel
// (apps/ventes/quote_engine/pricing.py) pour garantir la parité écran == PDF.
test('QF5 — tarif de repli unifié : KWH_PRICE (CompanyProfile) vs FALLBACK_KWH_PRICE (ultime repli backend)', () => {
  assert.equal(KWH_PRICE, 1.75) // CompanyProfile.onee_tarif_kwh défaut (parametres/selectors.py)
  assert.equal(FALLBACK_KWH_PRICE, 1.20) // pricing.py _FALLBACK_KWH_PRICE (miroir exact)
})

test('QF4 — monthlyBillFromKwh : barème ONEE par tranche (300 kWh/mois)', () => {
  // QX38 — barème ONEE aligné (plafonds 100/250/400/∞) : 300 kWh/mois tombe
  // dans la bande 251-400. Référence pricing.py _monthly_bill_from_kwh(300).
  assert.ok(Math.abs(monthlyBillFromKwh(300, ONEE_TRANCHES) - 306.545) < 1e-9)
})

test('QF4 — kwhFromBill : inverse du barème ONEE (850 MAD → 698.4 kWh/mois)', () => {
  // QX38 — barème ONEE aligné (plafonds 100/250/400/∞). Parité pricing.py.
  const r = kwhFromBill(850, 'onee')
  assert.equal(r.kwhMensuel, 698.4)
  assert.equal(r.approximatif, false)
  assert.equal(r.estimation, false)
})

test('QF4 — kwhFromBill : distributeur privé (Lydec) marqué approximatif', () => {
  const r = kwhFromBill(500, 'lydec')
  assert.equal(r.kwhMensuel, 400.0)
  assert.equal(r.approximatif, true)
})

test('QF4 — kwhFromBill : sans distributeur connu → repli FALLBACK_KWH_PRICE, étiqueté estimation', () => {
  const r = kwhFromBill(120, 'inconnu')
  assert.equal(r.kwhMensuel, Math.round((120 / FALLBACK_KWH_PRICE) * 10) / 10)
  assert.equal(r.estimation, true)
})

test('QF4 — kwhFromBill : facture vide → 0 kWh, estimation', () => {
  const r = kwhFromBill(0, 'onee')
  assert.equal(r.kwhMensuel, 0)
  assert.equal(r.estimation, true)
})

test('QF2/QF5 — twoBillsSavings : économie réelle par tranche (ratio 0.60, sans batterie)', () => {
  // QX38 — barème ONEE aligné (plafonds 100/250/400/∞). Référence :
  // pricing.py two_bills_savings(6000, 7200, 0.6, utility='onee').
  const r = twoBillsSavings(6000, 7200, 0.6, 'onee')
  assert.deepEqual(r, {
    factureSans: 8544, factureAvec: 3679, economie: 4865, autoconsoKwh: 3600,
  })
})

test('QF2/QF5 — twoBillsSavings : économie réelle par tranche (ratio 0.85, avec batterie)', () => {
  // QX38 — barème ONEE aligné (plafonds 100/250/400/∞). Référence :
  // pricing.py two_bills_savings(6000, 7200, 0.85, utility='onee').
  const r = twoBillsSavings(6000, 7200, 0.85, 'onee')
  assert.deepEqual(r, {
    factureSans: 8544, factureAvec: 2004, economie: 6540, autoconsoKwh: 5100,
  })
})

test('twoBillsSavings : dégrade en null sans donnée réelle (jamais un chiffre inventé)', () => {
  assert.equal(twoBillsSavings(0, 7200, 0.6, 'onee'), null) // pas de production
  assert.equal(twoBillsSavings(6000, 0, 0.6, 'onee'), null) // pas de conso
  assert.equal(twoBillsSavings(6000, 7200, 0, 'onee'), null) // pas de ratio
  assert.equal(twoBillsSavings(6000, 7200, 0.6, 'inconnu'), null) // pas de barème
})

// ── QX38 — productible canonique PVGIS par ville (miroir backend) ────────────
test('QX38 — productibleForCity : PVGIS par ville, repli central, override société', () => {
  assert.equal(productibleForCity('Agadir'), 1687)
  assert.equal(productibleForCity('agadir'), 1687)
  assert.equal(productibleForCity('Casablanca'), PRODUCTIBLE_PAR_VILLE.casablanca)
  // ville inconnue → repli central (jamais un chiffre inventé)
  assert.equal(productibleForCity('Oujda'), DEFAULT_PRODUCTIBLE)
  // alias secondaire → ville de référence
  assert.equal(productibleForCity('Kenitra'), PRODUCTIBLE_PAR_VILLE.rabat)
  // override = défaut historique 1600 → on lit le PVGIS de la ville
  assert.equal(productibleForCity('Agadir', 1600), 1687)
  // override société explicite (≠ 1600) → il prime
  assert.equal(productibleForCity('Agadir', 1750), 1750)
})

test('QX38 — computeROI : production = productible × kwp (parité PDF/web)', () => {
  const kwp = 7.1
  const roi = computeROI({
    kwp, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 80000, totalAvec: 100000, batteryKwh: 0,
    productible: productibleForCity('Agadir'),
  })
  // production annuelle = 1687 × 7.1 (répartie par forme GHI, somme = total)
  assert.equal(Math.round(roi.production_annuelle_kwh), Math.round(1687 * kwp))
})

// ── QX39 — cashflow 25 ans honnête (miroir backend pricing.py) ──────────────
test('QX39 — computeCashflowPayback : croisement du cumul à zéro (parité backend)', () => {
  const cf = computeCashflowPayback(50000, 10000)
  assert.equal(cf.cumulative.length, 25)
  assert.ok(cf.paybackYears > 0 && cf.paybackYears < 25)
  assert.ok(cf.cumulative[0] < 0)                 // année 1 encore négatif
  assert.ok(cf.cumulative[cf.cumulative.length - 1] > 0) // rentabilisé à 25 ans
  assert.ok(cf.netGain > 0)
})

test('QX39 — computeCashflowPayback : dégénéré → payback null', () => {
  assert.equal(computeCashflowPayback(0, 10000).paybackYears, null)
  assert.equal(computeCashflowPayback(50000, 0).paybackYears, null)
})

test('QX39 — batterie (rendement aller-retour) allonge le payback', () => {
  const no = computeCashflowPayback(50000, 10000)
  const bat = computeCashflowPayback(50000, 10000, { battery: true })
  assert.ok(bat.paybackYears >= no.paybackYears)
})

// ── QX40 — pompage : compatibilité phase/tension pompe ↔ variateur ──────────
const _curvePump = (nom, kw, tension, prix, courbe) => ({
  id: ++_id, nom, pompe_kw: kw, tension_v: tension, prix_vente: prix,
  courbe_pompe: courbe,
})
// courbe simple : à HMT 60 m délivre 40 m³/h (≥ le débit demandé de 30)
const _COURBE = { debits_m3h: [0, 40, 60], hmt_m: [90, 60, 30] }

test('QX40 — tensionOf / tensionForAlim', () => {
  assert.equal(tensionForAlim('mono'), 220)
  assert.equal(tensionForAlim('tri'), 380)
  assert.equal(tensionOf({ tension_v: 380 }), 380)
  assert.equal(tensionOf({ nom: 'Pompe immergée 220V' }), 220)
  assert.equal(tensionOf({ nom: 'Pompe sans tension' }), null)
})

test('QX40 — une demande mono/220V ne renvoie JAMAIS une pompe 380V', () => {
  const produits = [
    _curvePump('Pompe immergée OSP 380V', 7.5, 380, '12000', _COURBE),
  ]
  const sel = selectPompeByCurve(produits, { hmt: 60, debit: 30, typePompe: 'immergee', alim: 'mono' })
  // la seule pompe à courbe pricée est 380V → incompatible mono → pas de pompe
  assert.equal(sel.pump, null)
  assert.equal(sel.phaseMismatch, true)
})

test('QX40 — une pompe compatible 220V est bien sélectionnée en mono', () => {
  const produits = [
    _curvePump('Pompe immergée OSP 380V', 7.5, 380, '12000', _COURBE),
    _curvePump('Pompe immergée OSP 220V', 7.5, 220, '11000', _COURBE),
  ]
  const sel = selectPompeByCurve(produits, { hmt: 60, debit: 30, typePompe: 'immergee', alim: 'mono' })
  assert.ok(sel.pump)
  assert.equal(tensionOf(sel.pump), 220)
})

test('QX40 — mismatch de phase dégrade vers le chemin CV avec avertissement', () => {
  const produits = [
    _curvePump('Pompe immergée OSP 380V', 7.5, 380, '12000', _COURBE),
  ]
  const sel = pompageSelection(produits, {
    cv: '10', typePompe: 'immergee', hmt: 60, debit: 30, heures: 7, alim: 'mono' })
  assert.equal(sel.mode, 'cv')
  assert.ok(sel.warning && sel.warning.includes('monophasée'))
})

test('QX40 — compose : jamais un couple pompe/variateur de tensions différentes', () => {
  const produits = [
    _curvePump('Pompe immergée OSP 380V', 7.5, 380, '12000', _COURBE),
    // un variateur 220V pricé (mono)
    { id: ++_id, nom: 'VARIATEUR VEICHI SI23 7.5KW 220V', pompe_kw: 7.5, tension_v: 220, prix_vente: '3000' },
  ]
  const lignes = autoFillPompage(produits, {
    cv: '10', alim: 'mono', typePompe: 'immergee', distance: 0,
    structureType: 'acier', hmt: 60, debit: 30, heures: 7 })
  // aucune ligne « Pompe … 380V » ne doit être chiffrée avec un variateur 220V
  const pompe380 = lignes.find(l => /380\s*v/i.test(l.designation || '') && /pompe/i.test(l.designation || ''))
  assert.equal(pompe380, undefined)
})

// ── QF5 — computeROI bascule sur le modèle « deux factures » (parité écran/PDF) ─
test('QF5 — computeROI : sans consommation réelle, comportement HISTORIQUE inchangé (estimation)', () => {
  const roi = computeROI({
    kwp: 5, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 80000, totalAvec: 100000, batteryKwh: 0,
  })
  assert.equal(roi.savings_model, 'estimation')
  assert.equal(roi.facture_sans, null)
})

test('QF5 — computeROI : avec consommation réelle + distributeur, bascule sur « deux factures »', () => {
  const kwp = 5
  const EFF = 0.8
  const prodAnnuelle = GHI.reduce((s, g) => s + g * kwp * EFF, 0)
  const consoAnnuelleKwh = 7200
  const roi = computeROI({
    kwp, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 80000, totalAvec: 100000, batteryKwh: 0,
    consoAnnuelleKwh, utility: 'onee',
  })
  assert.equal(roi.savings_model, 'factures')
  // Doit correspondre EXACTEMENT à twoBillsSavings appelé avec la même
  // production annuelle réellement calculée par computeROI (parité interne).
  const refSans = twoBillsSavings(prodAnnuelle, consoAnnuelleKwh, AUTOCONSO_SANS, 'onee')
  const refAvec = twoBillsSavings(prodAnnuelle, consoAnnuelleKwh, AUTOCONSO_AVEC, 'onee')
  assert.equal(roi.eco_annuelle_sans, refSans.economie)
  assert.equal(roi.eco_annuelle_avec, refAvec.economie)
  assert.equal(roi.facture_sans, refSans.factureSans)
  assert.equal(roi.facture_avec_sans, refSans.factureAvec)
  assert.equal(roi.facture_avec_avec, refAvec.factureAvec)
})

// ── QF7 — buildEtudeParamsChoice : scenario/recommended_option persistés ────
// pour TOUS les modes, même sans étude de base (industriel dégénéré/résidentiel).
test('QF7 — sans étude de base (résidentiel, ou industriel kwp=0) : le résultat porte quand même le choix', () => {
  const r = buildEtudeParamsChoice(null, {
    scenario: 'Les deux (Sans + Avec)', recommendedChoice: 'Auto',
    recommendedOption: 'Sans batterie', distributeur: 'onee', consoAnnuelleReelle: null,
  })
  assert.equal(r.scenario, 'Les deux (Sans + Avec)')
  assert.equal(r.recommended_choice, 'Auto')
  assert.equal(r.recommended_option, 'Sans batterie')
  // distributeur === 'onee' (défaut) sans conso réelle → pas de bruit ajouté
  assert.equal(r.distributeur, undefined)
})

test('QF7 — avec étude industrielle existante : le choix est fusionné, l\'étude préservée', () => {
  const etude = { kwc: 12.5, production_annuelle: 15000, taux_autoconso: 78 }
  const r = buildEtudeParamsChoice(etude, {
    scenario: 'Sans batterie', recommendedChoice: 'Auto',
    recommendedOption: 'Sans batterie', distributeur: 'onee', consoAnnuelleReelle: null,
  })
  assert.equal(r.kwc, 12.5)
  assert.equal(r.production_annuelle, 15000)
  assert.equal(r.scenario, 'Sans batterie')
  assert.equal(r.recommended_option, 'Sans batterie')
})

test('QF7 — agricole (étude pompage) : le choix est fusionné sans écraser les champs pompage', () => {
  const etudePompage = { pompe_cv: 5.5, hmt_m: 60, region: 'souss-massa' }
  const r = buildEtudeParamsChoice(etudePompage, {
    scenario: 'Les deux (Sans + Avec)', recommendedChoice: 'Auto',
    recommendedOption: 'Sans batterie', distributeur: 'onee', consoAnnuelleReelle: null,
  })
  assert.equal(r.pompe_cv, 5.5)
  assert.equal(r.region, 'souss-massa')
  assert.equal(r.recommended_option, 'Sans batterie')
})

test('QF7 — distributeur non-ONEE persisté même sans conso réelle (choix explicite du vendeur)', () => {
  const r = buildEtudeParamsChoice(null, {
    scenario: 'Sans batterie', recommendedChoice: 'Auto', recommendedOption: 'Sans batterie',
    distributeur: 'lydec', consoAnnuelleReelle: null,
  })
  assert.equal(r.distributeur, 'lydec')
})

test('QF7 — conso_annuelle réelle (QF4) fusionnée avec distributeur, sans écraser un conso_annuelle d\'étude existant', () => {
  const etude = { conso_annuelle: 9000, kwc: 8 } // conso dérivée de l'étude industrielle
  const r = buildEtudeParamsChoice(etude, {
    scenario: 'Sans batterie', recommendedChoice: 'Auto', recommendedOption: 'Sans batterie',
    distributeur: 'redal', consoAnnuelleReelle: 7200, // saisie réelle QF4, ne doit PAS écraser 9000
  })
  assert.equal(r.conso_annuelle, 9000) // préservé (source canonique = étude)
  assert.equal(r.distributeur, 'redal') // le distributeur choisi s'applique quand même
})

// ── QJ31 — Multi-propriétés : aperçu écran (TTC) mode ×N et mode villas ──────
const L = (designation, qty, ttc, extra = {}) => ({
  designation, quantite: String(qty), prix_unit_ttc: String(ttc), ...extra,
})

test('QJ31 — sans mode multi (pas de N, pas de groupe) : preview = null (mono-système inchangé)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)]
  assert.equal(multiPropertyPreviewTTC(lines, {}), null)
  assert.equal(multiPropertyPreviewTTC(lines, { nombreProprietes: '1' }), null)
})

test('QJ31 mode A — ×N multiplie le total TTC (unitaire × N)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)] // 34000 TTC
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '3', discountPct: '0' })
  assert.equal(r.mode, 'multiplicateur')
  assert.equal(r.nombreProprietes, 3)
  assert.equal(r.totalUnitaireSans, 34000)
  assert.equal(r.totalMultiSans, 102000) // 34000 × 3
})

test('QJ31 mode A — ×N applique aussi la remise (unitaire remisé × N)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)] // 34000 brut
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '2', discountPct: '10' })
  // unitaire remisé = round(34000 × 0.9) = 30600 ; ×2 = 61200
  assert.equal(r.totalUnitaireSans, 30600)
  assert.equal(r.totalMultiSans, 61200)
})

test('QJ31 mode B — groupes villas : sous-total par villa + total général', () => {
  const lines = [
    L('Installation commune', 1, 6000, { groupeIndex: 0, groupeLabel: 'Équipement commun' }),
    L('Onduleur réseau', 1, 20000, { groupeIndex: 1, groupeLabel: 'Villa A' }),
    L('Panneaux', 10, 1400, { groupeIndex: 1, groupeLabel: 'Villa A' }), // 14000
    L('Onduleur réseau', 1, 11000, { groupeIndex: 2, groupeLabel: 'Villa B' }),
    L('Panneaux', 8, 1400, { groupeIndex: 2, groupeLabel: 'Villa B' }), // 11200
  ]
  const r = multiPropertyPreviewTTC(lines, {})
  assert.equal(r.mode, 'villas')
  assert.deepEqual(r.groupes.map(g => g.label), ['Équipement commun', 'Villa A', 'Villa B'])
  assert.equal(r.groupes[0].totalTtc, 6000)
  assert.equal(r.groupes[1].totalTtc, 34000) // 20000 + 14000
  assert.equal(r.groupes[2].totalTtc, 22200) // 11000 + 11200
  assert.equal(r.grandTotalTtc, 62200) // somme des trois groupes
})

test('QJ31 mode B — libellé par défaut quand groupeLabel vide (Villa N / Équipement commun)', () => {
  const lines = [
    L('X', 1, 1000, { groupeIndex: 0, groupeLabel: '' }),
    L('Y', 1, 2000, { groupeIndex: 1, groupeLabel: '' }),
  ]
  const r = multiPropertyPreviewTTC(lines, {})
  assert.equal(r.groupes[0].label, 'Équipement commun')
  assert.equal(r.groupes[1].label, 'Villa 1')
})

test('QJ31 — le multiplicateur (>1) prime sur les groupes si les deux sont présents', () => {
  // À l'écran les deux modes sont exclusifs ; par sécurité, N>1 gagne.
  const lines = [L('X', 1, 1000, { groupeIndex: 1, groupeLabel: 'Villa 1' })]
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '4' })
  assert.equal(r.mode, 'multiplicateur')
})
