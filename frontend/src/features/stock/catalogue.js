// Taxonomie catalogue : CATÉGORIE → MARQUE → ARTICLES.
// Le groupement d'affichage suit la catégorie RÉELLE du produit (rangée par
// le seeder, ordre délibéré via Categorie.ordre) — jamais l'ordre alphabétique.
// La sélection auto-fill, elle, reste par mots-clés du nom (solar.js) : cette
// couche est purement visuelle et ne peut pas casser le dimensionnement.
import {
  Sun, Zap, BatteryCharging, Wrench, ShieldCheck, Cable, Droplets, Cpu,
  ClipboardList, Package,
} from 'lucide-react'
import {
  parseWatt, parseKw, parseKwh, parsePhaseIsTri, tauxTvaOf, ttcFromHt, _norm,
} from '../ventes/solar.js'

export const MARQUE_GENERIQUE = 'Génériques'

// APX18 — icône de CATÉGORIE, repli de la vignette photo. Construite d'office
// (APX19/APX36 s'appuient dessus) : elle fonctionne que le produit ait une
// photo ou non, donc la 1ʳᵉ colonne du catalogue a TOUJOURS un visuel de la
// même boîte 40 px — la hauteur de ligne ne dépend jamais des données.
// Renvoie un COMPOSANT lucide (pas de JSX ici : ce module reste du .js pur).
// Les libellés suivent la taxonomie du seeder (`seed_catalogue.TAXONOMIE`) ;
// une catégorie libre ou absente retombe sur le carton générique.
const ICONES_CATEGORIE = [
  [/panneau/i, Sun],
  [/onduleur/i, Zap],
  [/batterie/i, BatteryCharging],
  [/structure|fixation/i, Wrench],
  [/protection|accessoire/i, ShieldCheck],
  [/c[âa]ble/i, Cable],
  [/pompe/i, Droplets],
  [/variateur/i, Cpu],
  [/service|prestation/i, ClipboardList],
]

// STKCAT16 — icône par TYPE d'équipement (`typeOfProduit`, cf. plus bas :
// champ plat `categorie_type` ou `categorie.type_equipement`, l'enum stable
// stock.Categorie.TypeEquipement côté serveur) — fiable même si la catégorie
// est renommée/traduite, contrairement aux regex par NOM ci-dessus. Pas
// d'icône « compteur » dédiée dans le jeu lucide déjà importé pour ce module :
// Zap (déjà l'icône Onduleur) est la plus proche sémantiquement — un compteur
// mesure de l'électricité, ce n'est pas une protection mécanique (ShieldCheck
// reste réservé aux disjoncteurs/parafoudres de la catégorie Protection).
const ICONE_PAR_TYPE = {
  panneau: Sun,
  onduleur: Zap,
  batterie: BatteryCharging,
  structure: Wrench,
  protection: ShieldCheck,
  cable: Cable,
  pompe: Droplets,
  variateur: Cpu,
  compteur: Zap,
  accessoire: ShieldCheck,
  service: ClipboardList,
}

export function categorieIcone(produit) {
  const type = typeOfProduit(produit)
  if (type && ICONE_PAR_TYPE[type]) return ICONE_PAR_TYPE[type]
  const nom = produit?.categorie?.nom ?? ''
  for (const [motif, Icone] of ICONES_CATEGORIE) {
    if (motif.test(nom)) return Icone
  }
  return Package
}

// STKCAT16 — même formule que l'ancien aiguillage par NOM ci-dessous, mais
// pilotée par `typeOfProduit`. Structure/protection/service/compteur/
// accessoire n'ont explicitement AUCUNE spec clé inventée (comme les
// catégories homonymes par nom ne le faisaient déjà pas).
function _keySpecParType(type, p) {
  const nom = p.nom ?? ''
  if (type === 'panneau') {
    const w = parseWatt(nom)
    return w ? `${w} Wc` : null
  }
  if (type === 'onduleur' || type === 'variateur') {
    const kw = parseFloat(p.pompe_kw) || parseKw(nom)
    const phase = p.tension_v
      ? `${p.tension_v} V`
      : (parsePhaseIsTri(nom) ? 'Triphasé' : (/monophas/i.test(nom) ? 'Monophasé' : null))
    if (kw && phase) return `${kw} kW · ${phase}`
    return kw ? `${kw} kW` : phase
  }
  if (type === 'batterie') {
    const kwh = parseKwh(nom)
    return kwh ? `${kwh} kWh` : null
  }
  if (type === 'pompe') {
    const cv = parseFloat(p.pompe_cv)
    const hmt = parseFloat(p.hmt_m)
    const parts = []
    if (cv) parts.push(`${cv} CV`)
    if (hmt) parts.push(`HMT d'arrêt ${hmt} m`)
    if (p.courbe_pompe) parts.push('courbe constructeur')
    return parts.join(' · ') || null
  }
  if (type === 'cable') return /m[eè]tre/i.test(nom) ? 'au mètre' : null
  return null
}

