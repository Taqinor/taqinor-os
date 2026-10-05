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
  isPompe,
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
// source-choix: core.product_roles.TYPES_POMPE
export const TYPES_POMPE = [['immergee', 'Immergée'], ['surface', 'Surface'], ['dc', 'DC']]
// source-choix: core.product_roles.ALIMENTATIONS_POMPAGE
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

/* ── AGR106 — « Pompage à compléter » + « kit pompage chiffrable » ──────────
   Lecture SEULE, sur ce que le catalogue sert déjà (aucune valeur inventée,
   aucun seuil). `prix_achat` n'est lu ICI que comme drapeau « à renseigner »
   (écran interne Stock) : jamais affiché, jamais envoyé vers un document
   client. Le rôle vient de `role_pompage` DÉCLARÉ, sinon de la catégorie typée
   puis du nom (même ordre que `stock.selectors.produits_pompage`). */

/** Rôle pompage d'un produit du catalogue, ou `null` s'il n'en a pas. */
export function roleDuProduitPompage(p) {
  if (p?.role_pompage) return p.role_pompage
  const type = typeOfProduit(p)
  const nom = _norm(p?.nom ?? '')
  if (type === 'variateur' || nom.includes('variateur')) {
    return nom.includes('afficheur') ? 'afficheur_variateur' : 'variateur_pompage'
  }
  if (type === 'pompe' || isPompe(p?.nom ?? '')) return 'pompe'
  return null
}

/** Alimentation (mono / tri / dc) : déclarée, sinon tension, sinon nom. */
export function alimentationDuProduit(p) {
  if (p?.alimentation) return p.alimentation
  if (Number(p?.tension_v) === 220) return 'mono'
  if (Number(p?.tension_v) === 380) return 'tri'
  const nom = _norm(p?.nom ?? '')
  if (nom.includes('monophas')) return 'mono'
  if (nom.includes('triphas')) return 'tri'
  return ''
}

const CHAMPS_FICHE_VARIATEUR = [
  'ond_mppt_v_min', 'ond_mppt_v_max', 'ond_v_max_abs', 'ond_i_max_mppt_a',
  'ond_phases', 'ond_v_demarrage_v', 'var_voc_reco_min_v', 'var_voc_reco_max_v',
  'var_v_sortie_v', 'var_i_sortie_nominal_a', 'var_protection_marche_a_sec',
  'var_rendement_mppt_pct',
]

/** Une fiche variateur est « saisie » si elle est typée et porte au moins une
 * valeur publiée (une fiche vide = « fiche à saisir »). */
export function ficheVariateurSaisie(fiche) {
  if (fiche?.type_fiche !== 'variateur_pompage') return false
  return CHAMPS_FICHE_VARIATEUR.some(
    (k) => fiche[k] !== null && fiche[k] !== undefined && fiche[k] !== '')
}

const _pricee = (p) => !sansPrix(p)
const _avecCourbe = (p) => pointsCourbePompe(p?.courbe_pompe) != null
const _fiche = (fiches, p) => (fiches && typeof fiches.get === 'function' ? fiches.get(p.id) : null)

/** Articles à rôle pompage qui bloquent un devis pompage : sans prix de vente,
 * sans prix d'achat (quand il est servi), pompe sans courbe, variateur sans
 * fiche. Rend `[{ produit, role, raisons: [...] }]`, archivés exclus. */
export function produitsPompageACompleter(produits, fiches) {
  const out = []
  for (const p of produits ?? []) {
    if (p?.is_archived) continue
    const role = roleDuProduitPompage(p)
    if (!role) continue
    const raisons = []
    if (sansPrix(p)) raisons.push('prix de vente à renseigner')
    if (p.prix_achat !== undefined && p.prix_achat !== null
        && !(parseFloat(p.prix_achat) > 0)) raisons.push("prix d'achat à renseigner")
    if (role === 'pompe' && !_avecCourbe(p)) raisons.push('courbe constructeur absente')
    if (role === 'variateur_pompage' && !ficheVariateurSaisie(_fiche(fiches, p))) {
      raisons.push('fiche variateur à saisir')
    }
    if (raisons.length) out.push({ produit: p, role, raisons })
  }
  return out
}

