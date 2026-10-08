#!/usr/bin/env node
// SPL190 — GOLDEN des calculs écran de `solar.js` que les corpus figés ne
// couvrent pas, capturé sur le code ACTUEL, AVANT tout déplacement (SPL195,
// SPL197-SPL202, SPL207 découpent solar.js par déplacements purs).
//
// Les deux corpus figés (solar_corpus*.json, solar_calculs_corpus*.json)
// épinglent classification, parseWatt, productible, optionTotalsTTC, tarifs et
// computeROI. RIEN n'épinglait octet pour octet : autoFillLines (et l'ordre des
// lignes), defaultProductLines, structureRoleForName, structureChoisie,
// orderLinesByRolePreference, deriveRoleOrderFromLines, la recomposition
// (appliquerRecomposition / fusionnerRecomposition / fusionnerVariantes /
// lignesManuellesEnConflitPossible), multiPropertyPreviewTTC,
// avecBatterieAvailability, computeBuyCost, prixParKwc, discountForTarget.
// (optimalKwcByPayback, autoFillPompage et pompageSelection n'existent plus
// dans solar.js — retirés avec le moteur pompage JS, AGR132, et le
// dimensionnement serveur U3 — ils ne sont donc pas capturés.)
//
// GÉNÉRATION. Grilles explicites + PRNG seedé (mulberry32, comme
// solar_calculs_corpus.mjs) : mêmes cas à chaque exécution. Catalogue = les
// DEUX fixtures déjà commises (autoQuote.e2eSeedRepro.fixture.json, 94
// produits ; autoQuote.e2eSeedRepro.realPage1.fixture.json, 50 produits) —
// aucun prix inventé. Les LIGNES d'entrée des fonctions aval (recomposition,
// totaux multi-propriétés, disponibilité batterie, coût d'achat) sont écrites
// EN DONNÉES dans le JSON (jamais recalculées au moment du test) : un
// déplacement fautif d'autoFillLines ne peut pas se masquer en changeant aussi
// l'entrée des fonctions aval.
//
// RÉGÉNÉRATION (PACT10). Ce fichier est produit UNE fois, sur le code actuel,
// par `node frontend/scripts/calculs_golden.mjs`. Il n'est JAMAIS régénéré pour
// faire passer un déplacement : un golden rouge est un bug du déplacement.
import { writeFileSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import process from 'node:process'

const HERE = dirname(fileURLToPath(import.meta.url))
const VENTES = join(HERE, '..', 'src', 'features', 'ventes')
export const EXPECTED_PATH = join(VENTES, 'golden', 'calculs_ecran_expected.json')

/** Les deux catalogues commis, par nom (les entrées ne recopient que le nom). */
export function chargerCatalogues() {
  const lire = (f) => JSON.parse(readFileSync(join(VENTES, f), 'utf8'))
  return {
    seed94: lire('autoQuote.e2eSeedRepro.fixture.json'),
    realPage1: lire('autoQuote.e2eSeedRepro.realPage1.fixture.json'),
  }
}

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
// Graine FIGÉE — ne jamais la changer.
export const SEED = 0x5B190

/**
 * Forme JSON EXACTE d'une valeur : les propriétés nommées d'un tableau
 * (`lignes.nbPanneaux`, `lignes.marquesManquantes`…) et les nombres non finis
 * (NaN, ±Infinity) survivent à l'aller-retour ; `undefined` est explicite.
 */
export function figer(v) {
  if (v === undefined) return { __undefined: true }
  if (typeof v === 'number' && !Number.isFinite(v)) return { __nombre: String(v) }
  if (Array.isArray(v)) {
    const extra = Object.keys(v).filter((k) => !/^\d+$/.test(k))
    const elements = v.map(figer)
    if (!extra.length) return elements
    const out = { __tableau: elements }
    for (const k of extra.sort()) out[k] = figer(v[k])
    return out
  }
  if (v && typeof v === 'object') {
    const out = {}
    for (const k of Object.keys(v)) out[k] = figer(v[k])
    return out
  }
  return v
}

/**
 * CE QUE solar.js CALCULE sur une entrée — LE contrat. `f` = les fonctions de
 * solar.js passées par l'appelant (le test les importe symbole par symbole :
 * chaque déplacement ne change que SA ligne d'import), `cat` = les catalogues.
 */
export function calculer(e, f, cat) {
  const x = e.entree
  switch (e.axe) {
    case 'defaultProductLines':
      return figer(f.defaultProductLines(cat[x.catalogue], x.ordreLignes))
    case 'structureRoleForName':
      return figer(x.voulu === undefined
        ? f.structureRoleForName(x.nom) : f.structureRoleForName(x.nom, x.voulu))
    case 'structureChoisie': {
      const p = f.structureChoisie(cat[x.catalogue], x.structureProduitId)
      return figer(p ? { id: p.id, nom: p.nom } : null)
    }
    case 'orderLinesByRolePreference':
      return figer(f.orderLinesByRolePreference(x.tagged, x.ordreLignes))
    case 'deriveRoleOrderFromLines':
      return figer(f.deriveRoleOrderFromLines(x.lignes))
    case 'appliquerRecomposition':
      return figer(f.appliquerRecomposition(x.anciennes, x.generees, x.mode))
    case 'fusionnerRecomposition':
      return figer(f.fusionnerRecomposition(x.anciennes, x.generees))
    case 'fusionnerVariantes':
      return figer(f.fusionnerVariantes(x.sans, x.avec))
    case 'lignesManuellesEnConflitPossible':
      return figer(f.lignesManuellesEnConflitPossible(x.lignes))
    case 'multiPropertyPreviewTTC':
      return figer(f.multiPropertyPreviewTTC(x.lignes, x.options))
    case 'avecBatterieAvailability':
      return figer(f.avecBatterieAvailability(x.lignes, cat[x.catalogue], x.kwp))
    case 'computeBuyCost':
      return figer(f.computeBuyCost(x.lignes, cat[x.catalogue]))
    case 'prixParKwc':
      return figer(f.prixParKwc(x.totalTtc, x.kwp))
    case 'discountForTarget':
      return figer(f.discountForTarget(x.cibleKwc, x.kwp, x.totalBrutTtc))
    default:
      throw new Error(`axe inconnu : ${e.axe}`)
  }
}

// ── Génération des entrées ───────────────────────────────────────────────────
const ROLES = ['onduleur_reseau', 'onduleur_hybride', 'smart_meter', 'wifi_dongle',
  'panneau', 'batterie', 'structure_acier', 'structure_alu', 'socle', 'accessoires',
  'tableau', 'installation', 'transport', 'suivi']

const plain = (lignes) => JSON.parse(JSON.stringify([...lignes]))

export function genEntrees(f, cat) {
  const rand = mulberry32(SEED)
  const pick = (arr) => arr[Math.floor(rand() * arr.length)]
  const entries = []
  let n = 0
  const push = (axe, entree) => {
    entries.push({ id: `CALC-${String(n++).padStart(4, '0')}`, axe, entree })
  }

  // autoFillLines — grille complète (catalogue × kwp × panelW × structure ×
  // hors réseau × paires MPPT), puis des combinaisons tirées des options rares.
  for (const catalogue of ['seed94', 'realPage1']) {
    for (const kwp of [3, 5, 10, 30]) {
      for (const panelW of [550, 710]) {
        for (const structureType of ['acier', 'aluminium']) {
          for (const offgrid of [false, true]) {
            for (const mpptPaires of [1, 2]) {
              push('autoFillLines', { catalogue, options: { kwp, panelW, structureType, offgrid, mpptPaires } })
            }
          }
        }
      }
    }
  }
  const MARQUES = [
    undefined,
    { panneau: 'Jinko', onduleur_reseau: 'Huawei' },
    { panneau: 'Canadien Solar', onduleur_hybride: 'Deye', batterie: 'Dyness' },
    { structure_acier: 'MarqueInexistante', structure_alu: 'MarqueInexistante' },
  ]
  const ORDRES = [undefined, [], [...ROLES].reverse(), ['panneau', 'batterie', 'transport']]
  const STRUCTURES = [undefined, 22, '23', 9999, '']
  for (let i = 0; i < 48; i++) {
    push('autoFillLines', {
      catalogue: pick(['seed94', 'realPage1']),
      options: {
        kwp: pick([0, -1, 2.84, 4.26, 7.1, 14.2, 50, 120]),
        panelW: pick([550, 710]),
        structureType: pick(['acier', 'aluminium']),
        nbPanneaux: pick([undefined, undefined, 6, 20]),
        marques: pick(MARQUES),
        ordreLignes: pick(ORDRES),
        mpptPaires: pick([undefined, 1, 2, 3]),
        offgrid: pick([false, false, true]),
        structureProduitId: pick(STRUCTURES),
      },
    })
  }

  // defaultProductLines — catalogues × ordres.
  for (const catalogue of ['seed94', 'realPage1']) {
    for (const ordreLignes of ORDRES) push('defaultProductLines', { catalogue, ordreLignes })
  }

  // structureRoleForName — noms × préférence.
  const NOMS = ['Structures acier', 'Structures aluminium', 'Structure alu/acier mixte',
    'Pergola bois', 'Carport', '', null, 'STRUCTURE ACIER GALVA', 'Bac lesté']
  for (const nom of NOMS) {
    for (const voulu of [undefined, 'acier', 'alu', 'aluminium']) push('structureRoleForName', { nom, voulu })
  }

  // structureChoisie — catalogues × ids (présent, texte, absent, vide, null).
  for (const catalogue of ['seed94', 'realPage1']) {
    for (const structureProduitId of [null, '', 22, '23', 12, '59', 9999]) {
      push('structureChoisie', { catalogue, structureProduitId })
    }
  }

  // orderLinesByRolePreference — lignes étiquetées synthétiques × ordres.
  const tagged = ROLES.map((r, i) => [r, { designation: `Ligne ${r}`, quantite: String(i) }])
  tagged.push(['panneau', { designation: 'Ligne panneau bis', quantite: '9' }])
  tagged.push(['inconnu', { designation: 'Ligne hors rôle', quantite: '1' }])
  for (const ordreLignes of [...ORDRES, ['inconnu', 'panneau']]) {
    push('orderLinesByRolePreference', { tagged, ordreLignes })
  }

  // Lignes de référence (DONNÉES figées dans le JSON). ADEV69 — elles étaient
  // tirées d'`autoFillLines` (supprimé : un seul composeur, côté serveur) :
  // elles sont désormais RELUES du golden commis (les quatre premières entrées
  // `deriveRoleOrderFromLines`, mêmes octets), jamais recalculées.
  const precedent = JSON.parse(readFileSync(EXPECTED_PATH, 'utf8'))
  const LIGNES = precedent.entries
    .filter((e) => e.axe === 'deriveRoleOrderFromLines').slice(0, 4).map((e) => e.entree.lignes)
  const [L5, L10, L7off, L30r] = LIGNES

  for (const lignes of LIGNES) push('deriveRoleOrderFromLines', { lignes })
  push('deriveRoleOrderFromLines', { lignes: [] })
  push('deriveRoleOrderFromLines', { lignes: [{ designation: 'Structures aluminium' }, { designation: 'Texte libre' }] })

  // Recomposition : anciennes lignes « travaillées » (drapeaux tirés) + générées.
  const travailler = (lignes) => {
    const out = []
    for (const l of lignes) {
      const c = { ...l }
      const r = rand()
      if (r < 0.15) c.prixManuel = true
      else if (r < 0.3) { c.quantiteManuelle = true; c.quantite = String((parseFloat(c.quantite) || 0) + 1) }
      else if (r < 0.4) c.optionnelle = true
      else if (r < 0.6) c.compose = true
      out.push(c)
      if (rand() < 0.1) out.push({ designation: 'Section golden', typeLigne: 'section', quantite: '0', prix_unit_ttc: '0' })
    }
    if (rand() < 0.5) out.push({ produit: '', designation: 'Ligne libre', quantite: '1', prix_unit_ttc: '150' })
    return out
  }
  for (let i = 0; i < 12; i++) {
    const anciennes = travailler(pick(LIGNES))
    const generees = pick(LIGNES)
    for (const mode of ['garder', 'recalcule']) push('appliquerRecomposition', { anciennes, generees, mode })
    push('fusionnerRecomposition', { anciennes, generees })
    push('lignesManuellesEnConflitPossible', { lignes: anciennes })
  }
  push('fusionnerRecomposition', { anciennes: [], generees: L5 })
  push('fusionnerRecomposition', { anciennes: L5, generees: [] })

  // fusionnerVariantes — paires de compositions (sans, avec).
  for (const [sans, avec] of [[L5, L10], [L10, L7off], [L5, L5], [L30r, L7off], [[], L5], [L5, []]]) {
    push('fusionnerVariantes', { sans, avec })
  }

  // multiPropertyPreviewTTC — × N identiques, puis villas (groupes).
  for (const lignes of LIGNES) {
    for (const nombreProprietes of [undefined, 1, 2, 5, '3']) {
      for (const discountPct of [0, 5, '7.5']) {
        push('multiPropertyPreviewTTC', { lignes, options: { nombreProprietes, discountPct } })
      }
    }
    const groupees = lignes.map((l, i) => ({ ...l, groupeIndex: i % 3, groupeLabel: i % 3 ? `Villa ${i % 3}` : '' }))
    push('multiPropertyPreviewTTC', { lignes: groupees, options: {} })
    push('multiPropertyPreviewTTC', { lignes: groupees, options: { discountPct: 10 } })
  }

  // avecBatterieAvailability — lignes × catalogue × puissance (au-delà de
  // MAX_HYBRID_UNITS onduleurs hybrides en parallèle comprise).
  for (const lignes of [...LIGNES, []]) {
    for (const catalogue of ['seed94', 'realPage1']) {
      for (const kwp of [3, 30, 100, 200]) push('avecBatterieAvailability', { lignes, catalogue, kwp })
    }
  }

  // computeBuyCost — lignes × catalogue.
  for (const lignes of [...LIGNES, []]) {
    for (const catalogue of ['seed94', 'realPage1']) push('computeBuyCost', { lignes, catalogue })
  }

  // prixParKwc / discountForTarget — bornes et valeurs courantes.
  for (const totalTtc of [0, -10, 1, 42000, 98765.43]) {
    for (const kwp of [0, -1, 0.71, 5.68, 30]) push('prixParKwc', { totalTtc, kwp })
  }
  for (const cibleKwc of [0, '', '7500', 9000, 'abc']) {
    for (const kwp of [0, 5.68, 30]) {
      for (const totalBrutTtc of [0, 42000, 300000]) push('discountForTarget', { cibleKwc, kwp, totalBrutTtc })
    }
  }

  return entries
}

async function main() {
  const solar = await import('../src/features/ventes/solar.js')
  const cat = chargerCatalogues()
  // Aller-retour JSON AVANT le calcul : l'attendu est calculé sur l'entrée
  // exactement telle que le test la relira.
  // ADEV69 — l'axe `autoFillLines` n'est plus calculé (fonction supprimée) ;
  // ses tirages restent dans la séquence (mêmes ids, même graine pour la suite).
  const entries = genEntrees(solar, cat).filter((e) => e.axe !== 'autoFillLines').map((e) => {
    const relue = JSON.parse(JSON.stringify(e))
    return { ...relue, attendu: calculer(relue, solar, cat) }
  })
  const entete = {
    pact: 'PACT10',
    tache: 'SPL190',
    genere_par: 'frontend/scripts/calculs_golden.mjs',
    regeneration: 'JAMAIS pour faire passer un déplacement : un golden rouge est un bug du déplacement.',
    seed: SEED,
    count: entries.length,
  }
  writeFileSync(EXPECTED_PATH, `${JSON.stringify({ ...entete, entries }, null, 1)}\n`)
  console.log(`calculs_golden: ${entries.length} entrées écrites dans ${EXPECTED_PATH}`)
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]
if (isMain) main()
