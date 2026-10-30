// SPL200 — Recomposition et fusion des lignes de l'écran devis
// (appliquerRecomposition, fusionnerRecomposition, fusionnerVariantes).
// DÉPLACEMENT PUR depuis features/ventes/solar.js (aucune logique changée).

import { isBattery, isHybridInverter, isOffgridInverter, isReseauInverter } from '../solar.js'

// ── L-2OPT — deux optimiseurs indépendants (fondateur 24/08) ─────────────────
// Un devis résidentiel « Les deux (Sans + Avec) » ne dimensionne plus les
// deux options sur le MÊME kWc : `autoFillLines` est appelé une fois par
// optimum (sans-batterie / avec-batterie, chacun son propre kWc — le moteur
// horaire serveur, `recommandation_avec`) et les deux
// compositions résultantes sont FUSIONNÉES ici, ligne par ligne (les deux
// tableaux partagent le même ordre de rôles canonique — `ordreLignes`/
// `marques` identiques des deux côtés — donc un appariement POSITIONNEL est
// fiable) :
//   • ligne identique (produit, désignation, prix unitaire TTC, taux TVA,
//     quantité) → UNE ligne commune, `variante: ''` ;
//   • ligne de RÔLE (correctif orchestrateur 25/08, aligné sur le backend
//     `services.fusionner_kits`) : batterie et onduleur hybride appartiennent
//     au panier AVEC, l'onduleur réseau au panier SANS — en cas de
//     divergence, seul le panier PROPRIÉTAIRE fait foi (UNE ligne, sa
//     variante), jamais deux exemplaires. Sans cela, une batterie taguée
//     'sans' (résidu de la composition superset) serait rangée — ET FACTURÉE
//     — côté « Sans batterie » par le PDF/l'aval, dont la règle est « la
//     déclaration prime sur les mots-clés » ;
//   • quantité (ou produit) divergente sur une ligne ordinaire → DEUX lignes,
//     `variante: 'sans'` / `'avec'`, chacune portant SA composition ;
//   • présente d'un seul côté (défensif) → la variante de son RÔLE d'abord,
//     celle de son côté sinon.
// Repli de sécurité : deux compositions IDENTIQUES (même kWc des deux côtés,
// le cas le plus courant) fusionnent en lignes 100 % `variante: ''` —
// résultat BYTE-IDENTIQUE à l'ancienne composition unique, aucune ligne
// variantée. Fonction PURE, testable indépendamment de l'écran.
function _memeLigne(a, b) {
  if (!a || !b) return false
  return String(a.produit ?? '') === String(b.produit ?? '')
    && String(a.designation ?? '') === String(b.designation ?? '')
    && (parseFloat(a.prix_unit_ttc) || 0) === (parseFloat(b.prix_unit_ttc) || 0)
    && (parseFloat(a.taux_tva) || 0) === (parseFloat(b.taux_tva) || 0)
    && (parseFloat(a.quantite) || 0) === (parseFloat(b.quantite) || 0)
}

// Rôle d'appartenance d'une ligne : 'avec' (batterie/onduleur hybride —
// panier avec batterie), 'sans' (onduleur réseau), '' (ligne ordinaire).
// Mêmes mots-clés que le split historique (`optionTotalsTTC`/builder.py).
function _roleVariante(l) {
  if (!l) return null
  const d = l.designation
  if (isBattery(d) || isHybridInverter(d) || isOffgridInverter(d)) return 'avec'
  if (isReseauInverter(d)) return 'sans'
  return ''
}

// ── QJR570 (D-QJR5-4) — RECOMPOSER FUSIONNE, ne remplace plus ───────────────
// Auto-remplir, « Appliquer cette taille » et « Recalculer » remplaçaient les
// lignes d'un bloc : un prix tapé, une section, une note, une option ou un
// produit ajouté à la main disparaissaient. `fusionnerRecomposition` apparie
// les anciennes lignes aux lignes générées PAR ID PRODUIT et :
//   • reporte prix_unit_ttc + prixManuel quand le prix avait été tapé ;
//   • prend la `variante` de la ligne générée (le découpage d'options est
//     celui de la nouvelle composition) ;
//   • réinsère à leur position relative les anciennes lignes absentes de la
//     composition qui portent une saisie humaine : sections, notes,
//     optionnelles, prix ou quantité figés, produits ajoutés à la main
//     (quantité > 0, pas issus d'une composition précédente — marqueur
//     écran `compose`) ; une ligne composée HIER et absente aujourd'hui, un
//     placeholder sans produit ou une ligne à quantité nulle ne survivent pas ;
//   • une quantité FIGÉE (`quantiteManuelle`) qui diffère de la quantité
//     recalculée est GARDÉE et remontée dans `conflits` (jamais en silence :
//     l'appelant le dit au vendeur, qui a confirmé avant la recomposition).
// Toute ligne générée porte `compose: true` (marqueur d'écran, jamais envoyé
// au serveur). Fonction PURE.
const _estLigneProduit = (l) => (l?.typeLigne ?? l?.type_ligne ?? 'produit') === 'produit'

export function lignesQuantiteFigee(lignes) {
  return (lignes || []).filter(l => _estLigneProduit(l) && l.quantiteManuelle && l.produit)
}

// Lignes en CONFLIT possible avec une nouvelle composition : seules les
// quantités figées à la main. Un prix tapé ou une option ajoutée sont gardés
// d'office par la fusion, sans question ; une ligne `compose` n'en est jamais une.
export function lignesManuellesEnConflitPossible(lignes) {
  return lignesQuantiteFigee(lignes)
}