// Spec CLÉ par catégorie — celle qui compte pour choisir l'article. Lit
// d'abord `typeOfProduit(p)` (STKCAT16) ; retombe sur les égalités de nom
// historiques quand le type est absent (catégorie pas encore migrée).
export function keySpec(p) {
  const type = typeOfProduit(p)
  if (type) return _keySpecParType(type, p)
  const cat = p.categorie?.nom ?? ''
  const nom = p.nom ?? ''
  if (cat.startsWith('Panneaux')) {
    const w = parseWatt(nom)
    return w ? `${w} Wc` : null
  }
  if (cat.startsWith('Onduleurs') || cat === 'Variateurs') {
    const kw = parseFloat(p.pompe_kw) || parseKw(nom)
    const phase = p.tension_v
      ? `${p.tension_v} V`
      : (parsePhaseIsTri(nom) ? 'Triphasé' : (/monophas/i.test(nom) ? 'Monophasé' : null))
    if (kw && phase) return `${kw} kW · ${phase}`
    return kw ? `${kw} kW` : phase
  }
  if (cat === 'Batteries') {
    const kwh = parseKwh(nom)
    return kwh ? `${kwh} kWh` : null
  }
  if (cat === 'Pompes') {
    const cv = parseFloat(p.pompe_cv)
    const hmt = parseFloat(p.hmt_m)
    const parts = []
    if (cv) parts.push(`${cv} CV`)
    if (hmt) parts.push(`HMT d'arrêt ${hmt} m`)
    if (p.courbe_pompe) parts.push('courbe constructeur')
    return parts.join(' · ') || null
  }
  if (cat === 'Câbles') return /m[eè]tre/i.test(nom) ? 'au mètre' : null
  return null
}

export const prixTtc = (p) => ttcFromHt(p.prix_vente, tauxTvaOf(p))
export const sansPrix = (p) => !(parseFloat(p.prix_vente) > 0)

// Type d'un produit : le champ plat `categorie_type` avec repli sur la
// catégorie imbriquée pour rester robuste si l'API n'a pas encore le champ.
export const typeOfProduit = (p) => p?.categorie_type ?? p?.categorie?.type_equipement ?? null

// Famille attendue pour un rôle dans la composition d'une installation.
// Mappe les rôles aux familles de produits : 'structure' pour les structures,
// 'panneau' pour les panneaux, 'batterie' pour les batteries, null pour tout le reste.
export const familleAttendue = (role) => {
  if (!role) return null
  if (['structure', 'structure_acier', 'structure_alu'].includes(role)) return 'structure'
  if (role === 'panneau') return 'panneau'
  if (role === 'batterie') return 'batterie'
  return null
}

/* ── APX19 — Sévérité du niveau de stock ───────────────────────────────────
   Avant, RUPTURE (0 en stock, on ne peut plus vendre) et SOUS SEUIL (il en
   reste, il faut recommander) partageaient un unique badge « stock bas » :
   deux urgences très différentes, un seul signal. Trois états distincts
   désormais. `is_low_stock` (calculé serveur) fait autorité pour le
   sous-seuil ; la rupture prime dessus. */
export const SEV_RUPTURE = 'rupture'
export const SEV_BAS = 'bas'
export const SEV_OK = 'ok'

export function severiteStock(p) {
  const stock = Number(p?.quantite_stock) || 0
  if (stock <= 0) return SEV_RUPTURE
  const seuil = Number(p?.seuil_alerte) || 0
  if (p?.is_low_stock || (seuil > 0 && stock <= seuil)) return SEV_BAS
  return SEV_OK
}

/* Remplissage de la jauge, en %. La cible « saine » est 2× le seuil — la MÊME
   cible que la suggestion de réassort déjà affichée, on n'invente pas un
   second barème. Sans seuil renseigné, un stock non nul est plein (on ne peut
   rien promettre d'autre honnêtement). */