/** « Kit pompage chiffrable : oui / non » et CE QUI MANQUE : une pompe pricée
 * avec courbe par alimentation, un variateur pricé avec fiche, des protections
 * DC pricées. Rend `{ chiffrable, manques: [...] }`. */
export function kitPompageChiffrable(produits, fiches) {
  const actifs = (produits ?? []).filter((p) => !p?.is_archived)
  const manques = []
  for (const [alim, libelle] of [['mono', 'monophasée'], ['tri', 'triphasée']]) {
    const ok = actifs.some((p) => roleDuProduitPompage(p) === 'pompe' && _pricee(p)
      && _avecCourbe(p) && alimentationDuProduit(p) === alim)
    if (!ok) manques.push(`aucune pompe ${libelle} pricée avec courbe`)
  }
  if (!actifs.some((p) => roleDuProduitPompage(p) === 'variateur_pompage' && _pricee(p)
      && ficheVariateurSaisie(_fiche(fiches, p)))) {
    manques.push('aucun variateur pricé avec fiche')
  }
  if (!actifs.some((p) => roleDuProduitPompage(p) === 'protection_dc' && _pricee(p))) {
    manques.push('aucune protection DC pricée')
  }
  return { chiffrable: manques.length === 0, manques }
}

// ── CIQ104 — usage C&I (contrat produit_ci.json) ──────────────────────────
// Les rôles C&I et les types de pose ne sont PAS recopiés ici : leurs
// libellés FR voyagent par l'API (choix de `role_ci` / `type_pose` servis
// par OPTIONS sur /stock/produits/). Seuls les petits vocabulaires de FICHE
// sont déclarés, avec leur source vérifiée par check_choices_declares.

/** Type de fiche C&I qu'appelle un rôle C&I (`null` = pas de fiche C&I). */
export const TYPE_FICHE_PAR_ROLE_CI = {
  onduleur_string_tri: 'onduleur',
  compteur_injection: 'limiteur',
  controleur_injection: 'limiteur',
  logger_supervision: 'logger',
  protection_ac: 'protection',
  protection_dc: 'protection',
  coffret_ac: 'protection',
  coffret_dc: 'protection',
  cable_ac: 'cable',
  mise_a_la_terre: 'cable',
  structure_ci: 'structure',
}

export function typeFicheCi(roleCi) {
  return TYPE_FICHE_PAR_ROLE_CI[roleCi] ?? null
}

/** Champs de fiche C&I par type (ordre du contrat). */
export const CHAMPS_FICHE_CI = {
  onduleur: ['ond_limitation_export', 'ond_compteurs_compatibles',
    'ond_relais_decouplage', 'ond_cos_phi_min', 'ond_cos_phi_max'],
  limiteur: ['lim_mode', 'lim_i_max_a', 'lim_onduleurs_max', 'lim_marques', 'lim_phases'],
  logger: ['log_onduleurs_max', 'log_marques'],
  protection: ['prot_type', 'prot_cote', 'prot_calibre_a', 'prot_pouvoir_coupure_ka',
    'prot_poles', 'prot_tension_v'],
  cable: ['cable_cote', 'cable_section_mm2', 'cable_ame'],
  structure: ['struct_type_pose', 'struct_masse_kg_m2', 'struct_notice_document',
    'struct_notice_date', 'struct_notice_page'],
}

const _LISTES_CI = ['ond_compteurs_compatibles', 'lim_marques', 'log_marques']
const _ENTIERS_CI = ['lim_onduleurs_max', 'lim_phases', 'log_onduleurs_max', 'prot_poles',
  'struct_notice_page']
