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
  PRODUCT_CATEGORIES,
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

// Incident fondateur 01/09 (round 2) — autoFillLines doit composer avec le
// nom RÉEL du catalogue prod (« Deye off-Grid 6kw », sans « onduleur »), pas
// seulement le nom de test historique (« Onduleur Off-Grid Deye … »).

// ADEV69 — second composeur supprimé (D-QJR5-9) : la composition vit au serveur (apps/ventes/domain/composition.py, testée côté backend).
// Tests retirés (ils ne protégeaient QUE `autoFillLines`) :
//   · offgrid : compose UNE option — onduleur hors réseau (≥ 80 % cible) + batterie + panneaux, jamais réseau/hybride
//   · offgrid : aucun onduleur hors réseau tarifé → erreur FRANÇAISE claire, jamais un repli hybride
//   · offgrid : autoFillLines choisit « Deye off-Grid 6kw » (nom produit réel, sans le mot « onduleur »)
//   · offgrid : aucune batterie tarifée/compatible → erreur FRANÇAISE claire, jamais une composition sans stockage
//   · offgrid : une batterie SANS PRIX ne peut jamais être composée (jamais une ligne à 0 MAD)
//   · offgrid : `offgrid` absent/faux reste BYTE-IDENTIQUE à l\
