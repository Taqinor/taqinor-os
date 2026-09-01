// OFFGRID (ajout produit onduleur hors réseau) — le fondateur a ajouté un
// produit onduleur HORS RÉSEAU (site isolé, jamais raccordé à l'ONEE) au
// catalogue ; l'écran n'avait NI classification NI panier NI auto-remplissage
// pour lui. Ce fichier verrouille le contrat PARTAGÉ avec le backend (mêmes
// mots-clés, jamais un seul divergent — voir apps/ventes/services.py côté
// serveur, lane sœur du même chantier) :
//   • OFFGRID_KEYWORDS : 'off-grid', 'off grid', 'offgrid', 'hors reseau',
//     'autonome' — un onduleur hors réseau AVANT tout, jamais confondu avec
//     l'onduleur RÉSEAU (bug : « onduleur hors réseau » contient le sous-mot
//     « réseau ») ni avec l'onduleur HYBRIDE (précédence : hybride d'abord) ;
//   • paniers : off-grid EXCLU du panier « sans » (comme batterie/hybride),
//     INCLUS dans « avec » (comme hybride) — les panneaux restent dans les
//     DEUX (invariant jamais touché) ;
//   • auto-remplissage : compose UNE SEULE option (panneaux + onduleur hors
//     réseau + batterie, même sélection/mêmes quantités que la branche
//     « avec » historique) ; jamais un produit sans prix ; erreur FRANÇAISE
//     claire (jamais un repli silencieux sur l'hybride) quand aucun onduleur
//     hors réseau ou aucune batterie n'est tarifé(e) au catalogue.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  isOffgridInverter, isReseauInverter, isHybridInverter, classifyProduct,
  appartientAuPanierSans, appartientAuPanierAvec,
  autoFillLines, PRODUCT_CATEGORIES,
} from './solar.js'

// Même convention que solar.test.mjs / solar.marques.test.mjs : prix HT =
// TTC simulateur / 1.2, `quantite_stock` par défaut 500 (BATHOMO/F4 — le
// stock-gating batterie n'exclut QUE ce qu'un test met explicitement à 0).
const ht = (ttc) => (ttc / 1.2).toFixed(2)
let _id = 0
const P = (nom, ttc, qty = 500) => ({ id: ++_id, nom, prix_vente: ht(ttc), quantite_stock: qty })

// ── Classification (mots-clés partagés avec le backend) ─────────────────────
test('isOffgridInverter : off-grid/off grid/offgrid/hors réseau/autonome, jamais hybride', () => {
  assert.equal(isOffgridInverter('Onduleur Off-Grid Deye 5kW Monophasé'), true)
  assert.equal(isOffgridInverter('Onduleur off grid Deye 5kW'), true)
  assert.equal(isOffgridInverter('Onduleur offgrid Deye 5kW'), true)
  assert.equal(isOffgridInverter('Onduleur hors réseau 5kW'), true)
  assert.equal(isOffgridInverter('Onduleur hors reseau 5kW'), true) // sans accent
  assert.equal(isOffgridInverter('Onduleur Autonome 5kW'), true)
  // Précédence hybride : un onduleur hybride+hors réseau reste HYBRIDE, jamais
  // classé off-grid par ce prédicat (même ordre que classifyProduct ci-dessous).
  assert.equal(isOffgridInverter('Onduleur Hybride Off-Grid 5kW'), false)
  assert.equal(isHybridInverter('Onduleur Hybride Off-Grid 5kW'), true)
  // Ni panneau ni batterie ni onduleur réseau ordinaire.
  assert.equal(isOffgridInverter('Onduleur réseau Huawei 5kW'), false)
  assert.equal(isOffgridInverter('Panneau Off-Grid 550W'), false) // pas "onduleur"
  assert.equal(isOffgridInverter(''), false)
  assert.equal(isOffgridInverter(undefined), false)
})