// Applique une composition générée : 'garder' fusionne (saisies conservées),
// 'recalcule' ne garde EXACTEMENT que les lignes recalculées.
export function appliquerRecomposition(anciennes, generees, mode = 'garder') {
  if (mode === 'recalcule') {
    return {
      lignes: (Array.isArray(generees) ? generees : []).map(g => ({ ...g, compose: true })),
      conflits: [],
    }
  }
  return fusionnerRecomposition(anciennes, generees)
}

function _ancienneLigneAGarder(l) {
  if (!_estLigneProduit(l)) return true            // section / note
  if (l.optionnelle || l.prixManuel || l.quantiteManuelle) return true
  if (l.compose) return false                      // composition précédente
  return Boolean(l.produit) && (parseFloat(l.quantite) || 0) > 0
}

export function fusionnerRecomposition(anciennes, generees) {
  const olds = Array.isArray(anciennes) ? anciennes : []
  const gens = Array.isArray(generees) ? generees : []
  // File d'anciennes lignes produit par id (appariement dans l'ordre).
  const files = new Map()
  olds.forEach((l, i) => {
    if (!_estLigneProduit(l) || !l.produit) return
    const k = String(l.produit)
    if (!files.has(k)) files.set(k, [])
    files.get(k).push(i)
  })
  const appariee = new Map() // index ancienne → index générée
  const conflits = []
  const fusionnees = gens.map((g, gi) => {
    const file = g?.produit ? files.get(String(g.produit)) : null
    const oi = file && file.length ? file.shift() : null
    if (oi == null) return { ...g, compose: true }
    appariee.set(oi, gi)
    const o = olds[oi]
    // AGNR20 — la ligne ANCIENNE appariée est la base : la composition
    // n'écrase que ce qu'elle POSSÈDE — le produit, la quantité (si elle
    // n'est pas figée), la variante et le prix (s'il n'est pas tapé). Taux
    // de TVA (0 % + base légale), désignation, remise de ligne, groupe villa,
    // lot, rôle… restent ceux du vendeur. Une clé que seule la composition
    // porte est reprise d'elle.
    const base = {
      ...g,
      ...o,
      compose: true,
      produit: g.produit,
      variante: g.variante ?? '',
      quantite: g.quantite,
      prix_unit_ttc: g.prix_unit_ttc,
    }
    if (o.prixManuel) {
      base.prix_unit_ttc = o.prix_unit_ttc
      base.prixManuel = true
    }
    if (o.optionnelle) base.optionnelle = true
    if (o.quantiteManuelle) {
      base.quantiteManuelle = true
      if ((parseFloat(o.quantite) || 0) !== (parseFloat(g.quantite) || 0)) {
        conflits.push({
          designation: o.designation || g.designation || '',
          figee: String(o.quantite),
          recalculee: String(g.quantite),
        })
      }
      base.quantite = o.quantite
    }
    return base
  })
  // Réinsertion des anciennes lignes gardées à leur position RELATIVE.
  const apres = gens.map(() => [])
  const avant = gens.map(() => [])
  const fin = []
  olds.forEach((l, i) => {
    if (appariee.has(i) || !_ancienneLigneAGarder(l)) return
    for (let j = i - 1; j >= 0; j--) {
      if (appariee.has(j)) { apres[appariee.get(j)].push(l); return }
    }
    for (let j = i + 1; j < olds.length; j++) {
      if (appariee.has(j)) { avant[appariee.get(j)].push(l); return }
    }
    fin.push(l)
  })
  const lignes = []
  fusionnees.forEach((l, gi) => { lignes.push(...avant[gi], l, ...apres[gi]) })
  lignes.push(...fin)
  return { lignes, conflits }
}

export function fusionnerVariantes(lignesSans, lignesAvec) {
  const sans = Array.isArray(lignesSans) ? lignesSans : []
  const avec = Array.isArray(lignesAvec) ? lignesAvec : []
  const n = Math.max(sans.length, avec.length)
  const out = []
  for (let i = 0; i < n; i++) {
    const s = sans[i]
    const a = avec[i]
    const rs = _roleVariante(s)
    const ra = _roleVariante(a)
    if (s && a && rs === ra && rs === 'avec') {
      // Batterie / onduleur hybride : le panier AVEC fait foi. Identiques →
      // ligne commune (split mots-clés historique) ; divergents → SA version,
      // taguée — jamais un exemplaire fantôme dimensionné pour « sans ».
      out.push(_memeLigne(s, a) ? { ...s, variante: '' } : { ...a, variante: 'avec' })
      continue
    }
    if (s && a && rs === ra && rs === 'sans') {
      // Onduleur réseau : le panier SANS fait foi (symétrique du cas avec).
      out.push(_memeLigne(s, a) ? { ...s, variante: '' } : { ...s, variante: 'sans' })
      continue
    }
    if (s && !a) { out.push({ ...s, variante: rs || 'sans' }); continue }
    if (a && !s) { out.push({ ...a, variante: ra || 'avec' }); continue }
    if (_memeLigne(s, a)) { out.push({ ...s, variante: '' }); continue }
    // Paire ordinaire divergente (ou dérive défensive de rôles) : chaque côté
    // garde sa version — taguée par son RÔLE quand il en a un.
    out.push({ ...s, variante: rs || 'sans' })
    out.push({ ...a, variante: ra || 'avec' })
  }
  return out
}