const _NOMBRES_CI = ['ond_cos_phi_min', 'ond_cos_phi_max', 'lim_i_max_a', 'prot_calibre_a',
  'prot_pouvoir_coupure_ka', 'prot_tension_v', 'cable_section_mm2', 'struct_masse_kg_m2']

/** Libellés d'écran des champs de fiche C&I. */
export const LIBELLES_FICHE_CI = {
  ond_limitation_export: "Limitation d'export",
  ond_compteurs_compatibles: 'Compteurs compatibles (séparés par des virgules)',
  ond_relais_decouplage: 'Relais de découplage',
  ond_cos_phi_min: 'cos φ réglable mini',
  ond_cos_phi_max: 'cos φ réglable maxi',
  lim_mode: 'Mode de raccordement',
  lim_i_max_a: 'Courant maxi en direct (A)',
  lim_onduleurs_max: "Nombre d'onduleurs pilotés",
  lim_marques: 'Marques compatibles (séparées par des virgules)',
  lim_phases: 'Phases (1 ou 3)',
  log_onduleurs_max: "Nombre d'onduleurs supervisés",
  log_marques: 'Marques supervisées (séparées par des virgules)',
  prot_type: 'Type de protection',
  prot_cote: 'Côté de la protection',
  prot_calibre_a: 'Calibre (A)',
  prot_pouvoir_coupure_ka: 'Pouvoir de coupure (kA)',
  prot_poles: 'Nombre de pôles',
  prot_tension_v: 'Tension assignée (V)',
  cable_cote: 'Côté du câble',
  cable_section_mm2: 'Section (mm²)',
  cable_ame: 'Âme',
  struct_type_pose: 'Type de pose de la structure',
  struct_masse_kg_m2: 'Masse du système posé (kg/m²)',
  struct_notice_document: 'Notice fabricant (document)',
  struct_notice_date: 'Notice — date',
  struct_notice_page: 'Notice — page',
}

// source-choix: core.product_roles.LIM_MODES
export const CHOIX_LIM_MODE = [
  ['compteur_direct', 'Compteur en direct'],
  ['compteur_tc', 'Compteur à TC'],
  ['controleur', 'Contrôleur'],
]
// source-choix: core.product_roles.OND_LIMITATIONS_EXPORT
export const CHOIX_OND_LIMITATION = [
  ['integree', 'Intégrée'],
  ['compteur_requis', 'Compteur requis'],
  ['controleur_requis', 'Contrôleur requis'],
  ['non_publiee', 'Non publiée'],
]
// source-choix: core.product_roles.OND_RELAIS_DECOUPLAGE
export const CHOIX_OND_RELAIS = [
  ['integre', 'Intégré'],
  ['externe', 'Externe'],
  ['non_publie', 'Non publié'],
]
// source-choix: core.product_roles.PROT_TYPES
export const CHOIX_PROT_TYPE = [
  ['disjoncteur', 'Disjoncteur'],
  ['sectionneur', 'Sectionneur'],
  ['fusible', 'Fusible'],
  ['parafoudre', 'Parafoudre'],
  ['ddr', 'Différentiel (DDR)'],
  ['interrupteur', 'Interrupteur'],
]
// source-choix: core.product_roles.COTES_AC_DC
export const CHOIX_COTE = [['ac', 'AC'], ['dc', 'DC']]
// source-choix: core.product_roles.CABLE_AMES
export const CHOIX_AME = [['cu', 'Cuivre'], ['al', 'Aluminium']]

/** Les choix (clé, libellé) d'un champ texte de fiche C&I, ou `null`. */
export function choixChampFicheCi(cle) {
  return {
    ond_limitation_export: CHOIX_OND_LIMITATION,
    ond_relais_decouplage: CHOIX_OND_RELAIS,
    lim_mode: CHOIX_LIM_MODE,
    prot_type: CHOIX_PROT_TYPE,
    prot_cote: CHOIX_COTE,
    cable_cote: CHOIX_COTE,
    cable_ame: CHOIX_AME,
  }[cle] ?? null
}