// Incident fondateur 01/09 (round 2) — les VRAIS produits catalogue ne disent
// JAMAIS « onduleur » (ex. « Deye off-Grid 6kw ») : le prédicat élargi les
// reconnaît quand même, mais SEULEMENT si aucun mot-clé d'une autre famille
// (batterie/panneau/module/pompe/variateur/structure/câble/coffret/
// disjoncteur/différentiel/parafoudre/compteur/smart meter/wifi/kit/
// chargeur) n'apparaît dans le nom — sinon ce n'est manifestement pas
// l'onduleur lui-même.
test('isOffgridInverter élargi : noms produit RÉELS sans le mot « onduleur »', () => {
  assert.equal(isOffgridInverter('Deye off-Grid 6kw'), true)
  assert.equal(isOffgridInverter('Deye Off-Grid 6kW'), true)
  assert.equal(isOffgridInverter('Deye Autonome 5kW'), true)
  // Autre famille explicite dans le nom : JAMAIS retenu comme onduleur, même
  // avec un mot-clé off-grid.
  assert.equal(isOffgridInverter('Batterie off-grid'), false)
  assert.equal(isOffgridInverter('Kit solaire off-grid'), false)
  assert.equal(isOffgridInverter('Cable off-grid'), false)
  assert.equal(isOffgridInverter('Coffret off-grid'), false)
  assert.equal(isOffgridInverter('Variateur off-grid'), false)
  // Le mot « onduleur » prime TOUJOURS : présent, le nom est retenu même s'il
  // porte aussi un mot d'une autre famille (comportement historique intact).
  assert.equal(isOffgridInverter('Onduleur Off-Grid Deye 5kW Monophasé'), true)
  // Précédence hybride inchangée sur le nom réel (sans « onduleur »).
  assert.equal(isOffgridInverter('Deye Hybride Off-Grid 6kw'), false)
  assert.equal(classifyProduct('Deye off-Grid 6kw'), 'onduleur_offgrid')
  assert.equal(classifyProduct('Batterie off-grid'), 'batterie')
})

test('BUG CORRIGÉ — isReseauInverter n\'attrape plus « onduleur hors réseau »', () => {
  // « onduleur hors réseau » contient le sous-mot « réseau » : avant le
  // correctif, isReseauInverter(false positif) classait cette ligne au panier
  // « sans », jamais composée par l'auto-remplissage.
  assert.equal(isReseauInverter('Onduleur hors réseau 5kW'), false)
  assert.equal(isReseauInverter('Onduleur hors reseau 5kW'), false)
  assert.equal(isReseauInverter('Onduleur Off-Grid 5kW'), false)
  assert.equal(isReseauInverter('Onduleur Autonome 5kW'), false)
  // Comportement historique INCHANGÉ pour les vrais onduleurs réseau/injection.
  assert.equal(isReseauInverter('Onduleur réseau Huawei 10kW Triphasé'), true)
  assert.equal(isReseauInverter('Onduleur injection Huawei 10kW'), true)
  assert.equal(isReseauInverter('Onduleur hybride Deye 10kW'), false)
})

test('classifyProduct : hybride d\'abord, puis hors réseau, puis réseau — jamais un ordre divergent', () => {
  assert.equal(classifyProduct('Onduleur Hybride Deye 10kW'), 'onduleur_hybride')
  // Précédence hybride EXPLICITE : un nom hybride+hors réseau reste hybride.
  assert.equal(classifyProduct('Onduleur Hybride Off-Grid Deye 10kW'), 'onduleur_hybride')
  assert.equal(classifyProduct('Onduleur Off-Grid Deye 5kW Monophasé'), 'onduleur_offgrid')
  // Le bug historique : sans le détournement AVANT le test réseau/injection,
  // ceci retombait sur 'onduleur_reseau'.
  assert.equal(classifyProduct('Onduleur hors réseau Deye 5kW'), 'onduleur_offgrid')
  assert.equal(classifyProduct('Onduleur réseau Huawei 10kW Triphasé'), 'onduleur_reseau')
  assert.equal(classifyProduct('Panneau Canadien Solar 710W'), 'panneau')
  assert.equal(classifyProduct('Batterie Dyness 5 kWh'), 'batterie')
})

test('PRODUCT_CATEGORIES porte le rôle onduleur_offgrid, à côté des deux autres familles', () => {
  const keys = PRODUCT_CATEGORIES.map(([k]) => k)
  assert.ok(keys.includes('onduleur_offgrid'))
  assert.ok(keys.includes('onduleur_reseau'))
  assert.ok(keys.includes('onduleur_hybride'))
  const entry = PRODUCT_CATEGORIES.find(([k]) => k === 'onduleur_offgrid')
  assert.equal(entry[1], 'Onduleurs hors réseau')
})

// ── Paniers sans/avec ────────────────────────────────────────────────────────
test('panier « sans batterie » : EXCLUT l\'onduleur hors réseau, comme batterie/hybride', () => {
  assert.equal(appartientAuPanierSans({ designation: 'Onduleur Off-Grid Deye 5kW' }), false)
  assert.equal(appartientAuPanierSans({ designation: 'Batterie Dyness 5 kWh' }), false)
  assert.equal(appartientAuPanierSans({ designation: 'Onduleur hybride Deye 5kW' }), false)
  // Comportement historique inchangé : l'onduleur réseau reste dans « sans ».
  assert.equal(appartientAuPanierSans({ designation: 'Onduleur réseau Huawei 10kW' }), true)
})

