// Reproduction — e2e devis.spec.js E4 : "Devis auto impossible : aucun
// panneau du stock ne correspond à cette composition." (autoQuote.js F3,
// GitHub run 32200473257, PR #538).
//
// RACINE CONFIRMÉE en lisant la trace Playwright RÉELLE du run rouge
// (playwright-report-1, requête réseau `GET /api/django/stock/produits/`) :
//   { "count": 101, "next": ".../produits/?page=2", "results": [...50 items] }
// — page 1 s'arrête à « Onduleur réseau Huawei 5kW Monophasé » (ordre
// alphabétique, `ordering=['nom']` sur ProduitViewSet) ; LES DEUX « Panneau
// … » sont en page 2, jamais lus. `LeadDevisPanel.jsx` (et
// `DevisGenerator.jsx`, même bug) appelaient `stockApi.getProduits()` SANS
// paramètre — page 1 seulement (`StandardPagination.page_size = 50`) — alors
// que `features/stock/store/stockSlice.js` utilise déjà `fetchAllPages`
// (VX54) pour EXACTEMENT cette raison (« StockList/DevisList/FactureList/
// Dashboard étaient FAUX dès 101 enregistrements »). `getParametresGammes()`
// renvoyait `marques:{}` (aucun réglage) — la piste « marque épinglée »
// (suspect a) est éliminée par la même trace.
//
// Ce fichier rejoue le chemin résidentiel de `createAutoQuote` via les
// fonctions PURES de solar.js sur DEUX fixtures :
//   1. `autoQuote.e2eSeedRepro.realPage1.fixture.json` — les 50 PREMIERS
//      produits EXACTS renvoyés par ce run rouge (extraits de la réponse
//      réseau enregistrée dans le trace.zip) : reproduit le bug tel quel.
//   2. `autoQuote.e2eSeedRepro.fixture.json` — le catalogue COMPLET
//      reconstruit depuis seed_catalogue.py (94 lignes ; les 7 produits
//      génériques supplémentaires vus dans le run — « Batterie 5 kWh »,
//      « Onduleur hybride 5kW », etc. — sont des restes d'un ancien
//      seed/fixture mis en cache par le testdb WOW8, hors périmètre de ce
//      correctif) : prouve que le catalogue COMPLET compose bien.
//
// Run : node --test src/features/ventes/autoQuote.e2eSeedRepro.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  autoFillLines, optimalKwcByPayback, estimerKwcDepuisFacture, estimerMois,
  DAY_USAGE_DEFAULTS, KWH_PRICE, EFFICIENCY,
} from './solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const PRODUITS = JSON.parse(readFileSync(join(HERE, 'autoQuote.e2eSeedRepro.fixture.json'), 'utf8'))
const REAL_PAGE1 = JSON.parse(readFileSync(join(HERE, 'autoQuote.e2eSeedRepro.realPage1.fixture.json'), 'utf8'))

test('sanité fixture (reconstruite) : 94 produits, panneaux présents avec un prix (forme DRF, chaînes)', () => {
  assert.equal(PRODUITS.length, 94)
  const panneaux = PRODUITS.filter((p) => /panneau/i.test(p.nom))
  assert.equal(panneaux.length, 2)
  for (const p of panneaux) {
    assert.equal(typeof p.prix_vente, 'string')
    assert.ok(parseFloat(p.prix_vente) > 0)
  }
})

test('sanité fixture (trace réelle) : 50 produits, exactement ceux de la page 1 du run rouge, AUCUN panneau', () => {
  assert.equal(REAL_PAGE1.length, 50)
  assert.equal(REAL_PAGE1.filter((p) => /panneau/i.test(p.nom)).length, 0)
})