export function jaugeStock(p) {
  const stock = Math.max(0, Number(p?.quantite_stock) || 0)
  const seuil = Number(p?.seuil_alerte) || 0
  if (seuil <= 0) return stock > 0 ? 100 : 0
  return Math.round(Math.min(100, (stock / (seuil * 2)) * 100))
}

// APX20 — un produit est « de pompage » dès qu'il porte une caractéristique de
// pompe : sa fiche technique gagne alors puissance et tension, et elles seules.
export function estPompage(produit) {
  return [produit?.pompe_kw, produit?.tension_v, produit?.pompe_cv, produit?.hmt_m]
    .some((v) => v !== null && v !== undefined && v !== '')
}

/* ── APX21 — Points traçables de la courbe constructeur ────────────────────
   Les 11 pompes OSP 30 embarquent leur courbe débit→HMT (`courbe_pompe`).
   Elle servait UNIQUEMENT au dimensionnement (`solar.js debitAtHmt`) et
   n'apparaissait à l'écran qu'en badge TEXTE : personne ne l'a jamais vue.
   Renvoie les couples (débit m³/h, HMT m), ou `null` si la courbe est absente
   ou malformée — l'écran ne rend alors RIEN, jamais une carte vide. Mêmes
   garde-fous de forme que `debitAtHmt`, pour que le graphique ne puisse pas
   montrer autre chose que ce qui dimensionne. */
export function pointsCourbePompe(courbe) {
  if (!courbe || !Array.isArray(courbe.debits_m3h) || !Array.isArray(courbe.hmt_m)) {
    return null
  }
  const d = courbe.debits_m3h.map(Number)
  const h = courbe.hmt_m.map(Number)
  if (d.length < 2 || d.length !== h.length) return null
  if (d.some((v) => !Number.isFinite(v)) || h.some((v) => !Number.isFinite(v))) {
    return null
  }
  return d.map((debit, i) => ({ debit, hmt: h[i] }))
}

// CATÉGORIE → MARQUE → ARTICLES, ordres délibérés :
// catégories par Categorie.ordre ; marques par nombre d'articles décroissant,
// « Génériques » (sans marque) toujours en dernier.
export function groupCatalogue(produits) {
  const cats = new Map()
  for (const p of produits) {
    const nom = p.categorie?.nom ?? 'Autres'
    const ordre = p.categorie?.ordre ?? 999
    if (!cats.has(nom)) cats.set(nom, { nom, ordre, items: [] })
    cats.get(nom).items.push(p)
  }
  const out = [...cats.values()].sort((a, b) => a.ordre - b.ordre || a.nom.localeCompare(b.nom))
  for (const c of out) {
    const brands = new Map()
    for (const p of c.items) {
      const m = (p.marque || '').trim() || MARQUE_GENERIQUE
      if (!brands.has(m)) brands.set(m, [])
      brands.get(m).push(p)
    }
    c.count = c.items.length
    c.brands = [...brands.entries()]
      .map(([marque, items]) => ({ marque, items }))
      .sort((a, b) => {
        if (a.marque === MARQUE_GENERIQUE) return 1
        if (b.marque === MARQUE_GENERIQUE) return -1
        return b.items.length - a.items.length || a.marque.localeCompare(b.marque)
      })
  }
  return out
}