test('panier « avec batterie » : INCLUT l\'onduleur hors réseau, comme hybride', () => {
  assert.equal(appartientAuPanierAvec({ designation: 'Onduleur Off-Grid Deye 5kW' }), true)
  assert.equal(appartientAuPanierAvec({ designation: 'Onduleur hybride Deye 5kW' }), true)
  assert.equal(appartientAuPanierAvec({ designation: 'Batterie Dyness 5 kWh' }), true)
  // Comportement historique inchangé : l'onduleur réseau reste EXCLU d'« avec ».
  assert.equal(appartientAuPanierAvec({ designation: 'Onduleur réseau Huawei 10kW' }), false)
})

test('invariant jamais touché : les panneaux restent dans LES DEUX paniers', () => {
  const panneau = { designation: 'Panneau Canadien Solar 710W' }
  assert.equal(appartientAuPanierSans(panneau), true)
  assert.equal(appartientAuPanierAvec(panneau), true)
})

test('une ligne DÉCLARÉE (variante) tranche seule, même pour l\'onduleur hors réseau', () => {
  const l = { designation: 'Onduleur Off-Grid Deye 5kW', variante: 'sans' }
  // F14 — la déclaration prime toujours sur les mots-clés (miroir builder.py).
  assert.equal(appartientAuPanierSans(l), true)
  assert.equal(appartientAuPanierAvec({ ...l, variante: 'sans' }), false)
})

// ── Auto-remplissage hors réseau (`autoFillLines(..., { offgrid: true })`) ──
// kwp = 14 panneaux × 710 W = 9,94 kWc → seuil onduleur = 7,952 kW ; cible
// batterie = round(9,94/5)×5 = 10 kWh (même dérivation que solar.test.mjs).
const KWP_14 = 14 * 710 / 1000