// Rejoue le chemin résidentiel de `createAutoQuote` (autoQuote.js, branche
// `else` non-agricole) pour `facture_hiver = 900`, aucune marque épinglée
// (comportement par défaut d'une société e2e sans réglage Paramètres →
// Gammes — voir `apps/ventes/services.get_parametres_gammes`, confirmé par
// la trace réelle : `{"marques":{}}`).
function simulerCheminResidentiel(produits, { hiver, marques }) {
  const besoinKwc = estimerKwcDepuisFacture(hiver)
  assert.ok(besoinKwc > 0, 'précondition : la facture doit produire un besoin kWc positif')
  const dayUsagePct = DAY_USAGE_DEFAULTS['Résidentielle']
  const opt = optimalKwcByPayback({
    produits, factures: estimerMois(hiver, hiver), dayUsagePct,
    panelW: 710, structureType: 'acier', discountPct: '0',
    kwhPrice: KWH_PRICE, efficiency: EFFICIENCY, besoinKwc, marques,
  })
  const panels = opt.nbPanneaux > 0 ? opt.nbPanneaux : 8
  const kwpAuto = panels * 710 / 1000
  const rows = autoFillLines(produits, {
    kwp: kwpAuto, panelW: 710, nbPanneaux: panels, structureType: 'acier', marques,
  })
  // MIROIR EXACT du garde autoQuote.js (F3) : un panneau attendu sans produit
  // apparié.
  const panneauxSansProduit = rows.some(
    (r) => !r.produit && /panneau/i.test(r.designation || '') && parseFloat(r.quantite) > 0)
  return { opt, rows, panneauxSansProduit, marquesManquantes: rows.marquesManquantes ?? [] }
}

test('REPRO — nourri de la page 1 SEULE (ancien bug, forme EXACTE du run rouge) : le panneau N\'EST PAS apparié', () => {
  const { panneauxSansProduit } = simulerCheminResidentiel(
    REAL_PAGE1, { hiver: 900, marques: undefined })
  assert.equal(panneauxSansProduit, true,
    'si ce test casse, la page 1 seule contient de nouveau un panneau — revérifier la fixture réelle')
})

test('REPRO — catalogue COMPLET (reconstruit depuis seed_catalogue.py, 94 lignes) : le panneau EST apparié', () => {
  const { panneauxSansProduit, marquesManquantes, rows } = simulerCheminResidentiel(
    PRODUITS, { hiver: 900, marques: undefined })
  assert.deepEqual(marquesManquantes, [])
  assert.equal(panneauxSansProduit, false,
    `panneauxSansProduit ne devrait PAS se déclencher — lignes: ${JSON.stringify(rows.find((r) => /panneau/i.test(r.designation || '')))}`)
})

test('REPRO — avec `marques={}` (get-or-create par défaut de ParametresGammes, confirmé par la trace) : toujours apparié', () => {
  const { panneauxSansProduit } = simulerCheminResidentiel(
    PRODUITS, { hiver: 900, marques: {} })
  assert.equal(panneauxSansProduit, false)
})

test('CONTRÔLE — retirer les DEUX panneaux du catalogue complet reproduit bien le symptôme observé', () => {
  // Confirme que le garde F3 déclenche exactement le message observé en CI
  // quand le catalogue n'a VRAIMENT aucun panneau — pour qu'on sache que les
  // tests ci-dessus testent la bonne chose (et ne passent pas pour une
  // raison accidentelle, ex. kwp trop petit pour générer une ligne panneau).
  const sansPanneaux = PRODUITS.filter((p) => !/panneau/i.test(p.nom))
  const { panneauxSansProduit } = simulerCheminResidentiel(
    sansPanneaux, { hiver: 900, marques: undefined })
  assert.equal(panneauxSansProduit, true)
})

// ── Le FIX : lire le catalogue ENTIER (toutes les pages), pas seulement la
//    première — miroir de la correction apportée à LeadDevisPanel.jsx /
//    DevisGenerator.jsx (`fetchAllPages`, VX54). ──────────────────────────
test('FIX — page 1 + page 2 (simulée en découpant le catalogue complet en pages de 50) : le panneau EST apparié', () => {
  // `fetchAllPages` ne fait rien de plus, une fois toutes les pages reçues,
  // que CONCATÉNER `results` — cette simulation est donc un miroir fidèle,
  // sans avoir besoin d'un serveur DRF réel pour ce test pur.
  const page1 = PRODUITS.slice(0, 50)
  const page2 = PRODUITS.slice(50)
  assert.ok(page2.length > 0, 'précondition : le catalogue complet doit dépasser 50 lignes')
  const toutesLesPages = [...page1, ...page2]
  assert.equal(toutesLesPages.length, PRODUITS.length)
  const { panneauxSansProduit } = simulerCheminResidentiel(
    toutesLesPages, { hiver: 900, marques: undefined })
  assert.equal(panneauxSansProduit, false)
})
