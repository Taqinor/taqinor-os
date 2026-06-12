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
  P('Suivi journalier, maintenance chaque 12 mois pendent 2 ans', 5000),
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
    'Suivi journalier, maintenance chaque 12 mois pendent 2 ans', 'Autres',
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