export const estChampFicheCiNumerique = (cle) => _ENTIERS_CI.includes(cle) || _NOMBRES_CI.includes(cle)

/** État de formulaire (chaînes) des champs C&I d'une fiche servie. */
export function ficheCiDepuisServeur(fiche) {
  const out = {}
  for (const cles of Object.values(CHAMPS_FICHE_CI)) {
    for (const cle of cles) out[cle] = ''
  }
  if (!fiche) return out
  for (const cle of Object.keys(out)) {
    if (cle.startsWith('struct_notice_')) continue
    const v = fiche[cle]
    if (_LISTES_CI.includes(cle)) out[cle] = Array.isArray(v) ? v.join(', ') : ''
    else out[cle] = (v === null || v === undefined) ? '' : String(v)
  }
  const notice = fiche.struct_notice ?? {}
  out.struct_notice_document = notice.document ?? ''
  out.struct_notice_date = notice.date ?? ''
  out.struct_notice_page = notice.page != null ? String(notice.page) : ''
  return out
}

function _valeurServeurCi(cle, brut) {
  const s = String(brut ?? '').trim()
  if (_LISTES_CI.includes(cle)) return s ? s.split(',').map((x) => x.trim()).filter(Boolean) : []
  if (_ENTIERS_CI.includes(cle) || _NOMBRES_CI.includes(cle)) {
    // Saisie libre : jamais arrondie, jamais rejetée ici (le serveur tranche).
    return s === '' ? null : Number(s.replace(',', '.'))
  }
  return s
}

/** PATCH des seuls champs C&I MODIFIÉS d'un type de fiche (objet vide si rien
 * n'a bougé — « enregistrer sans toucher = PATCH vide »). La provenance de
 * masse repart en objet `struct_notice` dès qu'une de ses parties change. */
export function patchFicheCi(typeFiche, initial, courant) {
  const out = {}
  const cles = CHAMPS_FICHE_CI[typeFiche] ?? []
  let noticeChange = false
  for (const cle of cles) {
    if ((initial?.[cle] ?? '') === (courant?.[cle] ?? '')) continue
    if (cle.startsWith('struct_notice_')) { noticeChange = true; continue }
    out[cle] = _valeurServeurCi(cle, courant[cle])
  }
  if (noticeChange) {
    out.struct_notice = {
      document: String(courant.struct_notice_document ?? '').trim(),
      date: courant.struct_notice_date || null,
      page: _valeurServeurCi('struct_notice_page', courant.struct_notice_page),
    }
  }
  return out
}

/** Choix `[[valeur, libellé]]` d'un champ, lus dans la réponse OPTIONS
 * (`actions.POST.<champ>.choices`) — les libellés FR du serveur. */
export function choixDepuisOptions(optionsData, champ) {
  const choix = optionsData?.actions?.POST?.[champ]?.choices
    ?? optionsData?.actions?.PUT?.[champ]?.choices ?? []
  return choix
    .filter((c) => c && c.value !== '' && c.value != null)
    .map((c) => [String(c.value), String(c.display_name ?? c.value)])
}

/** « C&I à compléter » : un rôle C&I sans prix de vente, ou exclu (fiche
 * incomplète…), lu sur `etat_ci` servi par l'API. */
export function produitCiACompleter(p) {
  const etat = p?.etat_ci
  if (!etat) return false
  return !etat.prix_connu || !etat.eligible_ci
}

/** La raison affichée d'un article C&I à compléter (`''` sinon). */
export function raisonCiACompleter(p) {
  const etat = p?.etat_ci
  if (!etat) return ''
  if (!etat.eligible_ci && etat.motif_exclusion) return etat.motif_exclusion
  if (!etat.prix_connu) return 'prix à renseigner'
  return ''
}
