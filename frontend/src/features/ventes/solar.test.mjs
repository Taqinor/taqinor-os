// Parity tests for the solar generator math against the devis-simulator
// (source of truth). Run with: node --test src/features/ventes/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
// QJR109 — le garde-fou « le lead ne réinitialise pas le marché choisi » est
// désormais EXÉCUTÉ sur le reducer pur, au lieu d'être cherché dans le source.
import {
  sizingReducer, ETAT_INITIAL,
} from './quote/sizingReducer.js'
import {
  DEFAULT_MONTHLY_BILLS, estimerMois, formatMoney,
  computeROI, ttcFromHt, htFromTtc, optionTotalsTTC, autoFillLines, GHI,
  totauxCanoniquesTtc, appartientAuPanierSans, appartientAuPanierAvec,
  groupProduitsByCategory,
  KWH_PRICE, FALLBACK_KWH_PRICE, kwhFromBill, twoBillsSavings, monthlyBillFromKwh,
  ONEE_TRANCHES, AUTOCONSO_SANS, AUTOCONSO_AVEC,
  multiPropertyPreviewTTC,
  productibleForCity, PRODUCTIBLE_PAR_VILLE, DEFAULT_PRODUCTIBLE,
  computeCashflowPayback,
  isReseauInverter, batterieCompatible, plageBatterieOnduleur, DAYS_IN_MONTH,
  PRODUCTIBLE_NET_FACTOR, TARIFF_ESCALATION,
  isBattery, isHybridInverter, isAnyInverter, inverterCostFromLines,
  batteryKwhFromLines, INVERTER_REPLACE_YEAR, BATTERY_ROUNDTRIP,
  // STKCAT10 — sélecteur de structures piloté par le catalogue.,
  structureRoleForName, structureChoisie,
} from './solar.js'
import { PAS_ARRONDI_DEVIS } from './remise.js'

// Reflet du catalogue seedé (prix HT = TTC simulateur / 1.2, 2 décimales)
const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
// BATHOMO/F4 (fondateur 26/08/2026) — `quantite_stock` par défaut à 500,
// même convention que le catalogue seedé (`seed_catalogue.py`) : le stock-
// gating batterie n'exclut QUE ce qu'un test met explicitement à 0, jamais
// les fixtures existantes qui ne parlaient pas encore de stock.
const P = (nom, ttc, qty = 500) => ({ id: ++_id, nom, prix_vente: ht(ttc), quantite_stock: qty })
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
  // ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — chaîne canonique du noyau : HT
  // persisté 833,33 ; remise 104,17 ; HT net 729,16 ; TVA 145,83 → 874,99
  // (le chiffre facturé ; l'ancien « 1000 × 0,875 = 875 » ne l'était pas).
  // ARRONDI-100 : 874,99 → palier de 100 inférieur.
  assert.equal(totalSans, 800)
})