// Recherche transverse (nom, SKU, marque, catégorie, spec, description) —
// STKCAT15 : insensible aux accents/casse des DEUX côtés (requête ET botte de
// foin produit, via `_norm` partagée avec solar.js) et à jetons ET — chaque
// mot de la requête doit être un sous-mot d'AU MOINS un des champs du produit
// pour que celui-ci soit retenu (« hybride deye » == « deye hybride »), donc
// un jeton numérique nu (« 550 ») trouve aussi bien un nom qu'une spec
// (keySpec) qui le contient. Union stricte des anciens champs (nom, sku,
// marque, catégorie, spec) + description en prime — jamais un champ retiré.
const _prepTexte = (s) => _norm(s).replace(/['’ʼ`]/g, ' ').replace(/\s+/g, ' ').trim()

function _botteDeFoin(p) {
  return _prepTexte([
    p.nom, p.sku, p.marque, p.categorie?.nom, keySpec(p), p.description,
  ].filter(Boolean).join(' '))
}

export function searchCatalogue(produits, query) {
  const q = _prepTexte(query)
  if (!q) return produits
  const jetons = q.split(' ').filter(Boolean)
  return produits.filter((p) => {
    const foin = _botteDeFoin(p)
    return jetons.every((j) => foin.includes(j))
  })
}

/**
 * AGR105 — contrôle d'une courbe de pompe saisie ligne par ligne, MIROIR de la
 * règle serveur AGR102 (`controle_courbe_pompe_lisible`) : valeurs >= 0,
 * débits STRICTEMENT croissants, HMT NON croissante. Seules les lignes
 * COMPLÈTES (deux nombres) comptent comme des points ; rien n'est re-trié,
 * arrondi ni corrigé en silence.
 *
 * Rend `{ parLigne, bandeau }` : `parLigne[i] = { debit?: msg, hmt?: msg }`
 * (index = ligne de la table, pour afficher le message SOUS la cellule
 * fautive) ; `bandeau` = phrase nommant la première cellule fautive, ou null.
 */
export function erreursCourbePompe(rows) {
  const parLigne = {}
  let bandeau = null
  const marquer = (i, col, message) => {
    parLigne[i] = { ...(parLigne[i] ?? {}), [col]: message }
    if (!bandeau) bandeau = `Courbe constructeur, point ${i + 1} — ${message}`
  }
  let prec = null
  rows.forEach((r, i) => {
    const debit = parseFloat(r?.debit)
    const hmt = parseFloat(r?.hmt)
    if (!Number.isFinite(debit) || !Number.isFinite(hmt)) return
    if (debit < 0) marquer(i, 'debit', 'le débit ne peut pas être négatif.')
    if (hmt < 0) marquer(i, 'hmt', 'la HMT ne peut pas être négative.')
    if (prec) {
      if (debit <= prec.debit) {
        marquer(i, 'debit', `les débits doivent être strictement croissants (${debit} après ${prec.debit}).`)
      }
      if (hmt > prec.hmt) {
        marquer(i, 'hmt', `la HMT doit être non croissante (${hmt} après ${prec.hmt}).`)
      }
    }
    prec = { debit, hmt }
  })
  return { parLigne, bandeau }
}

// AGR105 — vocabulaire pompage. Les clés sont celles de `ROLES_POMPAGE`
// (core/product_roles.py, contrat `produit_pompage.json`) ; les libellés FR
// sont ceux du contrat. Le serveur reste l'autorité (400 nommant `role_pompage`).
// source-choix: core.product_roles.ROLES_POMPAGE
export const ROLES_POMPAGE = [
  ['pompe', 'Pompe'],
  ['variateur_pompage', 'Variateur de pompage'],
  ['afficheur_variateur', 'Afficheur du variateur'],
  ['structure_sol', 'Structure au sol'],
  ['cable_dc', 'Câble DC (panneaux → variateur)'],
  ['cable_descente', 'Câble de descente (variateur → pompe)'],
  ['protection_dc', 'Protection DC'],
  ['sonde_niveau', 'Sonde de niveau (protection marche à sec)'],
  ['compteur_eau', "Compteur d'eau"],
  ['colonne_refoulement', 'Colonne de refoulement'],
  ['clapet', 'Clapet anti-retour'],
  ['tuyauterie', 'Tuyauterie'],
  ['bassin', 'Bassin'],
  ['installation_pompage', 'Installation pompage'],
  ['entretien_pompage', 'Entretien pompage'],
  ['antivol', 'Antivol'],
  ['cloture', 'Clôture'],
]
// source-choix: stock.Produit.type_pompe
export const TYPES_POMPE = [['immergee', 'Immergée'], ['surface', 'Surface'], ['dc', 'DC']]
// source-choix: stock.Produit.alimentation
export const ALIMENTATIONS = [['mono', 'Monophasée'], ['tri', 'Triphasée'], ['dc', 'DC']]

/** Libellé FR d'une clé de vocabulaire pompage (`''` si inconnue / vide). */
export function libelleRolePompage(cle) {
  return ROLES_POMPAGE.find(([k]) => k === cle)?.[1] ?? ''
}
export function libelleTypePompe(cle) {
  return TYPES_POMPE.find(([k]) => k === cle)?.[1] ?? ''
}
export function libelleAlimentation(cle) {
  return ALIMENTATIONS.find(([k]) => k === cle)?.[1] ?? ''
}
