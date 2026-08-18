// PVMRQ (fondateur 18/08/2026) — marque préférée par rôle de composition
// automatique (`ParametresGammes.marques`, apps/ventes/models.py), miroir
// frontend dans `autoFillLines`/`optimalKwcByPayback` (solar.js). Verrouille
// les quatre garanties du contrat :
//   1. une marque épinglée GAGNE TOUJOURS (même quand une autre marque est
//      moins chère ou préférée par un tie-break existant, ex. « canadien ») ;
//   2. zéro correspondance en stock ⇒ zéro produit sur cette ligne — JAMAIS
//      un repli silencieux sur une autre marque — et `marquesManquantes`
//      consigne { role, marque } ;
//   3. la substitution « wattage le plus proche » ne joue plus que DANS le
//      vivier de la marque retenue ;
//   4. sans marque épinglée (`marques` absent/vide) : sortie BYTE-IDENTIQUE
//      au comportement historique (regression-lock).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { autoFillLines } from './solar.js'

const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc, marque) => ({
  id: ++_id, nom, prix_vente: ht(ttc), ...(marque ? { marque } : {}),
})

// Même catalogue que solar.test.mjs (SEEDED) — utilisé tel quel pour le
// verrou de régression « sans marque épinglée » ci-dessous.
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
  P('Batterie Dyness 5 kWh', 17000),
  P('Batterie Dyness 10 kWh', 30000),
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

test('PVMRQ — sans marque épinglée, sortie BYTE-IDENTIQUE au comportement historique', () => {
  const kwp = 14 * 710 / 1000
  const opts = { kwp, panelW: 710, structureType: 'acier' }
  const historique = autoFillLines(SEEDED, opts)
  const sansMarques = autoFillLines(SEEDED, { ...opts, marques: undefined })
  const marquesVide = autoFillLines(SEEDED, { ...opts, marques: {} })
  assert.deepEqual(sansMarques, historique)
  assert.deepEqual(marquesVide, historique)
  // La métadonnée existe mais reste vide — jamais un faux positif.
  assert.deepEqual(historique.marquesManquantes, [])
  assert.deepEqual(sansMarques.marquesManquantes, [])
  assert.deepEqual(marquesVide.marquesManquantes, [])
  // Repère chiffré (identique à solar.test.mjs) : la preuve que rien n'a bougé.
  const reseau = historique.find(r => r.designation.includes('réseau'))
  assert.equal(reseau.designation, 'Onduleur réseau Huawei 10kW Triphasé')
  const pan = historique.find(r => r.designation.includes('Panneau'))
  assert.equal(pan.designation, 'Panneau Canadien Solar 710W')
})

test('PVMRQ — marque épinglée GAGNE même sur le tie-break historique « canadien »', () => {
  const kwp = 14 * 710 / 1000
  // Sans épinglage, le tie-break EXISTANT préfère « canadien » à wattage égal
  // (voir solar.js) : le Jinko 710 W ne gagnerait donc JAMAIS de lui-même.
  const sansPin = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'acier' })
  assert.equal(sansPin.find(r => r.designation.includes('Panneau')).designation,
    'Panneau Canadien Solar 710W')

  const avecPin = autoFillLines(SEEDED, {
    kwp, panelW: 710, structureType: 'acier', marques: { panneau: 'Jinko' },
  })
  const pan = avecPin.find(r => r.designation.includes('Panneau'))
  assert.equal(pan.designation, 'Panneau Jinko 710W')
  assert.equal(pan.quantite, 14)
  assert.deepEqual(avecPin.marquesManquantes, [])
})

test('PVMRQ — marque épinglée introuvable : AUCUN produit sur la ligne, jamais un repli, et marquesManquantes la consigne', () => {
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(SEEDED, {
    kwp, panelW: 710, structureType: 'acier', marques: { panneau: 'LONGi' },
  })
  const pan = rows.find(r => r.designation === 'Panneaux' || r.designation.includes('Panneau'))
  // Ligne SANS produit — même patron que le vivier vide historique.
  assert.equal(pan.produit, '')
  assert.equal(pan.prix_unit_ttc, 0)
  // JAMAIS un repli sur Canadian Solar ou Jinko (les deux marques en stock).
  assert.ok(!rows.some(r => r.designation.includes('Canadien')))
  assert.ok(!rows.some(r => r.designation.includes('Jinko')))
  assert.deepEqual(rows.marquesManquantes, [{ role: 'panneau', marque: 'LONGi' }])
})

test('PVMRQ — onduleur : la marque épinglée gagne, une autre marque du même rôle n\'est jamais choisie', () => {
  const catalogue = [
    P('Onduleur réseau Huawei 10kW Triphasé', 20000, 'Huawei'),
    P('Onduleur réseau Deye 10kW Triphasé', 19000, 'Deye'),
    P('Panneau Canadien Solar 710W', 1400, 'Canadian Solar'),
    P('Structures acier', 500), P('Socles', 80),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, {
    kwp, panelW: 710, structureType: 'acier', marques: { onduleur_reseau: 'Deye' },
  })
  const reseau = rows.find(r => r.designation.includes('réseau'))
  assert.equal(reseau.designation, 'Onduleur réseau Deye 10kW Triphasé')
  assert.deepEqual(rows.marquesManquantes, [])
})

test('PVMRQ — wattage le plus proche : substitution CONFINÉE au vivier de la marque épinglée', () => {
  const catalogue = [
    // Sans épinglage, ce panneau Canadian 640 W serait le plus proche de 650 W
    // demandés (10 W d'écart) — la preuve que la marque épinglée restreint
    // bien le vivier AVANT le rapprochement de wattage.
    P('Panneau Canadian Solar 640W', 1300, 'Canadian Solar'),
    P('Panneau Jinko 710W', 1400, 'Jinko'),
    P('Panneau Jinko 550W', 1000, 'Jinko'),
    P('Onduleur réseau Huawei 10kW Triphasé', 20000, 'Huawei'),
    P('Structures acier', 500), P('Socles', 80),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, {
    kwp, panelW: 650, structureType: 'acier', marques: { panneau: 'Jinko' },
  })
  const pan = rows.find(r => r.designation.includes('Panneau'))
  // Le plus proche de 650 W DANS le vivier Jinko (710 W, écart 60) l'emporte
  // sur le Canadian 640 W (écart 10) laissé HORS vivier par l'épinglage.
  assert.equal(pan.designation, 'Panneau Jinko 710W')
})

test('PVMRQ — batterie : marque épinglée introuvable au vivier électriquement compatible', () => {
  const catalogue = [
    P('Onduleur hybride Deye 10kW Triphasé', 28000, 'Deye'), // pas de plage déclarée → repli mot-clé
    P('Batterie Dyness 10 kWh', 30000, 'Dyness'),
    P('Panneau Jinko 710W', 1400, 'Jinko'),
    P('Structures acier', 500), P('Socles', 80),
  ]
  const kwp = 14 * 710 / 1000
  const rows = autoFillLines(catalogue, {
    kwp, panelW: 710, structureType: 'acier', marques: { batterie: 'Pylontech' },
  })
  const battRows = rows.filter(r => r.designation === 'Batterie')
  assert.ok(battRows.every(r => r.produit === ''))
  assert.ok(rows.marquesManquantes.some(m => m.role === 'batterie' && m.marque === 'Pylontech'))
  // Jamais un repli silencieux sur la Dyness pourtant en stock.
  assert.ok(!rows.some(r => r.designation.includes('Dyness')))
})