test('sélecteur produits : groupé selon les catégories du catalogue simulateur', () => {
  const groups = groupProduitsByCategory([
    ...SEEDED,
    // Les deux câbles Nexans au mètre ont leurs propres groupes depuis le 18/08.
    { id: 998, nom: 'Câble solaire Nexans 6 mm² (au mètre)', prix_vente: '12.00' },
    { id: 999, nom: 'Câble de terre Nexans 6 mm² (au mètre)', prix_vente: '12.00' },
    // …et un produit non classable alimente toujours « Autres ».
    { id: 1000, nom: 'Échafaudage roulant', prix_vente: '850' },
  ])
  const labels = groups.map(g => g.label)
  assert.deepEqual(labels, [
    'Onduleur Injection', 'Onduleur Hybride', 'Panneaux', 'Batterie',
    'Structures acier', 'Structures aluminium', 'Socles',
    'Câble solaire DC', 'Câble de terre AC', 'Smart Meter',
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
  // les deux câbles au mètre tombent chacun dans SON groupe, jamais « Autres »
  assert.equal(by('Câble solaire DC').items.length, 1)
  assert.equal(by('Câble de terre AC').items.length, 1)
  // produit non solaire → groupe Autres
  assert.equal(by('Autres').items[0].nom, 'Échafaudage roulant')
})

// QJR109 — CETTE GARDE-CI RESTE UNE LECTURE DU SOURCE, ET C'EST DÉLIBÉRÉ.
// Elle porte sur des ATTRIBUTS DOM (`noValidate` du formulaire, `step="any"`
// sur chaque champ nombre) : c'est une règle FONDATEUR (« l'écran ne doit
// JAMAIS snapper ni rejeter un nombre tapé ») dont la seule autre expression
// possible est un rendu React (spec RTL). La convertir en pur est IMPOSSIBLE ;
// la retirer DESSERRERAIT la garde. Elle reste donc telle quelle, nommée pour
// que la prochaine passe ne la prenne pas pour un oubli.
// QJR101 — les champs nombres du marché ont suivi les quatre panneaux
// (`generator/Panneau*.jsx`). La garde les SUIT au lieu de rester verte en ne
// regardant plus qu'une fraction de l'écran : sans ce recalage elle passait de
// 20 champs surveillés à 3. Un cinquième panneau de marché rejoint cette liste.
// QJR244 — la carte « Factures Électriques » (factures hiver/été, grille des
// 12 mois, bloc facture réelle du client) a quitté les trois panneaux réseau
// pour un composant partagé unique (`CarteFacturesElectriques.jsx`) : ses
// champs nombre ne sont plus lus TROIS FOIS (une fois par panneau copié-collé)
// mais UNE seule fois — la garde ajoute ce fichier, sinon elle retomberait
// silencieusement de 34 à ~4 champs surveillés.
const SURFACES_SAISIE = [
  '../../pages/ventes/DevisGenerator.jsx',
  '../../pages/ventes/generator/PanneauResidentiel.jsx',
  '../../pages/ventes/generator/PanneauIndustriel.jsx',
  '../../pages/ventes/generator/PanneauCommercial.jsx',
  '../../pages/ventes/generator/PanneauAgricole.jsx',
  '../../pages/ventes/generator/CarteFacturesElectriques.jsx',
  // QJR5 (lot 4) — conso annuelle + grille MT des panneaux Industriel et
  // Commercial, désormais UN composant partagé.
  '../../pages/ventes/generator/BlocEtudeReseau.jsx',
  // QJR624 — l'échéancier éditable de l'Édition complète.
  '../../pages/ventes/generator/CarteEcheancier.jsx',
  // QJR667 — le formulaire « Lots / multi-sites » (champ ordre).
  './LotsMultiSites.jsx',
]

test('garde-fou : plus aucune contrainte step restrictive sur l\'écran', () => {
  const ici = dirname(fileURLToPath(import.meta.url))
  const lire = (rel) => readFileSync(join(ici, rel), 'utf-8')
  assert.ok(lire(SURFACES_SAISIE[0]).includes('noValidate'),
    'le formulaire doit être noValidate (aucun rejet navigateur)')
  let champsNombre = 0
  for (const rel of SURFACES_SAISIE) {
    const jsx = lire(rel)
    for (const bad of ['step="100"', 'step="10"', 'step="1"', 'step="0.01"']) {
      assert.ok(!jsx.includes(bad), `contrainte de saisie restrictive dans ${rel} : ${bad}`)
    }
    // Seul le curseur (type="range") garde un pas ; aucun champ nombre n'en a.
    const numberSteps = jsx.split('type="number"').slice(1)
      .map(chunk => /step="([^"]+)"/.exec(chunk)?.[1])
    numberSteps.forEach(s => assert.equal(s, 'any', `${rel} : champ nombre sans step="any"`))
    champsNombre += numberSteps.length
  }
  // Cliquet : 26 champs nombres mesurés sur les SIX surfaces (recalé par
  // QJR244, qui a fait passer le socle des factures — hiver/été + grille des
  // 12 mois (une seule expression `.map()` en SOURCE, jamais comptée 12 fois)
  // + facture réelle, 4 occurrences en source — de « recopié dans les trois
  // panneaux réseau » (compté 3 fois, 12 occurrences) à « un seul composant
  // partagé » (compté 1 fois, 4 occurrences) : 34 − 12 + 4 = 26. Un champ qui
  // migrerait vers un fichier absent de la liste ci-dessus ferait tomber ce
  // compte au lieu de sortir de la garde en silence.
  // Recalé à 25 par le lot 4 QJR5 : conso annuelle + grille MT, recopiées
  // dans Industriel ET Commercial (4 occurrences), passent dans le composant
  // partagé `BlocEtudeReseau.jsx` (ajouté à la liste) — 2 champs + 1 mention
  // `type="number"` de son commentaire d'en-tête = 3 : 26 − 4 + 3 = 25.
  assert.ok(champsNombre >= 25,
    `seulement ${champsNombre} champs nombres sous garde (25 attendus)`)
})

// QJR109 — CETTE GARDE A CESSÉ DE LIRE LE SOURCE. Elle cherchait la chaîne
// `!sizing.touche.mode` à moins de 120 caractères de `LEAD_TYPE_TO_MODE` dans
// `DevisGenerator.jsx` : une épingle qui rougit sur un reformatage et reste
// verte si le garde-fou est déplacé dans une branche morte. Depuis QJR87/QJR99
// le garde-fou est un ÉTAT du reducer PUR — il est ici EXÉCUTÉ.
test('garde-fou : choisir un lead ne réinitialise JAMAIS le mode choisi', () => {
  // Le commercial a choisi son marché à la main…
  const choisi = sizingReducer(ETAT_INITIAL,
    { type: 'MARCHE_CHANGE', mode: 'industriel' })
  assert.equal(choisi.modeInstallation, 'industriel')
  assert.equal(choisi.touche.mode, true,
    'un choix UTILISATEUR doit marquer le drapeau')

  // …puis il sélectionne un lead d'un AUTRE marché : le choix tient.
  const apresLead = sizingReducer(choisi, {
    type: 'LEAD_APPLIQUE', lead: { type_installation: 'residentiel' } })
  assert.equal(apresLead.modeInstallation, 'industriel',
    'le lead ne doit pas réinitialiser le marché déjà choisi')

  // Sans choix préalable, le lead pose bien le marché (le garde-fou ne gèle
  // pas l'écran) — et ne marque PAS le drapeau : ce n'est pas un choix.
  const vierge = sizingReducer(ETAT_INITIAL, {
    type: 'LEAD_APPLIQUE', lead: { type_installation: 'agricole' } })
  assert.equal(vierge.modeInstallation, 'agricole')
  assert.equal(vierge.touche.mode, false)

  // Un `type_installation` inconnu ne change rien (jamais un marché inventé).
  assert.equal(
    sizingReducer(ETAT_INITIAL,
      { type: 'LEAD_APPLIQUE', lead: { type_installation: 'sous-marin' } })
      .modeInstallation,
    'residentiel')
})

test('ROI : production GHI × kWc × 0.8', () => {
  const roi = computeROI({
    kwp: 9.94, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 65040, totalAvec: 103040, batteryKwh: 10,
  })
  const sumGhi = GHI.reduce((a, b) => a + b, 0)
  assert.ok(Math.abs(roi.production_annuelle_kwh - sumGhi * 9.94 * 0.8) < 0.1)
  // ORDRE FONDATEUR (18/08) — l'apport batterie n'est plus un forfait de
  // 60 MAD/kWh/mois : c'est de l'ÉNERGIE, capacité × 1 cycle/jour, plafonnée
  // par le surplus du mois (production − part diurne) et valorisée au tarif.
  // Dérivation à la main, janvier : production = 83,99 × 9,94 × 0,8 = 667,99 kWh ;
  // part diurne 60 % = 400,79 kWh ; surplus stockable = 267,20 kWh ; la batterie
  // pourrait décaler 10 kWh × 31 j = 310 kWh → PLAFONNÉE à 267,20 kWh.
  for (let i = 0; i < 12; i++) {
    const prod = GHI[i] * 9.94 * 0.8
    const shift = Math.min(10 * DAYS_IN_MONTH[i], prod * 0.4)
    assert.ok(
      Math.abs(roi.eco_avec_monthly[i] - roi.eco_sans_monthly[i] - shift * 1.75) < 0.001,
      `mois ${i + 1} : l'apport batterie doit valoir les kWh décalés × 1,75 MAD`)
  }
  // Le forfait historique (10 kWh × 60 = 600 MAD/mois) n'existe plus.
  assert.ok(Math.abs(roi.eco_avec_monthly[0] - roi.eco_sans_monthly[0] - 600) > 1)
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

  // Batteries : cible 10 kWh → 1 × Dyness 10 kWh, 0 × 5 kWh
  assert.equal(by('Dyness 10').quantite, 1)
  assert.equal(by('Dyness 10').prix_unit_ttc, 30000)
  assert.equal(by('Dyness 5').quantite, 0)

  // Structures acier ×14 (500), aluminium 0 ; Socles ×28 (80)
  assert.equal(by('acier').quantite, 14)
  assert.equal(by('acier').prix_unit_ttc, 500)
  assert.equal(by('aluminium').quantite, 0)
  assert.equal(by('Socles').quantite, 28)
  assert.equal(by('Socles').prix_unit_ttc, 80)

  // L-FORFAIT (fondateur 24/08/2026) — cotés AU PANNEAU (miroir TTC des
  // champs Stock) : accessoires 62,5×n, tableau 243,75×n, installation
  // 2 400 + 300×n. À 14 panneaux :
  assert.equal(by('Accessoires').prix_unit_ttc, 875)
  assert.equal(by('Tableau').prix_unit_ttc, 3412.5)
  assert.equal(by('Installation').prix_unit_ttc, 6600)
  assert.equal(by('Transport').prix_unit_ttc, 1000)
  assert.equal(by('Suivi').quantite, 0)

  // Prix entiers à l'écran — SAUF les trois forfaits au panneau : les taux
  // dérivés du fondateur (÷2 et +30 % sur les anciens ancrages) portent des
  // centimes légitimes ; la chaîne de totaux les traite exactement.
  const FORFAITS = ['Accessoires', 'Tableau', 'Installation']
  rows.forEach(r => {
    if (FORFAITS.some(f => r.designation.includes(f))) return
    assert.ok(CLEAN_INT(r.prix_unit_ttc), `prix non entier: ${r.designation} ${r.prix_unit_ttc}`)
  })

  // Totaux par option, exactement comme updateTotals du simulateur
  // (recalés L-FORFAIT : −1 312,50 de forfaits vs l'ancienne règle par blocs)
  // ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — les PRIX saisis restent ceux du
  // simulateur (Σ TTC des paniers inchangée) ; le TOTAL affiché est celui que
  // le noyau facture sur ces mêmes lignes (chaîne canonique HT → TVA).
  const sommeTtc = (rs) => rs.reduce((s, r) => s + r.quantite * r.prix_unit_ttc, 0)
  assert.equal(sommeTtc(rows.filter(appartientAuPanierSans)), 63727.5)
  assert.equal(sommeTtc(rows.filter(appartientAuPanierAvec)), 101727.5)
  // ARRONDI-100 : le total par option est ramené au palier de 100 MAD
  // inférieur ; le noyau de référence reçoit le même palier.
  const totals = optionTotalsTTC(rows, 0)
  assert.equal(totals.totalSansBrut, totauxCanoniquesTtc(rows.filter(appartientAuPanierSans), 0, PAS_ARRONDI_DEVIS))
  assert.equal(totals.totalAvecBrut, totauxCanoniquesTtc(rows.filter(appartientAuPanierAvec), 0, PAS_ARRONDI_DEVIS))
  // ARRONDI-100 : 63 727,73 → palier de 100 inférieur (ancienne attente : à moins de 1 MAD de 63 727,5).
  assert.equal(totals.totalSansBrut, 63700)
  // ARRONDI-100 : 101 727,72 → palier de 100 inférieur (ancienne attente : à moins de 1 MAD de 101 727,5).
  assert.equal(totals.totalAvecBrut, 101700)
})

test('auto-fill 24 panneaux × 710 W : batterie homogène 3×5 kWh (jamais 10+5), structures alu', () => {
  // BATHOMO/F4 (fondateur 26/08/2026) — l'ancien calcul mélangeait 1×10 + 1×5
  // (électriquement interdit, l'incident qui a fait retirer le Dyness 10 kWh
  // du stock). Sur ce fixture (5 kWh = 17 000 TTC → 3 400/kWh ; 10 kWh =
  // 30 000 TTC → 3 000/kWh), le 10 kWh est moins cher AU kWh, mais 15 kWh
  // exigerait un 2×10 kWh EN SURPLUS (20 kWh, 60 000 TTC) contre un 3×5 kWh
  // EXACT (51 000 TTC) : le moins cher au TOTAL gagne, jamais une préférence
  // de calibre fixe — c'est le 5 kWh, homogène, jamais mélangé.
  const kwp = 24 * 710 / 1000 // 17.04 → cible batterie 15 kWh
  const rows = autoFillLines(SEEDED, { kwp, panelW: 710, structureType: 'aluminium' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Dyness 10').quantite, 0)
  assert.equal(by('Dyness 5').quantite, 3)
  assert.equal(by('Dyness 5').prix_unit_ttc, 17000)
  assert.equal(by('aluminium').quantite, 24)
  assert.equal(by('aluminium').prix_unit_ttc, 850)
  assert.equal(by('acier').quantite, 0)
  // L-FORFAIT — au panneau, 24 panneaux : 62,5×24 / 243,75×24 / 2 400+300×24
  assert.equal(by('Accessoires').prix_unit_ttc, 1500)
  assert.equal(by('Tableau').prix_unit_ttc, 5850)
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
  // cible batterie : max(5, round(3.55/5)*5) = 5 → 1 × Dyness 5 kWh
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Dyness 5').quantite, 1)
  assert.equal(by('Dyness 10').quantite, 0)
})

// ── Tolérance d'orthographe Dyness / Deyness (fondateur, 2026-08-18) ─────────
// La marque s'écrit « Dyness » ; le catalogue a longtemps écrit « Deyness ».
// Une base pas encore migrée (ou un produit saisi à la main) doit continuer
// d'alimenter le vivier batterie — sinon l'auto-remplissage retomberait sur
// TOUTES les batteries du catalogue et proposerait un module Gel ou Lithium
// générique à la place du bon.
test('auto-fill : un catalogue encore écrit « Deyness » alimente le même vivier', () => {
  const ancien = SEEDED.map(p => ({
    ...p, nom: p.nom.replace('Dyness', 'Deyness'),
  }))
  // Le module GÉNÉRIQUE 5 kWh passe DEVANT : sans la tolérance d'orthographe, le
  // vivier retomberait sur toutes les batteries et retiendrait celui-ci.
  const iGenerique = ancien.findIndex(p => p.nom.includes('Batterie Lithium'))
  ancien.unshift(...ancien.splice(iGenerique, 1))

  // BATHOMO/F4 — cible 15 kWh → 3×5 kWh homogène (jamais 1×10 + 1×5 mélangé,
  // même raison économique que le test « batterie homogène » ci-dessus).
  const kwp = 24 * 710 / 1000 // 17.04 → cible batterie 15 kWh
  const rows = autoFillLines(ancien, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Deyness 10').quantite, 0)
  assert.equal(by('Deyness 10').prix_unit_ttc, 30000)
  assert.equal(by('Deyness 5').quantite, 3)
  assert.equal(by('Deyness 5').prix_unit_ttc, 17000)
  // Aucune batterie générique ne s'est glissée à la place de la marque.
  assert.ok(rows.every(r => !r.designation.includes('Lithium')))
})

// ── PVG4 — garde HAUTE TENSION (BAT-DYN-HV-16, miroir EXACT du garde backend
// _is_battery_basse_tension, fondateur 2026-08-18) ────────────────────────────
// La batterie Dyness haute tension (16 kWh) est réservée aux dossiers haute
// tension : jamais auto-choisie en kit résidentiel, même moins chère et même
// si sa capacité coïncide par coïncidence avec la cible basse tension.
test('auto-fill : batterie « haute tension » jamais auto-choisie même moins chère', () => {
  const avecHV = [...SEEDED]
  const iDyness10 = avecHV.findIndex(p => p.nom === 'Batterie Dyness 10 kWh')
  // Insérée AVANT la Dyness 10 kWh normale, bien moins chère (100 vs 30 000),
  // même marque « Dyness » et capacité coïncidant à 10 kWh, casse mélangée
  // (« HAUTE TENSION ») : sans le garde, le premier .find() par capacité la
  // retiendrait à la place de la bonne batterie basse tension.
  avecHV.splice(iDyness10, 0, P('Batterie Dyness HAUTE TENSION 10 kWh', 100))

  const kwp = 14 * 710 / 1000 // 9.94 → cible batterie 10 kWh
  const rows = autoFillLines(avecHV, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))

  // La batterie haute tension n'apparaît dans AUCUNE ligne auto-composée.
  assert.ok(rows.every(r => !r.designation.toLowerCase().includes('haute tension')))
  // La vraie Dyness 10 kWh (30 000 DH) est retenue à sa place, comme avant.
  assert.equal(by('Dyness 10').designation, 'Batterie Dyness 10 kWh')
  assert.equal(by('Dyness 10').quantite, 1)
  assert.equal(by('Dyness 10').prix_unit_ttc, 30000)
})

test('auto-fill : les batteries 5/10 kWh restent choisies (homogène) malgré une HV au catalogue', () => {
  const avecHV = [...SEEDED, P('Batterie Dyness haute tension 16 kWh', 100)]

  // BATHOMO/F4 — cible 15 kWh → 3×5 kWh homogène, même raison économique.
  const rows24 = autoFillLines(avecHV, { kwp: 24 * 710 / 1000, panelW: 710, structureType: 'aluminium' })
  const by24 = (frag) => rows24.find(r => r.designation.includes(frag))
  assert.equal(by24('Dyness 10').quantite, 0)
  assert.equal(by24('Dyness 5').quantite, 3)

  const rows5 = autoFillLines(avecHV, { kwp: 5 * 710 / 1000, panelW: 710, structureType: 'acier' })
  const by5 = (frag) => rows5.find(r => r.designation.includes(frag))
  assert.equal(by5('Dyness 5').quantite, 1)
  assert.equal(by5('Dyness 10').quantite, 0)
})

// ── BATHOMO/F4 (fondateur 26/08/2026, revue adversariale) — MIROIR EXACT du
// moteur serveur (apps/ventes/services.py::composition_residentielle) :
// homogène par calibre, EN STOCK seulement, prix TTC total le plus bas,
// plafond de modules respecté. Mêmes cas que
// apps/ventes/tests/test_bathomo_banque_homogene.py côté backend.
test('F4 — prix RÉELS fondateur : 2×5 kWh (28 000 TTC) bat 1×10 kWh (30 000 TTC) pour une cible de 10 kWh', () => {
  // « 2×5=28 000 beats 1×10=30 000 for a 10 kWh target » (fondateur,
  // 26/08/2026) : catalogue de production, 5 kWh = 14 000 TTC (2 800/kWh),
  // 10 kWh = 30 000 TTC (3 000/kWh) — le 5 kWh est moins cher au kWh.
  const catalogue = [
    P('Onduleur réseau Huawei 5kW Monophasé', 14000),
    P('Onduleur hybride Deye 5kW Monophasé', 17000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 5 kWh', 14000),
    P('Batterie Dyness 10 kWh', 30000),
    P('Structures acier', 500), P('Socles', 80),
    P('Accessoires', 2000), P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800), P('Transport', 1000),
  ]
  const kwp = 14 * 710 / 1000 // 9.94 → cible batterie 10 kWh
  const rows = autoFillLines(catalogue, { kwp, panelW: 710, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Dyness 5').quantite, 2)
  assert.equal(by('Dyness 10').quantite, 0)
})

test('F4 — jusqu\'à 40 kWh (8 packs de 5 kWh) le 5 kWh reste économique, jamais mélangé', () => {
  const catalogue = [
    P('Onduleur réseau Huawei 5kW Monophasé', 14000),
    P('Onduleur hybride Deye 5kW Monophasé', 17000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 5 kWh', 14000),
    P('Batterie Dyness 10 kWh', 30000),
    P('Structures acier', 500), P('Socles', 80),
    P('Accessoires', 2000), P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800), P('Transport', 1000),
  ]
  for (const cibleKwh of [15, 20, 25, 30, 35, 40]) {
    const kwp = cibleKwh // panelW=1000W → kwp == cible arrondie au multiple de 5
    const rows = autoFillLines(catalogue, { kwp, panelW: 1000, structureType: 'acier' })
    const by = (frag) => rows.find(r => r.designation.includes(frag))
    assert.equal(by('Dyness 10').quantite, 0, `cible ${cibleKwh} kWh`)
    assert.equal(by('Dyness 5').quantite * 5, cibleKwh, `cible ${cibleKwh} kWh`)
  }
})

test('F4 — un calibre à 0 en stock est EXCLU du choix économique', () => {
  const catalogue = [
    P('Onduleur réseau Huawei 5kW Monophasé', 14000),
    P('Onduleur hybride Deye 5kW Monophasé', 17000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 5 kWh', 14000),
    P('Batterie Dyness 10 kWh', 30000, /* qty */ 0), // rupture de stock
    P('Structures acier', 500), P('Socles', 80),
    P('Accessoires', 2000), P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800), P('Transport', 1000),
  ]
  // Cible 20 kWh : sans la garde de stock, le 10 kWh (moins cher au kWh à ce
  // prix) gagnerait l'arbitrage économique — la garde de stock l'exclut.
  const kwp = 20
  const rows = autoFillLines(catalogue, { kwp, panelW: 1000, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Dyness 10').quantite, 0)
  assert.equal(by('Dyness 5').quantite, 4)
})

test('F4 — max_modules_par_banc (specs_solaire) rejette une candidate qui le dépasse, jamais un mélange', () => {
  const bat5 = P('Batterie Dyness 5 kWh', 14000)
  bat5.specs_solaire = { famille: 'batterie', max_modules_par_banc: 2 }
  const catalogue = [
    P('Onduleur réseau Huawei 5kW Monophasé', 14000),
    P('Onduleur hybride Deye 5kW Monophasé', 17000),
    P('Panneau Canadien Solar 710W', 1400),
    bat5,
    P('Batterie Dyness 10 kWh', 30000),
    P('Structures acier', 500), P('Socles', 80),
    P('Accessoires', 2000), P('Tableau De Protection AC/DC', 2000),
    P('Installation', 4800), P('Transport', 1000),
  ]
  // 20 kWh exigerait 4×5 (au-dessus du plafond 2) : REJETÉ — seul le 10 kWh
  // (2×10, sans plafond) reste, jamais une banque tronquée à 2×5=10 kWh.
  const rows = autoFillLines(catalogue, { kwp: 20, panelW: 1000, structureType: 'acier' })
  const by = (frag) => rows.find(r => r.designation.includes(frag))
  assert.equal(by('Dyness 5').quantite, 0)
  assert.equal(by('Dyness 10').quantite, 2)
})

// ── PVOND — garde batterie PILOTÉ PAR LA DONNÉE + verrou de complétude ──────
// Les deux tests PVG4 ci-dessus restent VRAIS et inchangés : sans
// `specs_solaire` au catalogue (fixtures ci-dessus), le repli mot-clé garde la
// main à l'identique. Les tests qui suivent vérifient ce que le mot-clé ne
// savait PAS faire.
const _specs = (p, specs) => ({
  ...p,
  specs_solaire: {
    famille: null, plage_batterie_v: null, v_nominal: null, manquantes: [],
    ...specs,
  },
})

test('PVOND — une batterie hors plage est refusée même si son nom ne dit rien', () => {
  // 204,8 V sous un onduleur 48 V : appairage électriquement impossible que le
  // mot-clé « haute tension » ne voyait pas (le nom est parfaitement neutre).
  const catalogue = SEEDED.map(p =>
    p.nom === 'Onduleur hybride Deye 10kW Triphasé'
      ? _specs(p, { famille: 'onduleur', plage_batterie_v: [40, 60] })
      : p)
  catalogue.push(_specs(P('Batterie LFP 10 kWh rack', 100),
                        { famille: 'batterie', v_nominal: 204.8 }))

  const rows = autoFillLines(catalogue, { kwp: 14 * 710 / 1000, panelW: 710, structureType: 'acier' })
  assert.ok(rows.every(r => !r.designation.includes('LFP')))
})

test('PVOND — une batterie haute tension EST retenue sous un onduleur haute tension', () => {
  // L'autre moitié du gain : le mot-clé interdisait l'appairage LÉGITIME.
  const catalogue = SEEDED
    .filter(p => !p.nom.startsWith('Batterie'))
    .map(p => p.nom === 'Onduleur hybride Deye 10kW Triphasé'
      ? _specs(p, { famille: 'onduleur', plage_batterie_v: [160, 700] })
      : p)
  catalogue.push(_specs(P('Batterie Dyness haute tension 10 kWh', 40000),
                        { famille: 'batterie', v_nominal: 204.8 }))

  const rows = autoFillLines(catalogue, { kwp: 14 * 710 / 1000, panelW: 710, structureType: 'acier' })
  const bat = rows.find(r => r.designation.includes('haute tension'))
  assert.ok(bat, 'la batterie HV aurait dû être retenue sous un onduleur HV')
  assert.equal(bat.quantite, 1)
})

test('PVOND — un onduleur au contrat incomplet est écarté ET nommé', () => {
  const catalogue = SEEDED.map(p =>
    p.nom === 'Onduleur réseau Huawei 10kW Triphasé'
      ? _specs(p, { famille: 'onduleur', manquantes: ['courant maxi par MPPT (A)'] })
      : p)

  const rows = autoFillLines(catalogue, { kwp: 10, panelW: 710, structureType: 'acier' })

  assert.ok(rows.onduleursIncomplets.some(o => o.nom === 'Onduleur réseau Huawei 10kW Triphasé'))
  assert.deepEqual(rows.onduleursIncomplets[0].manquantes, ['courant maxi par MPPT (A)'])
  // Il n'est PAS chiffré : la ligne « Onduleur réseau » porte un autre modèle.
  const reseau = rows.find(r => isReseauInverter(r.designation))
  assert.notEqual(reseau?.designation, 'Onduleur réseau Huawei 10kW Triphasé')
})

// ── PVOND — LE REPLI MOT-CLÉ N'EST PLUS UN RATTRAPAGE UNIVERSEL ─────────────
// Règle corrigée (fondateur 2026-08-18) : le mot-clé ne parle QUE lorsque
// l'ONDULEUR ne déclare aucune plage. Dès qu'une plage existe, une candidate
// sans tension nominale — ou avec une tension nulle, donc une donnée INVALIDE —
// est exclue. Miroir exact de `_batterie_compatible` (apps/ventes/services.py).
test('PVOND — plage déclarée + batterie SANS fiche ⇒ exclue (jamais le mot-clé)', () => {
  const sansFiche = P('Batterie Dyness 5 kWh', 16000)
  assert.equal(batterieCompatible(sansFiche, [40, 60]), false)
  // …mais SANS plage déclarée, le repli mot-clé garde la main à l'identique.
  assert.equal(batterieCompatible(sansFiche, null), true)
})

test('PVOND — v_nominal = 0 est une donnée INVALIDE, pas une absence', () => {
  const zero = _specs(P('Batterie Dyness 5 kWh', 16000),
                      { famille: 'batterie', v_nominal: 0 })
  // Python teste `40 <= 0.0 <= 60` et REFUSE : le JS refuse désormais aussi.
  assert.equal(batterieCompatible(zero, [40, 60]), false)
})

test('PVOND — le repli mot-clé exige « batterie » dans le nom (miroir Python)', () => {
  // `_is_battery_basse_tension` exige "batterie" ET pas "haute tension".
  assert.equal(batterieCompatible(P('Batterie Dyness 5 kWh', 16000), null), true)
  assert.equal(
    batterieCompatible(P('Batterie Dyness haute tension 16 kWh', 48000), null),
    false)
  // Un produit qui n'est pas une batterie n'est jamais « compatible ».
  assert.equal(batterieCompatible(P('Onduleur hybride Deye 10kW', 28000), null),
               false)
})

test('PVOND — vivier batterie VIDE sous une plage : la composition AVERTIT', () => {
  // Le cas RÉEL du catalogue : sous un Deye 15 kW (160-700 V), les batteries
  // génériques sans fiche partaient quand même — désormais aucune ne passe, et
  // le devis le DIT au lieu de partir silencieusement sans stockage.
  const catalogue = SEEDED.map(p =>
    p.nom === 'Onduleur hybride Deye 15kW Triphasé'
      ? _specs(p, { famille: 'onduleur', plage_batterie_v: [160, 700] })
      : p)

  const rows = autoFillLines(catalogue, { kwp: 15, panelW: 710, structureType: 'acier' })

  assert.equal(rows.avertissementsBatterie.length, 1)
  assert.ok(rows.avertissementsBatterie[0].includes('160-700 V'))
  assert.ok(rows.avertissementsBatterie[0].includes('SANS batterie'))
})

test('PVOND — aucune alerte batterie quand le vivier sert normalement', () => {
  const rows = autoFillLines(SEEDED, { kwp: 10, panelW: 710, structureType: 'acier' })
  assert.deepEqual(rows.avertissementsBatterie, [])
})

// ── PVOND — CONTRAT CONDITIONNEL À LA FAMILLE (ordre fondateur 18/08/2026) ──
// La plage de tension batterie décrit un PORT qui n'existe pas sur un onduleur
// RÉSEAU : la réclamer grisait la moitié du bandeau « Onduleur(s) non
// chiffrable(s) » pour cette SEULE variable. Elle n'est donc exigée que des
// HYBRIDES (et des familles indéterminées). Miroir de
// `stock.selectors.plage_batterie_onduleur` / `famille_onduleur`.
test('PVOND — un onduleur RÉSEAU sans plage déclarée vaut « aucune batterie »', () => {
  const reseau = P('Onduleur réseau Huawei 10kW Triphasé', 20000)
  assert.deepEqual(plageBatterieOnduleur(reseau), [0, 0])
  // …et aucune batterie ne s'y accroche : le mot-clé ne reprend PAS la main.
  assert.equal(
    batterieCompatible(P('Batterie Dyness 5 kWh', 16000), plageBatterieOnduleur(reseau)),
    false)
})

test('PVOND — un onduleur HYBRIDE sans plage reste « non déclarée » (repli intact)', () => {
  const hybride = P('Onduleur hybride Deye 10kW Triphasé', 28000)
  assert.equal(plageBatterieOnduleur(hybride), null)
  // Sans plage, le repli mot-clé PVG4 garde la main, byte-identique à hier.
  assert.equal(
    batterieCompatible(P('Batterie Dyness 5 kWh', 16000), plageBatterieOnduleur(hybride)),
    true)
})

test('PVOND — « hybride » l\'emporte sur « réseau » dans le nom (miroir Python)', () => {
  // Même ORDRE que `classer_produit` / `famille_onduleur` : un hybride qui
  // mentionne aussi l'injection réseau reste un HYBRIDE, plage EXIGÉE.
  assert.equal(plageBatterieOnduleur(P('Onduleur hybride injection réseau 10kW', 1)), null)
  // Une référence nue (famille indéterminée) reste exigeante elle aussi.
  assert.equal(plageBatterieOnduleur(P('Onduleur Deye SUN-10K', 1)), null)
})

test('PVOND — une plage SERVIE par l\'API l\'emporte sur le défaut de famille', () => {
  // Le jour où un Huawei est vendu AVEC stockage, la fenêtre déclarée est lue.
  const reseauAvecBatterie = _specs(P('Onduleur réseau Huawei 5kW Monophasé', 14000),
                                    { famille: 'onduleur', plage_batterie_v: [350, 560] })
  assert.deepEqual(plageBatterieOnduleur(reseauAvecBatterie), [350, 560])
})

test('PVOND — un RÉSEAU complet n\'est plus grisé, un HYBRIDE sans plage l\'est encore', () => {
  const catalogue = SEEDED.map(p => {
    if (p.nom === 'Onduleur réseau Huawei 10kW Triphasé') {
      // Ce que le backend sert désormais : plage « aucune », rien ne manque.
      return _specs(p, { famille: 'onduleur', plage_batterie_v: [0, 0], manquantes: [] })
    }
    if (p.nom === 'Onduleur hybride Deye 10kW Triphasé') {
      return _specs(p, { famille: 'onduleur',
                         manquantes: ['plage de tension batterie (V)'] })
    }
    return p
  })

  const rows = autoFillLines(catalogue, { kwp: 10, panelW: 710, structureType: 'acier' })

  const noms = rows.onduleursIncomplets.map(o => o.nom)
  assert.ok(!noms.includes('Onduleur réseau Huawei 10kW Triphasé'),
            'un onduleur réseau ne doit plus être grisé pour la plage batterie')
  assert.ok(noms.includes('Onduleur hybride Deye 10kW Triphasé'),
            'un hybride sans plage batterie doit rester écarté ET nommé')
  assert.deepEqual(
    rows.onduleursIncomplets.find(o => o.nom === 'Onduleur hybride Deye 10kW Triphasé').manquantes,
    ['plage de tension batterie (V)'])
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
    P('Batterie Dyness 10 kWh', 30000),
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
  prixParKwc, discountForTarget, computeBuyCost,
  expectedTvaForDesignation,
} from './solar.js'

// ══ Classification pompe (le moteur pompage JS est retiré, AGR132) ═══════════
import { isPompe } from './solar.js'

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

// ── QJR130 — jamais de repli silencieux sur un matériel sous-dimensionné ──────
// ── QJR131 — `_hasPrix` couvre AUSSI panneaux/structures/socles/câble/
// installation/transport (avant : réservé pompe/variateur/afficheur) : un
// candidat sans prix n'est plus jamais chiffré, repli sur un placeholder
// (aucun `produit`, jamais un article gratuit à id réel) ─────────────────────
const POMPAGE_ARGS = {
  cv: '5.5', alim: 'tri', typePompe: 'immergee', distance: '35', structureType: 'acier',
}
const zeroed = (produits, matches) => produits.map(p =>
  matches.some(m => p.nom.includes(m)) ? { ...p, prix_vente: '0.00' } : p)

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

// QJR567 — le coût d'achat (marge du générateur) suit la MÊME population que
// les totaux : ni ligne optionnelle (add-on non activé), ni section/note.
test('QJR567 computeBuyCost ignore une ligne optionnelle et les sections/notes', () => {
  const produits = [
    { id: 1, nom: 'Panneau X', prix_vente: '1000', prix_achat: '800' },
    { id: 3, nom: 'Borne de recharge', prix_vente: '5000', prix_achat: '4000' },
  ]
  const normale = { produit: '1', designation: 'Panneau X', quantite: '10', prix_unit_ttc: '1100' }
  const lines = [
    normale,
    { produit: '3', designation: 'Borne de recharge', quantite: '1', prix_unit_ttc: '6000', optionnelle: true },
    { produit: '1', designation: 'Section toiture', quantite: '1', prix_unit_ttc: '0', typeLigne: 'section' },
    { produit: '1', designation: 'Note', quantite: '1', prix_unit_ttc: '0', typeLigne: 'note' },
  ]
  assert.equal(computeBuyCost(lines, produits), computeBuyCost([normale], produits))
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

test('QF4 — monthlyBillFromKwh : barème ONEE SÉLECTIF (300 kWh/mois)', () => {
  // BARÈME SÉLECTIF (grille officielle, cf. solar.js) : au-dessus de 150
  // kWh/mois, TOUTE la conso est facturée au tarif de SA tranche. 300 kWh/mois
  // tombe dans la bande 201-300 (bornes effectives 211-310, tolérance 10 kWh)
  // → tarif 1,187388 sur les 300 kWh (2026, TVA 20%).
  // Dérivation à la main : 300 × 1,187388 = 356,2164 MAD/mois.
  assert.ok(Math.abs(monthlyBillFromKwh(300, ONEE_TRANCHES) - 356.2164) < 1e-9)
  // La bande d'EN DESSOUS (progressive, ≤ 150) reste cumulative :
  // 100 × 0,916272 + 50 × 1,091388 = 91,6272 + 54,5694 = 146,1966 MAD/mois.
  assert.ok(Math.abs(monthlyBillFromKwh(150, ONEE_TRANCHES) - 146.1966) < 1e-9)
})

test('QF4 — kwhFromBill : inverse EXACT du barème sélectif', () => {
  // Facture atteignable : 700 × 1,622856 = 1 135,9992 MAD/mois → 700 kWh/mois.
  const r = kwhFromBill(1135.9992, 'onee')
  assert.equal(r.kwhMensuel, 700)
  assert.equal(r.approximatif, false)
  assert.equal(r.estimation, false)
  // 850 MAD/mois tombe dans un TROU du barème : la bande 301-500 plafonne à
  // 510 × 1,381704 = 704,66904 MAD et la bande supérieure démarre au-dessus de
  // 511 × 1,622856 = 829,279416 MAD… mais 850 MAD EST atteignable au-dessus de
  // 510 : 850 / 1,622856 = 523,7998… kWh (> 510, donc bien dans sa bande) →
  // arrondi 523,8.
  assert.equal(kwhFromBill(850, 'onee').kwhMensuel, 523.8)
  // Vrai trou : 235 MAD/mois. À 210 kWh la facture vaut 210 × 1,091388 =
  // 229,19148 ; au premier kWh au-dessus elle saute à 211 × 1,187388 =
  // 250,538868. Aucune conso ne produit 235 MAD → on résout à la BORNE BASSE
  // du saut (210 kWh), jamais une conso que le barème ne peut pas produire
  // (règle miroir en Python).
  assert.equal(kwhFromBill(235, 'onee').kwhMensuel, 210)
})

test('Q7 (fondateur 20/08) — kwhFromBill : Lydec/Redal = LA grille nationale, plus d\'approximation', () => {
  // Il n'existe pas de grille Lydec/Redal distincte : les distributeurs
  // appliquent la grille nationale unique — même inversion, même résultat
  // que l'ONEE, et le drapeau « approximatif » n'a plus d'objet.
  const onee = kwhFromBill(500, 'onee')
  for (const distributeur of ['lydec', 'redal']) {
    const r = kwhFromBill(500, distributeur)
    assert.deepEqual(r, onee, distributeur)
    assert.equal(r.approximatif, false, distributeur)
  }
})

test('QF4/CAD167 — kwhFromBill : SANS distributeur → repli FALLBACK_KWH_PRICE, étiqueté estimation', () => {
  // Même règle que test_cad167 test_SANS_distributeur_le_comportement_d_avant_est_conserve.
  for (const aucun of [undefined, null, '', '  ']) {
    const r = kwhFromBill(120, aucun)
    assert.equal(r.kwhMensuel, Math.round((120 / FALLBACK_KWH_PRICE) * 10) / 10)
    assert.equal(r.estimation, true)
  }
})

test('CAD167 — kwhFromBill : un distributeur NOMMÉ hors table (SRM, « autre ») lit la grille nationale', () => {
  // Même règle que pricing._resolve_tranches (test_cad167 test_autre_cesse_de_casser_la_courbe) :
  // AVANT, 'srm_casablanca' divisait la facture par 1,20 — DEV-202609-0113.
  const onee = kwhFromBill(22000, 'onee')
  for (const code of ['srm_casablanca', 'srm_rabat', 'autre', 'amendis', 'inconnu']) {
    const r = kwhFromBill(22000, code)
    assert.deepEqual(r, onee, code)
    assert.equal(r.estimation, false, code)
  }
  assert.notEqual(onee.kwhMensuel, Math.round((22000 / FALLBACK_KWH_PRICE) * 10) / 10)
})

test('QF4 — kwhFromBill : facture vide → 0 kWh, estimation', () => {
  const r = kwhFromBill(0, 'onee')
  assert.equal(r.kwhMensuel, 0)
  assert.equal(r.estimation, true)
})

// QJR168 — les factures ci-dessous portent le barème COMPLET (énergie + les
// deux lignes fixes + TPPAN), jumeau de bareme.facture_mad : 39,936 MAD TTC de
// location/entretien par mois (479,23/an) et une TPPAN empilée 0,10/0,15/0,20,
// bornes 100/200 kWh, plafonnée à 100 MAD/mois, nulle sous 50 kWh/mois.
test('QF2/QF5 — twoBillsSavings : économie réelle au barème (ratio 0.60, sans batterie)', () => {
  // Dérivation à la main (barème SÉLECTIF, 2026 — TVA 20 %) :
  //   conso    7 200/12 = 600 kWh/mois → > 510 → 600 × 1,622856 = 973,7136
  //                                            MAD/mois × 12 = 11 684,5632
  //     TPPAN  10 + 15 + 400 × 0,20 = 105 → PLAFOND 100 MAD/mois × 12 = 1 200
  //     fixes  479,23 → facture 11 684,5632 + 479,232 + 1 200 = 13 363,80 → 13 364
  //   autoconsommé 6 000 × 0,60 = 3 600 kWh (≤ conso) → résiduel 3 600 kWh/an
  //   résiduel 3 600/12 = 300 kWh/mois → bande 211-310 → 300 × 1,187388 =
  //                                            356,2164 × 12 = 4 274,5968
  //     TPPAN  10 + 15 + 100 × 0,20 = 45 MAD/mois × 12 = 540
  //     fixes  479,23 → facture 4 274,5968 + 479,232 + 540 = 5 293,83 → 5 294
  //   économie 13 364 − 5 294 = 8 070 MAD/an
  const r = twoBillsSavings(6000, 7200, 0.6, 'onee')
  assert.deepEqual(r, {
    factureSans: 13364, factureAvec: 5294, economie: 8070, autoconsoKwh: 3600,
  })
})

test('QF2/QF5 — twoBillsSavings : économie réelle au barème (ratio 0.85, avec batterie)', () => {
  // Dérivation à la main (barème SÉLECTIF, 2026 — TVA 20 %) :
  //   autoconsommé 6 000 × 0,85 = 5 100 kWh → résiduel 2 100 kWh/an
  //   résiduel 2 100/12 = 175 kWh/mois → bande 151-210 → 175 × 1,091388 =
  //                                            190,9929 × 12 = 2 291,9148
  //     TPPAN  10 + 75 × 0,15 = 21,25 MAD/mois × 12 = 255
  //     fixes  479,23 → facture 2 291,9148 + 479,232 + 255 = 3 026,15 → 3 026
  //   économie 13 364 − 3 026 = 10 338 MAD/an
  // En redescendant sous 510 PUIS sous 310, le client ne fait pas qu'effacer
  // des kWh : il RE-TARIFE tout son résiduel (1,622856 → 1,091388), et sa
  // TPPAN dégringole avec lui (les lignes fixes, elles, s'annulent).
  const r = twoBillsSavings(6000, 7200, 0.85, 'onee')
  assert.deepEqual(r, {
    factureSans: 13364, factureAvec: 3026, economie: 10338, autoconsoKwh: 5100,
  })
})

// ── VERROU DE DÉRIVE — barème SÉLECTIF : JS ↔ Python ↔ site ─────────────────
// Jumeau EXACT de apps/ventes/tests/test_bareme_selectif_fondateur.py (ERP) et
// de apps/web/tests/savingsTranchesFondateur.test.ts (site public). Les trois
// fichiers portent les MÊMES entrées et les MÊMES attendus, tous DÉRIVÉS À LA
// MAIN de la grille officielle (jamais copiés d'une sortie de code).
//
// ÉCART TEMPORAIRE ASSUMÉ ET DATÉ (QJR26, 29/08/2026) : la correction T5
// ci-dessous est portée sur les DEUX branches ERP (ce fichier + le jumeau
// Python), PAS sur la branche site — apps/web/** est une tâche séparée (QJW).
// Tant qu'elle n'a pas atterri, savingsTranchesFondateur.test.ts reste sur
// l'ancienne valeur. Le verrou à trois branches se referme avec QJW.
//
// Grille (TTC, 2026 — TVA 20 %) : progressif 0-100 = 0,916272 ·
// 101-150 = 1,091388 ; sélectif (toute la conso au tarif de sa tranche,
// tolérance 10 kWh) : 151-210 = 1,091388 · 211-310 = 1,187388 ·
// 311-510 = 1,381704 · > 510 = 1,622856.
//
// DÉCISION FONDATEUR D5 (29/08/2026) — T5 RECALÉE SUR LA FACTURE : 311-510
// vaut 1,381704 (facture SRM n° 643769639 du 08/05/2026 : 359 kWh × 1,15142 HT
// = 496,03 TTC ⇒ 1,15142 × 1,20), et non l'extrapolation « HT constant ». TOUS
// les attendus T5 ci-dessous ont été RE-DÉRIVÉS À LA MAIN de 1,381704.
const BAREME_FIXTURE = [
  [100, 91.6272],      // progressif : 100 × 0,916272
  [150, 146.1966],     // progressif : 91,6272 + 50 × 1,091388 (= 54,5694)
  [151, 164.799588],   // 1re marche sélective : 151 × 1,091388
  [210, 229.19148],    // haut de bande (tolérance) : 210 × 1,091388
  [211, 250.538868],   // bande suivante, TOUTE la conso : 211 × 1,187388
  [310, 368.09028],    // 310 × 1,187388
  [311, 429.709944],   // 311 × 1,381704
  [499, 689.470296],   // 499 × 1,381704
  [500, 690.852],      // 500 × 1,381704 — le seuil « 500 » du fondateur
  [501, 692.233704],   // 501 × 1,381704 (encore dans sa bande : borne effective 510)
  [510, 704.66904],    // 510 × 1,381704
  [511, 829.279416],   // 511 × 1,622856 — la marche du haut de grille
  [700, 1135.9992],    // 700 × 1,622856
]

test('VERROU — barème sélectif : chaque marche vaut le montant dérivé à la main', () => {
  for (const [kwh, mad] of BAREME_FIXTURE) {
    assert.ok(Math.abs(monthlyBillFromKwh(kwh, ONEE_TRANCHES) - mad) < 1e-9,
      `${kwh} kWh/mois → attendu ${mad} MAD, obtenu ${monthlyBillFromKwh(kwh, ONEE_TRANCHES)}`)
  }
  // La facture ne décroît JAMAIS quand la conso monte (monotonie du barème).
  for (let i = 1; i < BAREME_FIXTURE.length; i++) {
    assert.ok(BAREME_FIXTURE[i][1] > BAREME_FIXTURE[i - 1][1])
  }
  // 511 kWh coûte 124,610376 MAD de plus que 510 kWh pour UN kWh de plus :
  // c'est la marche sélective (829,279416 − 704,66904), pas une erreur d'arrondi.
  // La marche a GRANDI avec la correction D5 : son bas est descendu à 1,381704
  // alors que son haut (1,622856) n'a pas bougé.
  assert.ok(Math.abs((829.279416 - 704.66904) - 124.610376) < 1e-9)
})

test('VERROU — kwhFromBill est l’inverse EXACT sur toute la grille (aller-retour)', () => {
  for (const [kwh] of BAREME_FIXTURE) {
    assert.equal(kwhFromBill(monthlyBillFromKwh(kwh, ONEE_TRANCHES), 'onee').kwhMensuel, kwh)
  }
})

test('VERROU — scénario FONDATEUR : 700 kWh/mois, résiduel sous le seuil', () => {
  // « The client will go down in the price per kWh because he will be below
  //   500 kWh per month — I want the new price per kWh to be used. »
  // Dérivation à la main (2026 — TVA 20 %) :
  //   avant  700 kWh/mois → 700 × 1,622856 = 1 135,9992 MAD (1,622856 MAD/kWh)
  //   après  280 kWh/mois → 280 × 1,187388 =   332,46864 MAD (1,187388 MAD/kWh)
  //   économie 1 135,9992 − 332,46864 = 803,53056 MAD/mois → × 12 = 9 642,3672 MAD/an
  const avant = monthlyBillFromKwh(700, ONEE_TRANCHES)
  const apres = monthlyBillFromKwh(280, ONEE_TRANCHES)
  assert.ok(Math.abs(avant - 1135.9992) < 1e-9)
  assert.ok(Math.abs(apres - 332.46864) < 1e-9)
  assert.ok(Math.abs((avant - apres) - 803.53056) < 1e-9)
  // Le PRIX du kWh baisse vraiment (c'est la phrase du fondateur).
  assert.ok(Math.abs(avant / 700 - 1.622856) < 1e-9)
  assert.ok(Math.abs(apres / 280 - 1.187388) < 1e-9)
  // …et l'économie vaut PLUS que les 420 kWh effacés au tarif marginal :
  // 420 × 1,622856 = 681,59952 MAD < 803,53056 MAD (le résiduel est re-tarifé).
  assert.ok(Math.abs(420 * 1.622856 - 681.59952) < 1e-9)
  assert.ok(803.53056 > 681.59952)
  // Annualisation : 803,53056 × 12 = 9 642,3672 → 9 642 MAD/an. Le mois est
  // l'unité de tarification (le seuil est MENSUEL) : on ne divise jamais
  // l'année avant de tarifer.
  assert.equal(Math.round((avant - apres) * 12), 9642)
})

test('twoBillsSavings : dégrade en null sans donnée réelle (jamais un chiffre inventé)', () => {
  assert.equal(twoBillsSavings(0, 7200, 0.6, 'onee'), null) // pas de production
  assert.equal(twoBillsSavings(6000, 0, 0.6, 'onee'), null) // pas de conso
  assert.equal(twoBillsSavings(6000, 7200, 0, 'onee'), null) // pas de ratio
  assert.equal(twoBillsSavings(6000, 7200, 0.6, undefined), null) // pas de barème
  // CAD167 — un distributeur NOMMÉ (SRM) n'est plus « pas de barème » : grille nationale.
  assert.deepEqual(twoBillsSavings(6000, 7200, 0.6, 'srm_casablanca'),
    twoBillsSavings(6000, 7200, 0.6, 'onee'))
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

test('QX38 — computeROI : production = productible × kwp × pertes 20 % (parité PDF/web)', () => {
  const kwp = 7.1
  const roi = computeROI({
    kwp, factures: Array(12).fill(500), dayUsagePct: 60,
    totalSans: 80000, totalAvec: 100000, batteryKwh: 0,
    productible: productibleForCity('Agadir'),
  })
  // ORDRE FONDATEUR (18/08) — 20 % de pertes AU TOTAL : le productible stocké
  // (PVGIS, déjà net de 14 %) ne subit que le complément 0,80/0,86 = 0,9302.
  // À la main : 1687 × 7,1 = 11 977,7 kWh bruts ; × 0,9302325581 = 11 142,05
  // → 11 142 kWh/an (le PDF calcule EXACTEMENT la même chose).
  assert.equal(Math.round(roi.production_annuelle_kwh),
    Math.round(1687 * kwp * PRODUCTIBLE_NET_FACTOR))
  assert.equal(Math.round(roi.production_annuelle_kwh), 11142)
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

test('QX39 — projection à TARIF CONSTANT (miroir pricing.py TARIFF_ESCALATION=0)', () => {
  // ALIGNEMENT 18/08 — l'écran supposait +2 %/an alors que le PDF et la page
  // proposition écrivent « projection à tarif constant » : le modèle doit FAIRE
  // ce qu'il dit. Seule la dégradation panneau (0,5 %/an) érode les économies.
  assert.equal(TARIFF_ESCALATION, 0)
  const cf = computeCashflowPayback(50000, 10000)
  // Année 1 : cumul = −50 000 + 10 000 = −40 000 (aucune indexation).
  assert.equal(cf.cumulative[0], -40000)
  // Année 2 : économie × (1 − 0,005) = 9 950 → cumul −30 050.
  assert.equal(cf.cumulative[1], -30050)
})

test('QX39 — computeCashflowPayback : dégénéré → payback null', () => {
  assert.equal(computeCashflowPayback(0, 10000).paybackYears, null)
  assert.equal(computeCashflowPayback(50000, 0).paybackYears, null)
})

test('ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — drapeau jamaisRembourse (même règle que pricing)', () => {
  const jamais = computeCashflowPayback(269065, 3000)
  assert.equal(jamais.jamaisRembourse, true)
  assert.ok(jamais.cumulative[jamais.cumulative.length - 1] < 0)
  assert.equal(computeCashflowPayback(50000, 10000).jamaisRembourse, false)
  assert.equal(computeCashflowPayback(0, 10000).jamaisRembourse, false)
})

test('QX39 — batterie (rendement aller-retour) allonge le payback', () => {
  const no = computeCashflowPayback(50000, 10000)
  const bat = computeCashflowPayback(50000, 10000, { battery: true })
  assert.ok(bat.paybackYears >= no.paybackYears)
})

// ── Z5 (ORDRE FONDATEUR, 20/08/2026) — le rendement aller-retour batterie ne
// frappe QUE la part de l'économie qui transite RÉELLEMENT par elle, jamais
// 100 % (miroir pricing.py compute_cashflow_payback, batt_factor). ──────────
test('Z5 — batteryShare borne la perte aller-retour à la part réellement stockée', () => {
  // Investissement 50 000, économie année 1 = 10 000 MAD, moitié de
  // l'économie transite par la batterie (batteryShare = 0,5).
  //   batt_factor = 1 − (1 − 0,90) × 0,5 = 1 − 0,05 = 0,95
  //   Année 1 (dégradation/escalade = ×1 encore) :
  //     yearSaving = 10 000 × 0,95 = 9 500 → cumul = −50 000 + 9 500 = −40 500
  const half = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 0.5 })
  assert.equal(half.cumulative[0], -40500)

  // batteryShare = 0 : RIEN ne transite par la batterie (tout est autoconsommé
  // au fil du soleil) → aucune perte → IDENTIQUE au cashflow sans batterie.
  const zero = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 0 })
  const none = computeCashflowPayback(50000, 10000)
  assert.deepEqual(zero.cumulative, none.cumulative)

  // batteryShare = 1 (toute l'économie transite) et batteryShare = null/absent
  // (repli historique, appelant direct sans décomposition) sont IDENTIQUES au
  // forfait plein 0,90 sur 100 % — comportement inchangé pour ces appelants.
  const full = computeCashflowPayback(50000, 10000, { battery: true, batteryShare: 1 })
  const legacy = computeCashflowPayback(50000, 10000, { battery: true })
  assert.deepEqual(full.cumulative, legacy.cumulative)
  assert.equal(legacy.cumulative[0], -50000 + 10000 * BATTERY_ROUNDTRIP) // −41 000

  // AVANT Z5, batteryShare était ignoré : la part diurne directe (qui ne
  // traverse jamais la batterie) payait quand même 10 % de perte — une double
  // peine qui allongeait le payback « avec batterie ». Le payback à
  // batteryShare=0,5 doit désormais se situer STRICTEMENT ENTRE les deux bornes.
  assert.ok(half.paybackYears >= zero.paybackYears)
  assert.ok(half.paybackYears <= legacy.paybackYears)
})

// ── Q1 (ORDRE FONDATEUR, 20/08/2026) — la provision de remplacement onduleur
// (année 12) vaut le PRIX RÉEL de la ligne onduleur du devis, jamais un
// pourcentage forfaitaire de l'investissement (miroir pricing.py
// compute_cashflow_payback + builder.py _cout_onduleur). ─────────────────────
test('Q1 — computeCashflowPayback : la provision = prix RÉEL, jamais 8 % de l\'investissement', () => {
  const investment = 80000
  const economieAnnee1 = 12000
  const withoutProvision = computeCashflowPayback(investment, economieAnnee1)
  // Prix réel d'une ligne onduleur — délibérément DIFFÉRENT de l'ancien
  // forfait 8 % (0,08 × 80 000 = 6 400) pour prouver qu'il n'est plus utilisé.
  const realInverterPrice = 15300
  assert.notEqual(realInverterPrice, Math.round(investment * 0.08))
  const withProvision = computeCashflowPayback(investment, economieAnnee1, {
    inverterReplaceCost: realInverterPrice,
  })
  // Avant l'année de remplacement (12) : STRICTEMENT AUCUNE différence.
  for (let i = 0; i < INVERTER_REPLACE_YEAR - 1; i++) {
    assert.equal(withProvision.cumulative[i], withoutProvision.cumulative[i],
      `année ${i + 1} : la provision ne doit rien changer avant l'année ${INVERTER_REPLACE_YEAR}`)
  }
  // À l'année 12 (indice 11) et pour tout le reste de la projection : le cumul
  // « avec provision » est en retrait EXACTEMENT du prix réel de l'onduleur —
  // jamais un pourcentage (round(a) − round(a − k) = k pour k entier : la
  // preuve tient quelle que soit la valeur exacte du cumul non arrondi).
  for (let i = INVERTER_REPLACE_YEAR - 1; i < 25; i++) {
    assert.equal(
      withoutProvision.cumulative[i] - withProvision.cumulative[i],
      realInverterPrice,
      `année ${i + 1} : écart ≠ prix réel de l'onduleur`)
  }
  // Aucune ligne onduleur identifiable (inverterReplaceCost null/absent) :
  // AUCUNE provision — jamais un repli sur un pourcentage.
  const omitted = computeCashflowPayback(investment, economieAnnee1, { inverterReplaceCost: null })
  assert.deepEqual(omitted.cumulative, withoutProvision.cumulative)
})

test('Q1 — computeROI dérive la provision onduleur des VRAIES lignes (sans/avec), jamais un forfait', () => {
  const lignes = [
    { designation: 'Onduleur réseau Huawei 10kW Triphasé', quantite: '1', prix_unit_ttc: '20000' },
    { designation: 'Onduleur hybride Deye 10kW Triphasé', quantite: '1', prix_unit_ttc: '28000' },
    { designation: 'Batterie Dyness 10 kWh', quantite: '1', prix_unit_ttc: '17000' },
    { designation: 'Panneau Canadien Solar 710W', quantite: '14', prix_unit_ttc: '1400' },
  ]
  // « sans » exclut batterie + onduleur hybride (miroir optionTotalsTTC /
  // builder.py sans_items) → il ne reste que le réseau (20 000 MAD).
  // « avec » exclut l'onduleur réseau (miroir avec_items) → il ne reste que
  // l'hybride (28 000 MAD).
  const linesSans = lignes.filter(l => !isBattery(l.designation) && !isHybridInverter(l.designation))
  const linesAvec = lignes.filter(l => !isReseauInverter(l.designation))
  assert.equal(inverterCostFromLines(linesSans), 20000)
  assert.equal(inverterCostFromLines(linesAvec), 28000)
  assert.equal(isAnyInverter('Onduleur réseau Huawei 10kW Triphasé'), true)
  assert.equal(isAnyInverter('Panneau Canadien Solar 710W'), false)

  const base = {
    kwp: 10, factures: Array(12).fill(1500), dayUsagePct: 60,
    totalSans: 100000, totalAvec: 140000, batteryKwh: batteryKwhFromLines(lignes),
  }
  const withLines = computeROI({ ...base, lines: lignes })
  const withoutLines = computeROI({ ...base, lines: [] })
  // La provision ne touche QUE le cashflow/payback, jamais l'économie année 1.
  assert.equal(withLines.eco_annuelle_avec, withoutLines.eco_annuelle_avec)
  // Écart exact = prix RÉEL de l'onduleur hybride (28 000), jamais 8 % de
  // l'investissement « avec » (0,08 × 140 000 = 11 200).
  assert.notEqual(28000, Math.round(base.totalAvec * 0.08))
  assert.equal(
    withoutLines.cashflow_avec[INVERTER_REPLACE_YEAR - 1]
      - withLines.cashflow_avec[INVERTER_REPLACE_YEAR - 1],
    28000)
  // Le côté « sans » porte SA PROPRE provision (l'onduleur réseau, 20 000) —
  // jamais mélangée avec celle de l'option « avec ».
  assert.equal(
    withoutLines.cashflow_sans[INVERTER_REPLACE_YEAR - 1]
      - withLines.cashflow_sans[INVERTER_REPLACE_YEAR - 1],
    20000)
})

// ── M9 (audit du 19/08/2026) — l'option « avec batterie » ne porte le
// rendement aller-retour QUE lorsqu'une VRAIE batterie est chiffrée sur le
// devis (dérivé de batteryKwhFromLines(lignes) > 0), jamais codé en dur. ─────
test('M9 — la présence de batterie vient des VRAIES lignes, jamais codée en dur', () => {
  const base = {
    kwp: 8, factures: Array(12).fill(1200), dayUsagePct: 60,
    totalSans: 90000, totalAvec: 90000, kwhPrice: 1.20,
  }
  // batteryKwh=0 (aucune vraie batterie) : le cashflow « avec » doit être
  // STRUCTURELLEMENT IDENTIQUE à un cashflow sans aucune perte de batterie —
  // avant M9, `battery: true` était codé en dur pour l'option 2 et infligeait
  // quand même 10 % de perte à un devis qui ne porte aucune batterie.
  const roiNoBattery = computeROI({ ...base, batteryKwh: 0 })
  const refNoBattery = computeCashflowPayback(base.totalAvec, roiNoBattery.eco_annuelle_avec)
  assert.deepEqual(roiNoBattery.cashflow_avec, refNoBattery.cumulative)
  assert.equal(roiNoBattery.payback_avec, refNoBattery.paybackYears)

  // Avec une VRAIE capacité (10 kWh) sur les mêmes entrées par ailleurs : la
  // perte aller-retour DOIT désormais s'appliquer — le cashflow diverge du
  // cashflow « sans aucune perte » calculé sur la MÊME économie avec batterie.
  const roiWithBattery = computeROI({ ...base, batteryKwh: 10 })
  const refWithBatteryNoLoss = computeCashflowPayback(
    base.totalAvec, roiWithBattery.eco_annuelle_avec)
  assert.notDeepEqual(roiWithBattery.cashflow_avec, refWithBatteryNoLoss.cumulative)
})

// ── QX40 — pompage : compatibilité phase/tension pompe ↔ variateur ──────────
const _curvePump = (nom, kw, tension, prix, courbe) => ({
  id: ++_id, nom, pompe_kw: kw, tension_v: tension, prix_vente: prix,
  courbe_pompe: courbe,
})
// courbe simple : à HMT 60 m délivre 40 m³/h (≥ le débit demandé de 30)
const _COURBE = { debits_m3h: [0, 40, 60], hmt_m: [90, 60, 30] }

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
  // ALIGNEMENT 18/08 — cette production est ARRONDIE à l'entier avant le modèle
  // par tranches, comme le fait le moteur PDF (pricing.calculate_savings_roi) :
  // écran et document tombent ainsi du même côté des arrondis de tranche.
  const prodCanonique = Math.round(prodAnnuelle)
  const refSans = twoBillsSavings(prodCanonique, consoAnnuelleKwh, AUTOCONSO_SANS, 'onee')
  const refAvec = twoBillsSavings(prodCanonique, consoAnnuelleKwh, AUTOCONSO_AVEC, 'onee')
  assert.equal(roi.eco_annuelle_sans, refSans.economie)
  assert.equal(roi.eco_annuelle_avec, refAvec.economie)
  assert.equal(roi.facture_sans, refSans.factureSans)
  assert.equal(roi.facture_avec_sans, refSans.factureAvec)
  assert.equal(roi.facture_avec_avec, refAvec.factureAvec)
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
  // Chaîne canonique (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER) : 34 000,04, que
  // l'ARRONDI-100 ramène au palier de 100 MAD inférieur (noyau : même palier).
  assert.equal(r.totalUnitaireSans, totauxCanoniquesTtc(lines, 0, PAS_ARRONDI_DEVIS))
  assert.equal(r.totalUnitaireSans, 34000)
  // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N au CENTIME (miroir backend) : unitaire × 3.
  // ARRONDI-100 : 102 000,12 → palier de 100 inférieur (unitaire arrondi AVANT le ×N).
  assert.equal(r.totalMultiSans, 102000)
})

test('QJ31 mode A — ×N applique aussi la remise (unitaire remisé × N)', () => {
  const lines = [L('Panneaux', 10, 1400), L('Onduleur réseau', 1, 20000)] // 34000 brut
  const r = multiPropertyPreviewTTC(lines, { nombreProprietes: '2', discountPct: '10' })
  // Chaîne canonique (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER) : 30 600,04, que
  // l'ARRONDI-100 ramène au palier de 100 MAD inférieur (noyau : même palier).
  assert.equal(r.totalUnitaireSans, totauxCanoniquesTtc(lines, 10, PAS_ARRONDI_DEVIS))
  assert.equal(r.totalUnitaireSans, 30600)
  // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N au CENTIME : unitaire × 2.
  // ARRONDI-100 : 61 200,08 → palier de 100 inférieur (unitaire arrondi AVANT le ×N).
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

const ETUDE_BASE = {
  kwp: 300, consoMensuelleKwh: 20000, dayUsagePct: 80,
  totalTtc: 900000, kwhPrice: 1.4, efficiency: 0.8,
}

// STKCAT24 — `groupProduitsByCategory` bucket sur le rôle EFFECTIF résolu
// côté serveur (`role_devis_effectif`, STKCAT21) quand il est présent, mots-
// clés du nom en repli. Pin explicite : la fixture SEEDED existante (aucun
// produit n'y porte `role_devis_effectif`) doit grouper à l'IDENTIQUE
// d'avant STKCAT24 — même sélecteur, même compte par étiquette que le test
// « sélecteur produits : groupé selon les catégories du catalogue simulateur »
// ci-dessus (jamais retouché).
test('STKCAT24 — sans role_devis_effectif (fixture ancienne) : groupage byte-identique à avant', () => {
  const groups = groupProduitsByCategory(SEEDED)
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Onduleur Injection').items.length, 10)
  assert.equal(by('Onduleur Hybride').items.length, 5)
  assert.equal(by('Panneaux').items.length, 2)
  assert.equal(by('Batterie').items.length, 4)
  assert.equal(by('Structures acier').items.length, 1)
  assert.equal(by('Structures aluminium').items.length, 1)
  // Un `role_devis_effectif` explicitement NULL (et pas seulement absent) doit
  // suivre exactement le même repli que le champ absent.
  const avecNull = SEEDED.map(p => ({ ...p, role_devis_effectif: null }))
  const groupsNull = groupProduitsByCategory(avecNull)
  assert.deepEqual(
    groupsNull.map(g => [g.label, g.items.length]),
    groups.map(g => [g.label, g.items.length]))
})

test('STKCAT24 — role_devis_effectif="panneau" sans mot-clé dans le nom : bucketé Panneaux', () => {
  const sansMotCle = { id: 9001, nom: 'Module ABC-550', prix_vente: '750',
    role_devis_effectif: 'panneau' }
  const groups = groupProduitsByCategory([...SEEDED, sansMotCle])
  const panneaux = groups.find(g => g.label === 'Panneaux')
  assert.ok(panneaux.items.some(p => p.id === 9001),
    'le produit sans mot-clé mais au rôle effectif "panneau" doit rejoindre le groupe Panneaux')
})

test('STKCAT24 — structure : rôle effectif générique + mot-clé matière du nom (acier/alu/aucun)', () => {
  const acier = { id: 9010, nom: 'Charpente acier galvanisée', prix_vente: '400',
    role_devis_effectif: 'structure' }
  const alu = { id: 9011, nom: 'Support aluminium sur mesure', prix_vente: '450',
    role_devis_effectif: 'structure' }
  const generique = { id: 9012, nom: 'Pergola', prix_vente: '500',
    role_devis_effectif: 'structure' }
  const groups = groupProduitsByCategory([acier, alu, generique])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Structures acier')?.items?.[0]?.id, 9010)
  assert.equal(by('Structures aluminium')?.items?.[0]?.id, 9011)
  // Aucun mot-clé matière dans le nom → seau générique 'structure', rendu
  // sous l'étiquette 'Structures' (clé ajoutée par STKCAT2 à PRODUCT_CATEGORIES).
  assert.equal(by('Structures')?.items?.[0]?.id, 9012)
})

test('STKCAT24 — structure_acier/alu DÉCLARÉ explicitement : bucketé tel quel, jamais re-décidé par le nom', () => {
  // Le nom ne dit ni « acier » ni « alu » — seul le rôle DÉCLARÉ tranche.
  const declareAcier = { id: 9020, nom: 'Charpente sur mesure', prix_vente: '400',
    role_devis_effectif: 'structure_acier' }
  const declareAlu = { id: 9021, nom: 'Support sur mesure', prix_vente: '450',
    role_devis_effectif: 'structure_alu' }
  const groups = groupProduitsByCategory([declareAcier, declareAlu])
  const by = (label) => groups.find(g => g.label === label)
  assert.equal(by('Structures acier')?.items?.[0]?.id, 9020)
  assert.equal(by('Structures aluminium')?.items?.[0]?.id, 9021)
})

/* ── STKCAT10 — LE SÉLECTEUR DE STRUCTURES PILOTÉ PAR LE CATALOGUE ──────────
   Décision fondateur 16/09/2026 : le bouton acier/aluminium est remplacé par
   un choix de PRODUIT. Les trois garanties épinglées ici :
     1. SANS produit choisi, la composition est BYTE-IDENTIQUE à l'historique
        (la paire acier + alu, l'une à nbPanneaux, l'autre à 0) ;
     2. AVEC un produit choisi, UNE SEULE ligne structure, au nom du produit ;
     3. le RÔLE émis suit le NOM du produit, exactement comme le serveur
        (`composition.py::role_structure_du_produit`) — donc une pergola porte
        le rôle GÉNÉRIQUE `structure`, jamais `structure_acier` par défaut. */

// Une PERGOLA : catégorie TYPÉE `structure`, mais dont le NOM ne contient ni
// « structure », ni « acier », ni « alu » — invisible pour le classifieur par
// mots-clés, atteignable UNIQUEMENT par son id (c'est tout le chantier).
const PERGOLA = {
  ...P('Pergola bioclimatique 4x3', 12000),
  categorie_type: 'structure',
  categorie: { nom: 'Pergolas', ordre: 5, type_equipement: 'structure' },
}
const SEEDED_PERGOLA = [...SEEDED, PERGOLA]
const KWP14 = 14 * 710 / 1000

test('STKCAT10 — structureRoleForName : MIROIR EXACT de role_structure_du_produit (serveur)', () => {
  assert.equal(structureRoleForName('Structures acier'), 'structure_acier')
  assert.equal(structureRoleForName('Structures aluminium'), 'structure_alu')
  // Ni l'un ni l'autre ⇒ rôle GÉNÉRIQUE (STKCAT2), jamais acier par défaut.
  assert.equal(structureRoleForName('Pergola bioclimatique 4x3'), 'structure')
  assert.equal(structureRoleForName('Bac lesté béton'), 'structure')
  // `voulu` départage un nom qui porte LES DEUX mots-clés…
  assert.equal(structureRoleForName('Structure acier et aluminium', 'aluminium'), 'structure_alu')
  assert.equal(structureRoleForName('Structure acier et aluminium', 'acier'), 'structure_acier')
  // …et c'est aussi le rôle rendu quand aucun nom n'est lisible.
  assert.equal(structureRoleForName('', 'aluminium'), 'structure_alu')
  assert.equal(structureRoleForName(null), 'structure_acier')
})

test('STKCAT10 — structureChoisie : id résolu sur le catalogue COMPLET, après la garde de prix', () => {
  assert.equal(structureChoisie(SEEDED_PERGOLA, PERGOLA.id).nom, 'Pergola bioclimatique 4x3')
  // Chaîne ou entier, même résolution (l'écran envoie des chaînes).
  assert.equal(structureChoisie(SEEDED_PERGOLA, String(PERGOLA.id)).id, PERGOLA.id)
  // Id inconnu / vide ⇒ rien (on retombe sur le bouton acier/alu).
  assert.equal(structureChoisie(SEEDED_PERGOLA, 99999), null)
  assert.equal(structureChoisie(SEEDED_PERGOLA, ''), null)
  assert.equal(structureChoisie(SEEDED_PERGOLA, null), null)
  // Produit NON TARIFÉ ⇒ rien : une composition ne cote jamais un prix absent
  // (même garde que le serveur, qui résout l'id APRÈS `_has_price`).
  const sansPrix = {
    id: 7777, nom: 'Carport (prix à renseigner)', prix_vente: '0',
    categorie_type: 'structure',
  }
  assert.equal(structureChoisie([...SEEDED_PERGOLA, sansPrix], 7777), null)
})

test('STKCAT10 — SANS produit choisi : composition BYTE-IDENTIQUE à l historique', () => {
  const base = { kwp: KWP14, panelW: 710, structureType: 'acier' }
  const avant = autoFillLines(SEEDED_PERGOLA, base)
  // Les trois façons de « ne pas choisir » donnent le MÊME tableau, au
  // caractère près, que l'appel historique sans le paramètre.
  for (const vide of [undefined, null, '']) {
    assert.deepEqual(
      autoFillLines(SEEDED_PERGOLA, { ...base, structureProduitId: vide }), avant,
      `structureProduitId=${JSON.stringify(vide)} doit être un no-op`)
  }
  // …et un id qui ne résout RIEN (autre société / produit sans prix) aussi.
  assert.deepEqual(autoFillLines(SEEDED_PERGOLA, { ...base, structureProduitId: 99999 }), avant)
  // La paire d'hier est bien là : acier à 14, aluminium à 0.
  const acier = avant.find(r => r.designation.includes('acier'))
  const alu = avant.find(r => r.designation.includes('aluminium'))
  assert.equal(acier.quantite, 14)
  assert.equal(alu.quantite, 0)
})

test('STKCAT10 — AVEC une pergola choisie : UNE ligne, à son nom, rôle générique structure', () => {
  const rows = autoFillLines(SEEDED_PERGOLA, {
    kwp: KWP14, panelW: 710, structureType: 'acier',
    structureProduitId: PERGOLA.id,
  })
  const structures = rows.filter(r => String(r.produit) === String(PERGOLA.id))
  assert.equal(structures.length, 1, 'une seule ligne structure, jamais la paire')
  assert.equal(structures[0].designation, 'Pergola bioclimatique 4x3')
  assert.equal(structures[0].quantite, 14)
  assert.equal(structures[0].prix_unit_ttc, 12000)
  // La paire figée a DISPARU : plus aucune ligne « Structures acier/aluminium ».
  assert.equal(rows.filter(r => /Structures (acier|aluminium)/.test(r.designation)).length, 0)
  // LE RÔLE ÉMIS, prouvé par l'ordre : `ordreLignes: ['structure']` ne peut
  // remonter cette ligne en tête que si elle porte bien le rôle GÉNÉRIQUE.
  const ordonne = autoFillLines(SEEDED_PERGOLA, {
    kwp: KWP14, panelW: 710, structureType: 'acier',
    structureProduitId: PERGOLA.id, ordreLignes: ['structure'],
  })
  assert.equal(ordonne[0].designation, 'Pergola bioclimatique 4x3')
  // …et le rôle acier ne la classe PAS (ce serait l'ancien défaut implicite).
  const ordonneAcier = autoFillLines(SEEDED_PERGOLA, {
    kwp: KWP14, panelW: 710, structureType: 'acier',
    structureProduitId: PERGOLA.id, ordreLignes: ['structure_acier'],
  })
  assert.notEqual(ordonneAcier[0].designation, 'Pergola bioclimatique 4x3')
})

test('STKCAT10 — un produit choisi qui porte encore « aluminium » garde le rôle structure_alu', () => {
  const alu = SEEDED.find(p => p.nom === 'Structures aluminium')
  const rows = autoFillLines(SEEDED_PERGOLA, {
    kwp: KWP14, panelW: 710,
    // Le bouton dit « acier » : le PRODUIT choisi l'emporte intégralement,
    // les deux ne se combinent jamais (même règle que le serveur).
    structureType: 'acier', structureProduitId: alu.id,
    ordreLignes: ['structure_alu'],
  })
  assert.equal(rows[0].designation, 'Structures aluminium')
  assert.equal(rows[0].quantite, 14)
  assert.equal(rows.filter(r => /Structures acier/.test(r.designation)).length, 0)
})

test('STKCAT10 — un produit choisi ne déclenche AUCUNE « marque introuvable » de structure', () => {
  // Une marque épinglée sans AUCUN candidat au stock : SANS choix explicite,
  // c'est un vrai motif de refus (le devis partirait sans structure).
  const marques = { structure_acier: 'MarqueInexistante', structure_alu: 'MarqueInexistante' }
  const base = { kwp: KWP14, panelW: 710, structureType: 'acier', marques }
  const sans = autoFillLines(SEEDED_PERGOLA, base)
  const rolesSans = (sans.marquesManquantes ?? []).map((m) => m.role)
  assert.ok(rolesSans.includes('structure_acier'), 'sans choix, la marque manquante est consignée')

  // AVEC un produit choisi, le rôle n'est même pas consulté — miroir EXACT du
  // serveur, qui n'appelle `par_marque` que dans sa branche `else`. Sans cette
  // symétrie, une épingle orpheline ferait REFUSER un devis à pergola pour un
  // rôle qu'il n'utilise pas.
  const avec = autoFillLines(SEEDED_PERGOLA, { ...base, structureProduitId: PERGOLA.id })
  const rolesAvec = (avec.marquesManquantes ?? []).map((m) => m.role)
  assert.ok(!rolesAvec.some((r) => r.startsWith('structure')),
    `aucun rôle structure attendu, reçu ${JSON.stringify(rolesAvec)}`)
  // …et la pergola est bien la ligne structure, à sa quantité.
  assert.equal(avec.filter((r) => String(r.produit) === String(PERGOLA.id)).length, 1)
})

// QJR529 — la remise PAR LIGNE stockée (LigneDevis.remise) compte dans le
// même calcul que les totaux canoniques, comme `total_ht` = q × pu × (1 − remise/100)
// côté serveur : sinon l'écran ≠ le PDF.
test('QJR529 — totauxCanoniquesTtc applique la remise de ligne', () => {
  assert.equal(totauxCanoniquesTtc(
    [{ quantite: '1', prix_unit_ttc: '1200', taux_tva: 20, remise: '10' }], 0), 1080)
  // Remise absente / nulle : strictement inchangé.
  assert.equal(totauxCanoniquesTtc(
    [{ quantite: '1', prix_unit_ttc: '1200', taux_tva: 20 }], 0), 1200)
  // Taux mixtes + remise globale : la remise de ligne s'applique AVANT.
  // HT : 2 × 1000 × 0,5 = 1000 (10 %) + 1000 (20 %) → brut 2000, remise
  // globale 10 % → 1800 ; TVA 900 × 10 % + 900 × 20 % = 270 → 2070.
  assert.equal(totauxCanoniquesTtc([
    { quantite: '2', prix_unit_ttc: '1100', taux_tva: 10, remise: '50' },
    { quantite: '1', prix_unit_ttc: '1200', taux_tva: 20 },
  ], 10), 2070)
})

test('ERR-QJR576 — SCENARIOS_ALTERNATIVE est la liste unique de quote/scenarios.js (SCENARIOS_VALIDES)', async () => {
  const { SCENARIOS_ALTERNATIVE } = await import('./solar.js')
  const { SCENARIOS_VALIDES } = await import('./quote/sizingReducer.js')
  assert.equal(SCENARIOS_ALTERNATIVE, SCENARIOS_VALIDES)
  assert.deepEqual([...SCENARIOS_ALTERNATIVE].sort(),
    ['Avec batterie', 'Les deux (Sans + Avec)', 'Sans batterie'])
})