const OFFGRID_CATALOGUE = [
  P('Onduleur Off-Grid Deye 5kW Monophasé', 17000),
  P('Onduleur Off-Grid Deye 10kW Monophasé', 26000),
  P('Onduleur Off-Grid Deye 10kW Triphasé', 27000),
  P('Panneau Canadien Solar 710W', 1400),
  P('Batterie Dyness 5 kWh', 17000),
  P('Batterie Dyness 10 kWh', 30000),
  P('Structures acier', 500),
  P('Socles', 80),
  P('Smart Meter', 1800),
  P('Wifi Dongle', 1200),
  P('Accessoires', 2000),
  P('Tableau De Protection AC/DC', 2000),
  P('Installation', 4800),
  P('Transport', 1000),
  P('Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 5000),
]

test('offgrid : compose UNE option — onduleur hors réseau (≥ 80 % cible) + batterie + panneaux, jamais réseau/hybride', () => {
  const rows = autoFillLines(OFFGRID_CATALOGUE, {
    kwp: KWP_14, panelW: 710, structureType: 'acier', offgrid: true,
  })
  assert.ok(rows.length > 0)
  // Plus petit modèle ≥ 7,952 kW : 10 kW Mono et 10 kW Triphasé sont à égalité
  // de puissance → Triphasé préféré (règle historique, bestPower >= 10).
  const inv = rows.find(r => r.designation.includes('Off-Grid'))
  assert.equal(inv.designation, 'Onduleur Off-Grid Deye 10kW Triphasé')
  assert.equal(inv.quantite, 1)
  assert.equal(inv.prix_unit_ttc, 27000)
  // JAMAIS de ligne onduleur réseau ni hybride sur une composition hors réseau.
  assert.equal(rows.find(r => r.designation === 'Onduleur réseau'), undefined)
  assert.equal(rows.find(r => r.designation.includes('réseau Huawei')), undefined)
  assert.equal(rows.find(r => r.designation.toLowerCase().includes('hybride')), undefined)
  // Panneaux : identique à la composition historique.
  const pan = rows.find(r => r.designation.includes('Panneau'))
  assert.equal(pan.designation, 'Panneau Canadien Solar 710W')
  assert.equal(pan.quantite, 14)
  // Batterie : cible 10 kWh → 1 × Dyness 10 kWh (moins cher que 2 × 5 kWh),
  // MÊME logique BATHOMO que la branche hybride historique.
  assert.equal(rows.find(r => r.designation.includes('Dyness 10')).quantite, 1)
  assert.equal(rows.find(r => r.designation.includes('Dyness 5')).quantite, 0)
})

test('offgrid : aucun onduleur hors réseau tarifé → erreur FRANÇAISE claire, jamais un repli hybride', () => {
  const catalogue = [
    P('Onduleur Off-Grid Deye 10kW Triphasé', 0), // prix 0 = jamais choisi
    P('Onduleur hybride Deye 10kW Triphasé', 28000), // présent mais JAMAIS utilisé
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 10 kWh', 30000),
  ]
  const rows = autoFillLines(catalogue, {
    kwp: KWP_14, panelW: 710, structureType: 'acier', offgrid: true,
  })
  assert.equal(rows.length, 0)
  // Incident fondateur 01/09 round 2 — le motif seul ne disait pas au vendeur
  // POURQUOI un produit qu'il voit au catalogue (prix 0 ici) n'est pas trouvé :
  // le message rappelle désormais le contrat de nommage ET l'exigence de prix.
  assert.equal(rows.offgridErreur,
    'Aucun onduleur hors réseau avec prix au catalogue. '
    + 'Le NOM du produit doit contenir « off-grid », « off grid », '
    + '« hors réseau » ou « autonome » (ex. « Deye Off-Grid 6kW »), '
    + 'avec un prix de vente.')
  // Preuve « jamais un repli silencieux sur l'hybride » : le tableau est VIDE,
  // pas une seule ligne hybride composée à la place.
})

// Incident fondateur 01/09 (round 2) — autoFillLines doit composer avec le
// nom RÉEL du catalogue prod (« Deye off-Grid 6kw », sans « onduleur »), pas
// seulement le nom de test historique (« Onduleur Off-Grid Deye … »).
test('offgrid : autoFillLines choisit « Deye off-Grid 6kw » (nom produit réel, sans le mot « onduleur »)', () => {
  const catalogueReel = [
    P('Deye off-Grid 6kw', 18000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 5 kWh', 17000),
    P('Batterie Dyness 10 kWh', 30000),
  ]
  const rows = autoFillLines(catalogueReel, {
    kwp: KWP_14, panelW: 710, structureType: 'acier', offgrid: true,
  })
  assert.ok(rows.length > 0)
  const inv = rows.find(r => r.designation === 'Deye off-Grid 6kw')
  assert.ok(inv, 'la ligne « Deye off-Grid 6kw » doit être composée')
  // Seuil 7,952 kW, aucun modèle ≥ 6 kW seul disponible → 2 unités (comme le
  // repli historique quand le plus gros modèle du catalogue est trop petit).
  assert.equal(inv.quantite, 2)
  assert.equal(inv.prix_unit_ttc, 18000)
  assert.equal(rows.find(r => r.designation.toLowerCase().includes('hybride')), undefined)
})

test('offgrid : aucune batterie tarifée/compatible → erreur FRANÇAISE claire, jamais une composition sans stockage', () => {
  const catalogue = [
    P('Onduleur Off-Grid Deye 10kW Triphasé', 27000),
    P('Panneau Canadien Solar 710W', 1400),
    // Aucune batterie du tout au catalogue.
  ]
  const rows = autoFillLines(catalogue, {
    kwp: KWP_14, panelW: 710, structureType: 'acier', offgrid: true,
  })
  assert.equal(rows.length, 0)
  assert.equal(rows.offgridErreur,
    'Aucune batterie compatible tarifée au catalogue pour cet onduleur hors réseau.')
})

test('offgrid : une batterie SANS PRIX ne peut jamais être composée (jamais une ligne à 0 MAD)', () => {
  const catalogue = [
    P('Onduleur Off-Grid Deye 10kW Triphasé', 27000),
    P('Panneau Canadien Solar 710W', 1400),
    P('Batterie Dyness 10 kWh', 0), // en stock, mais prix à renseigner
  ]
  const rows = autoFillLines(catalogue, {
    kwp: KWP_14, panelW: 710, structureType: 'acier', offgrid: true,
  })
  assert.equal(rows.length, 0)
  assert.equal(rows.offgridErreur,
    'Aucune batterie compatible tarifée au catalogue pour cet onduleur hors réseau.')
})

test('offgrid : `offgrid` absent/faux reste BYTE-IDENTIQUE à l\'historique (réseau + hybride)', () => {
  const catalogueMixte = [
    ...OFFGRID_CATALOGUE,
    P('Onduleur réseau Huawei 10kW Triphasé', 20000),
    P('Onduleur hybride Deye 10kW Triphasé', 28000),
  ]
  const opts = { kwp: KWP_14, panelW: 710, structureType: 'acier' }
  const sansOption = autoFillLines(catalogueMixte, opts)
  const offgridFaux = autoFillLines(catalogueMixte, { ...opts, offgrid: false })
  const offgridUndefined = autoFillLines(catalogueMixte, { ...opts, offgrid: undefined })
  assert.deepEqual(offgridFaux, sansOption)
  assert.deepEqual(offgridUndefined, sansOption)
  // Le comportement historique compose réseau + hybride, JAMAIS l'off-grid,
  // même si le catalogue en porte un tarifé.
  assert.ok(sansOption.some(r => r.designation.includes('réseau')))
  assert.ok(sansOption.some(r => r.designation.includes('hybride')))
  assert.equal(sansOption.some(r => r.designation.includes('Off-Grid')), false)
})
