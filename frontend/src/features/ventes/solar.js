// Solar math + catalogue auto-fill, ported 1:1 from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill.py / autofill_router.py, app.js).
// The simulator is the source of truth: prices are handled in TTC (like the
// simulator UI) and only converted to HT at save time. Pure functions, no I/O.
// The premium PDF engine computes its own figures server-side — never fed here.

import { formatMAD } from '../../lib/format.js'
// QJR567 — la population des totaux (ligne PRODUIT non optionnelle) vient de
// `ligneCompteDansTotaux` (remise.js, même règle que le noyau des totaux ;
// remise.js n'importe rien : aucun cycle).
import { ligneCompteDansTotaux, PAS_ARRONDI_DEVIS, totauxCanoniques } from './remise.js'
import { SCENARIOS_VALIDES } from './quote/scenarios.js'
// SPL195 — modèle tarifaire (barèmes, factures ⇄ kWh, deux factures) déplacé
// tel quel dans calc/tarifs.js ; seul computeROI le lit encore ici.
import { twoBillsSavings } from './calc/tarifs.js'

// ── Constantes Maroc (irradiance GHI mensuelle + tarif ONEE) ──────────────────
// DC9 — MIROIR de la source Python unique
// (backend apps/ventes/quote_engine/constants.py GHI). Les deux tables DOIVENT
// rester identiques : un test de parité (test_dc9_ghi_parity.py) échoue sinon.
// Ne jamais éditer l'une sans répercuter l'autre à l'identique.
export const GHI = [
  83.99, 96.79, 133.43, 155.30, 175.28, 179.62,
  179.56, 161.17, 137.03, 111.59, 81.91, 74.61,
]
// Libellés des mois : grille des factures (complets) vs graphique (courts),
// exactement comme dans le simulateur (MONTHS_FR vs labels du chart).
export const MONTHS_FR = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
  'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const CHART_MONTHS = [
  'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Jun',
  'Jul', 'Aoû', 'Sep', 'Oct', 'Nov', 'Déc',
]
export const EFFICIENCY = 0.8 // rendement global
export const KWH_PRICE = 1.75 // MAD/kWh ONEE — usage interne, jamais affiché

// ── QX38 — productible CANONIQUE (kWh/kWc/an) par ville, source PVGIS ─────────
// MIROIR EXACT de backend apps/ventes/quote_engine/productible.py
// (PRODUCTIBLE_PAR_VILLE + DEFAULT_PRODUCTIBLE) et de apps/web yieldTable.ts
// (aspect Sud, inclinaison optimale). Les trois DOIVENT rester alignés :
// l'écran, le PDF et la proposition web affichent alors la MÊME production/
// économies pour les mêmes entrées. Ne jamais éditer l'un sans les deux autres.
export const PRODUCTIBLE_PAR_VILLE = {
  agadir: 1687,
  marrakech: 1651,
  casablanca: 1651,
  rabat: 1630,
  tanger: 1634,
}
export const DEFAULT_PRODUCTIBLE = 1651 // Casablanca (centre zone de service)

// ── Pertes système : 20 % AU TOTAL (ordre fondateur, 18/08) — MIROIR pricing.py
// Les productibles ci-dessus sont des sorties PVGIS demandées à `loss=14`
// (cf. backend apps/parametres/pvgis.py) : 14 % de pertes sont DÉJÀ dedans.
// Le fondateur fixe le total à 20 % → on applique le seul COMPLÉMENT,
// (1 − 20 %)/(1 − 14 %) ≈ 0,9302, pour passer d'un productible « net à 14 % »
// à un productible « net à 20 % ». Le chemin historique GHI × EFFICIENCY (0,8)
// porte DÉJÀ les 20 % : il n'est pas touché (sinon on compterait deux fois).
export const SYSTEM_LOSS_TOTAL = 0.20   // pertes système TOTALES (fondateur 18/08)
export const PVGIS_BUILTIN_LOSS = 0.14  // pertes déjà incluses dans le productible
export const PRODUCTIBLE_NET_FACTOR = (1 - SYSTEM_LOSS_TOTAL) / (1 - PVGIS_BUILTIN_LOSS)
const _PRODUCTIBLE_HISTORICAL_DEFAULT = 1600
const _CITY_ALIASES = {
  casa: 'casablanca', kenitra: 'rabat', sale: 'rabat', salé: 'rabat',
  mohammedia: 'casablanca', 'el jadida': 'casablanca', essaouira: 'agadir',
  safi: 'casablanca', temara: 'rabat', témara: 'rabat', tetouan: 'tanger',
  tétouan: 'tanger', settat: 'casablanca', benguerir: 'marrakech',
  berrechid: 'casablanca',
}

// Productible canonique pour une ville. `override` = productible société
// (CompanyProfile) : quand il diffère RÉELLEMENT du défaut historique 1600, il
// prime ; sinon on lit le productible PVGIS de la ville (repli DEFAULT).
export function productibleForCity(city, override = null) {
  const ov = parseFloat(override)
  if (Number.isFinite(ov) && ov > 0 && Math.abs(ov - _PRODUCTIBLE_HISTORICAL_DEFAULT) > 0.5) {
    return ov
  }
  const key = String(city || '').trim().toLowerCase()
  if (!key) return DEFAULT_PRODUCTIBLE
  const norm = _CITY_ALIASES[key] || key
  return PRODUCTIBLE_PAR_VILLE[norm] ?? DEFAULT_PRODUCTIBLE
}

// Factures mensuelles affichées au chargement (initApp du simulateur)
export const DEFAULT_MONTHLY_BILLS = [500, 450, 400, 380, 360, 500, 700, 680, 580, 480, 430, 480]

// Autoconsommation par défaut selon le type d'installation. CIQ128 — plus
// d'entrée commerciale ni industrielle : le profil de charge C&I est DÉCLARÉ
// au moteur serveur (`etude-ci/preview`), jamais une part diurne d'écran.
export const DAY_USAGE_DEFAULTS = {
  'Résidentielle': 60,
  'Agricole': 100,
}

// ── QX44 — catégories commerciales et leurs questions (libellés de SAISIE) ──
// CIQ128 — la part diurne par catégorie (table et fonction de day-share) est
// SUPPRIMÉE : la catégorie et ses réponses partent au
// moteur serveur C&I (`rythme.categorie_commerciale`), qui choisit l'archétype.
// Miroir informatif du questionnaire webhook (QX51) — clés snake_case.
export const COMMERCIAL_CATEGORIES = [
  { value: 'hotel', label: 'Hôtel / Riad' },
  { value: 'restaurant', label: 'Restaurant / Café' },
  { value: 'commerce', label: 'Commerce / Supermarché' },
  { value: 'bureau', label: 'Bureau / Siège' },
  { value: 'sante', label: 'Santé (clinique / cabinet)' },
  { value: 'ecole', label: 'École privée' },
  { value: 'hammam', label: 'Hammam / Spa / Gym' },
  { value: 'boulangerie', label: 'Boulangerie' },
  { value: 'froid', label: 'Entrepôt froid' },
  { value: 'autre', label: 'Autre commerce' },
]

// Questions 2-4 par catégorie (recherche 2026-07-16). key = clé snake_case
// envoyée au moteur C&I dans `rythme.reponses_categorie` (jamais à plat dans
// etude_params, CIQ129) et acceptée par le webhook QX51. type =
// 'number' | 'bool' | 'select' (+ options).
export const COMMERCIAL_CATEGORY_QUESTIONS = {
  hotel: [
    { key: 'chambres', label: 'Nombre de chambres', type: 'number' },
    { key: 'occupation_pct', label: "Taux d'occupation annuel (%)", type: 'number' },
    { key: 'piscine', label: 'Piscine chauffée', type: 'bool' },
  ],
  restaurant: [
    { key: 'chambres_froides', label: 'Chambres froides', type: 'number' },
    {
      key: 'horaires', label: 'Horaires', type: 'select', options: [
        { value: 'midi', label: 'Midi' }, { value: 'soir', label: 'Soir' },
        { value: 'continu', label: 'Continu' },
      ],
    },
    {
      key: 'cuisson', label: 'Cuisson', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  commerce: [
    { key: 'surface_vente_m2', label: 'Surface de vente (m²)', type: 'number' },
    { key: 'chambres_froides', label: 'Meubles / chambres froids', type: 'number' },
  ],
  bureau: [
    { key: 'effectif', label: 'Effectif (postes)', type: 'number' },
    { key: 'clim', label: 'Climatisation centralisée', type: 'bool' },
  ],
  sante: [
    { key: 'lits', label: 'Nombre de lits', type: 'number' },
    { key: 'garde_nuit', label: 'Garde de nuit', type: 'bool' },
  ],
  ecole: [
    { key: 'effectif', label: 'Effectif (élèves)', type: 'number' },
    { key: 'internat', label: 'Internat', type: 'bool' },
    { key: 'fermeture_estivale', label: 'Fermeture estivale', type: 'bool' },
  ],
  hammam: [
    { key: 'surface_m2', label: 'Surface (m²)', type: 'number' },
    {
      key: 'chauffe', label: 'Chauffe eau', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  boulangerie: [
    {
      key: 'four', label: 'Four', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
    { key: 'cuisson_nocturne', label: 'Cuisson nocturne', type: 'bool' },
  ],
  froid: [
    { key: 'temperature_consigne', label: 'Température de consigne (°C)', type: 'number' },
    { key: 'volume_m3', label: 'Volume froid (m³)', type: 'number' },
    { key: 'saisonnalite_recolte', label: 'Pic saisonnier (récolte)', type: 'bool' },
  ],
  autre: [],
}

// ── Format monétaire (port exact de formatMoney) ─────────────────────────────
export function formatMoney(val) {
  if (val === null || val === undefined || isNaN(val)) return '0 MAD'
  return formatMAD(val, { decimals: 0 })
}

// ── Estimation des factures mensuelles depuis hiver/été ──────────────────────
export function interpolerFactures(hiver, ete) {
  if (!ete || ete <= 0) return Array(12).fill(hiver)
  const premiere = Array.from({ length: 7 }, (_, i) => hiver + (ete - hiver) / 6 * i)
  const seconde = Array.from({ length: 5 }, (_, i) => ete - (ete - hiver) / 4 * i)
  return [...premiere, ...seconde]
}

// Les mois affichés sont toujours arrondis à l'entier (renderMonthlyInputs)
export function estimerMois(hiver, ete) {
  return interpolerFactures(hiver, ete).map(v => Math.round(v))
}

// CIQ128 — la doctrine de paliers ÉCRAN (pas de 5 kWc, tranche de 900 MAD,
// besoin lu sur la facture, balayage au payback) est SUPPRIMÉE : le C&I est dimensionné par le moteur serveur (CIQ107-CIQ122,
// pas de 5 kWc et horizon marginal côté `moteur_ci/taille.py`), le résidentiel
// par le moteur horaire serveur (U3-MOTEUR).

// ── Métrés de câble (règle fondateur 18/08, câble DC révisé 19/08 — PVCBL) ──
// Câble de terre AC 6 mm² : 25 m de base + 15 m par palier de 5 kWc — soit 40 m
// pour 5 kWc et 55 m pour 10 kWc, les deux cotes données par le fondateur.
// Câble solaire DC 6 mm² : voir `metreCableDcParPaires` ci-dessous — la règle
// « 60 m par palier » est SUPERSEDÉE par la règle par PAIRE de MPPT (19/08).
export const CABLE_DC_M_PAR_PALIER = 60
export const CABLE_TERRE_M_BASE = 25
export const CABLE_TERRE_M_PAR_PALIER = 15

// ── PVCBL (fondateur 19/08/2026) — métrage câble DC PAR PAIRE de MPPT ───────
// Bug constaté : un devis auto avait chiffré un ROULEAU de 100 m (produit au
// conditionnement rouleau, pas au mètre) avec une quantité en MÈTRES (60) →
// 71 400 MAD d'aberration (« who said 100m??? i wanted cable DC 6mm2 per
// metre »). Deux corrections ORTHOGONALES :
//  1. le produit retenu doit être vendu AU MÈTRE — voir `pickCable` dans
//     `autoFillLines`, qui exclut désormais tout conditionnement rouleau/
//     touret (jamais un repli silencieux sur un autre conditionnement) ;
//  2. le MÉTRAGE suit les PAIRES de câbles qui descendent du toit (30 m rouge
//     + 30 m noir = 60 m par paire), pas le palier de 5 kWc. Le nombre de
//     paires = le nombre d'entrées MPPT RÉELLEMENT UTILISÉES par l'onduleur
//     retenu — un calcul qui vit dans le moteur électrique
//     (apps/ventes/solar_design.py::string_design, core/electrique/chaines.py,
//     PV34) et exige des données que la composition simple (kWc + nb de
//     panneaux, sans plan de toiture ni fiche technique complète) n'a pas à ce
//     stade (`specs_solaire` ne sert pas encore `n_mppt` au frontend).
//     `nbPaires` est donc un paramètre EXPLICITE : un appelant qui a déjà ce
//     calcul (ex. l'écran Conception électrique, une fois branché) le
//     transmet ; SANS lui, repli fondateur EXPLICITEMENT AUTORISÉ : 1 paire —
//     jamais un calcul deviné.
export function metreCableDcParPaires(nbPaires = 1) {
  const n = Math.max(1, Math.round(Number(nbPaires) || 0) || 1)
  return n * CABLE_DC_M_PAR_PALIER
}

/** Longueur de câble de terre AC (m) pour `paliers` blocs de 5 kWc. */
export function metreCableTerre(paliers) {
  const n = Math.max(1, Math.round(Number(paliers) || 0))
  return CABLE_TERRE_M_BASE + n * CABLE_TERRE_M_PAR_PALIER
}

// Taux d'autoconsommation par option — miroir pricing.py AUTOCONSO_SANS/AVEC.
// Utilisés UNIQUEMENT par le modèle « deux factures » (QF5) ; l'estimation
// historique ci-dessous continue d'utiliser dayUsagePct (comportement inchangé).
export const AUTOCONSO_SANS = 0.60
// ORDRE FONDATEUR (18/08) — le forfait « 85 % avec batterie » n'est PLUS le
// modèle : une batterie ne relève pas un taux, elle décale une quantité
// d'énergie RÉELLE égale à sa capacité, une fois par jour. AUTOCONSO_AVEC ne
// survit que comme REPLI documenté : devis explicitement « avec batterie »
// dont la capacité est inconnue (aucune ligne batterie chiffrable) — le seul
// cas où l'on n'a rien de réel à additionner. Dès qu'une capacité existe, le
// taux est DÉRIVÉ (autoconsoAvecRatio ci-dessous), jamais forfaitaire.
export const AUTOCONSO_AVEC = 0.85

// ── Modèle batterie ADDITIF (ordre fondateur 18/08) — MIROIR pricing.py ──────
// autoconsommé_avec = 60 % × production + capacité_kWh × 1 cycle/jour.
// PLAFONDS (honnêteté : on ne vend jamais de l'énergie qui n'existe pas) :
//   • jamais plus que la production (la batterie ne décale que l'existant) ;
//   • jamais plus que la consommation réelle quand elle est connue (QF5).
export const BATTERY_CYCLES_PER_DAY = 1
export const DAYS_PER_YEAR = 365
export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

/**
 * Taux d'autoconsommation EFFECTIF de l'option « avec batterie », DÉRIVÉ de la
 * capacité réellement chiffrée (miroir exact de pricing.autoconso_avec_ratio).
 *
 * @param productionAnnuelleKwh production annuelle (kWh/an)
 * @param batteryKwh capacité batterie totale du devis (kWh) — 0/inconnue → repli
 * @param base taux sans batterie (défaut AUTOCONSO_SANS)
 * @param fallback taux de repli quand aucune capacité n'est connue
 * @param consoAnnuelleKwh consommation réelle (kWh/an) quand elle est connue
 */
export function autoconsoAvecRatio(productionAnnuelleKwh, batteryKwh, {
  base = AUTOCONSO_SANS, fallback = AUTOCONSO_AVEC, consoAnnuelleKwh = null,
} = {}) {
  const prod = parseFloat(productionAnnuelleKwh) || 0
  const cap = parseFloat(batteryKwh) || 0
  const conso = parseFloat(consoAnnuelleKwh) || 0
  if (prod <= 0) return fallback
  let ratio = cap > 0
    ? (parseFloat(base) || 0) + (cap * BATTERY_CYCLES_PER_DAY * DAYS_PER_YEAR) / prod
    : fallback
  ratio = Math.min(1, ratio)                      // plafond production
  if (conso > 0) ratio = Math.min(ratio, conso / prod)  // plafond consommation
  return ratio
}

// ── QX39 — cashflow 25 ans honnête (MIROIR backend pricing.py) ───────────────
// Mêmes hypothèses documentées : dégradation panneau, tarif CONSTANT (aucune
// hausse supposée), rendement batterie, remplacement onduleur optionnel. Le payback = croisement
// du cumul à zéro. Écran, PDF et proposition web affichent le MÊME payback.
export const CASHFLOW_YEARS = 25
export const PANEL_DEGRADATION = 0.005
// ALIGNEMENT 18/08 — QRES54 (aucune hausse tarifaire supposée) n'avait été
// appliqué qu'au backend : l'écran promettait +2 %/an alors que le PDF et la
// page proposition écrivent « projection à tarif constant ». On dit VRAI des
// deux côtés — la constante reste exportée, à 0 (miroir pricing.py).
// Toute hausse réelle du tarif ne peut qu'améliorer le résultat du client.
export const TARIFF_ESCALATION = 0.0
export const BATTERY_ROUNDTRIP = 0.90
// Q1 (décision fondateur du 20/08/2026) — PROVISION DE REMPLACEMENT ONDULEUR :
// le principe mi-vie (année 12, IEA PVPS) est confirmé, mais le MONTANT n'est
// plus un pourcentage forfaitaire du CAPEX (l'ancien ≈ 8 % ne correspondait au
// prix d'AUCUN onduleur réel) — c'est le PRIX TTC RÉEL de la ligne onduleur du
// devis (`inverterReplaceCost`, résolu par `inverterCostFromLines`/`isAnyInverter`
// ci-dessous). Aucune ligne onduleur identifiable ⇒ AUCUNE provision — jamais
// un pourcentage de repli.
export const INVERTER_REPLACE_YEAR = 12

export function computeCashflowPayback(investment, economieAnnee1, {
  battery = false,
  // Z5 (ORDRE FONDATEUR, 20/08/2026) — PART de l'économie qui transite
  // RÉELLEMENT par la batterie (0..1). Le rendement aller-retour ne frappe QUE
  // elle, jamais le socle autoconsommé directement au fil du soleil (qui ne
  // subit aucune perte de charge/décharge). `null` (défaut) conserve le
  // forfait historique (0,90 sur 100 % de l'économie) pour un appelant direct
  // sans la décomposition sans/avec.
  batteryShare = null,
  // Q1 — prix TTC RÉEL de l'onduleur de cette option, retranché à
  // INVERTER_REPLACE_YEAR. `null`/0 ⇒ aucune provision.
  inverterReplaceCost = null,
  // QJR137 (miroir `pricing`) — rendement aller-retour PROUVÉ par la fiche
  // batterie quand le moteur horaire le publie, sinon l'hypothèse de référence.
  batteryRoundtrip = BATTERY_ROUNDTRIP,
} = {}) {
  const inv = parseFloat(investment) || 0
  const base = parseFloat(economieAnnee1) || 0
  if (base <= 0 || inv <= 0) {
    return { paybackYears: null, cumulative: [], netGain: 0, years: CASHFLOW_YEARS, jamaisRembourse: false }
  }
  // Z5 — facteur batterie EFFECTIF : la perte aller-retour ne frappe que la
  // part réellement stockée puis restituée. `batteryShare=null` → forfait
  // historique (0,90 sur tout) ; `0` → aucune perte ; `1` → identique au forfait.
  const rt = (parseFloat(batteryRoundtrip) > 0 && parseFloat(batteryRoundtrip) <= 1)
    ? parseFloat(batteryRoundtrip) : BATTERY_ROUNDTRIP
  let battFactor = 1
  if (battery) {
    if (batteryShare === null || batteryShare === undefined) {
      battFactor = rt
    } else {
      const part = Math.max(0, Math.min(1, parseFloat(batteryShare) || 0))
      battFactor = 1 - (1 - rt) * part
    }
  }
  const invCost = parseFloat(inverterReplaceCost) || 0
  const cumulative = []
  let cumul = -inv
  let payback = null
  let prev = -inv
  for (let y = 1; y <= CASHFLOW_YEARS; y++) {
    const prodFactor = (1 - PANEL_DEGRADATION) ** (y - 1)
    const tarifFactor = (1 + TARIFF_ESCALATION) ** (y - 1)
    let yearSaving = base * prodFactor * tarifFactor
    if (battery) yearSaving *= battFactor
    let yearCf = yearSaving
    if (INVERTER_REPLACE_YEAR && invCost > 0 && y === INVERTER_REPLACE_YEAR) {
      yearCf -= invCost
    }
    prev = cumul
    cumul += yearCf
    cumulative.push(Math.round(cumul))
    if (payback === null && cumul >= 0) {
      const span = cumul - prev
      const frac = span ? (0 - prev) / span : 0
      payback = Math.round(((y - 1) + frac) * 10) / 10
    }
  }
  // ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — miroir de `pricing` : la
  // sentinelle numérique reste (comparaisons), le drapeau pilote l'affichage.
  const jamaisRembourse = payback === null
  if (jamaisRembourse) payback = CASHFLOW_YEARS
  return { paybackYears: payback, cumulative, netGain: Math.round(cumul), years: CASHFLOW_YEARS, jamaisRembourse }
}

// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — le payback de l'écran quand l'étude
// horaire SERVEUR a répondu : la formule du MOTEUR (`pricing.calculate_savings_roi`
// → `compute_cashflow_payback`, cashflow 25 ans QX39 : dégradation, rendement
// batterie sur la seule part stockée, remplacement onduleur au prix réel),
// appliquée à l'économie servie par le serveur — jamais `coût ÷ économie`
// (écran 13,43 / 8,95 ans contre 8,2 / 5,5 au document).
// `annuel` = `etude.annuel` du serveur (taux d'autoconsommation, production,
// consommation) : la part batterie se dérive comme dans `pricing` (plafond
// sans ≤ conso/production, plancher avec ≥ sans). Rend
// `{ paybackYears, jamaisRembourse }`, ou `null` sans coût ni économie.
export function paybackMoteurHoraire(total, ecoAnnuelle, {
  annuel = null, rendementBatterie = null, stockage = false, inverterReplaceCost = null,
} = {}) {
  const t = parseFloat(total) || 0
  const eco = parseFloat(ecoAnnuelle) || 0
  if (!(t > 0) || !(eco > 0)) return null
  let part = 0
  if (stockage && annuel) {
    const prod = parseFloat(annuel.production_kwh) || 0
    const conso = parseFloat(annuel.consommation_kwh) || 0
    let sansEff = parseFloat(annuel.taux_autoconso_sans) || 0
    if (conso > 0 && prod > 0) sansEff = Math.min(sansEff, conso / prod)
    const avecEff = Math.max(parseFloat(annuel.taux_autoconso_avec) || 0, sansEff)
    part = avecEff > 0 ? Math.max(0, avecEff - sansEff) / avecEff : 0
  }
  const cf = computeCashflowPayback(t, eco, {
    battery: !!stockage, batteryShare: part, inverterReplaceCost,
    batteryRoundtrip: rendementBatterie ?? BATTERY_ROUNDTRIP,
  })
  return { paybackYears: cf.paybackYears, jamaisRembourse: !!cf.jamaisRembourse }
}

// ── Simulation ROI (port exact de /api/roi/calculate du simulateur) ──────────
// QF5 — quand une consommation annuelle RÉELLE + un distributeur connu sont
// fournis (`consoAnnuelleKwh`/`utility`, capturés par QF4), l'économie bascule
// sur le modèle « deux factures » par tranche (miroir EXACT du backend QF2) :
// l'écran affiche alors la MÊME économie que le PDF pour les mêmes entrées.
// Sans ces données, comportement HISTORIQUE inchangé (estimation production ×
// autoconsommation diurne × tarif) — jamais de régression pour un devis existant.
export function computeROI({
  kwp, factures, dayUsagePct, totalSans, totalAvec, batteryKwh, kwhPrice, efficiency,
  consoAnnuelleKwh, utility, productible,
  // Q1 (fondateur 20/08/2026) — lignes RÉELLES du devis, pour retrouver le
  // prix TTC de l'onduleur de chaque option (provision de remplacement à
  // l'année 12). Optionnel : sans lignes, aucune provision (jamais un
  // pourcentage de repli) — comportement inchangé pour un appelant qui ne les
  // fournit pas (encore).
  lines = [],
}) {
  // Tarif ONEE et rendement éditables (Paramètres → Avancé) ; sans valeur, on
  // garde EXACTEMENT les constantes historiques (parité simulateur garantie).
  const PRICE = (Number.isFinite(Number(kwhPrice)) && Number(kwhPrice) > 0) ? Number(kwhPrice) : KWH_PRICE
  const EFF = (Number.isFinite(Number(efficiency)) && Number(efficiency) > 0) ? Number(efficiency) : EFFICIENCY
  // QX38 — productible CANONIQUE (kWh/kWc/an) : quand il est fourni (PVGIS par
  // ville, source unique partagée avec le PDF/web), la production annuelle vaut
  // productible × kwp, répartie par la FORME saisonnière GHI (le graphe mensuel
  // garde sa saisonnalité). Sans productible, comportement HISTORIQUE inchangé
  // (GHI[i] × kwp × rendement) — jamais de régression pour un devis existant.
  const PROD = Number(productible)
  const useProductible = Number.isFinite(PROD) && PROD > 0
  const GHI_SUM = GHI.reduce((s, v) => s + v, 0)
  let bills = [...(factures ?? [])]
  if (bills.length < 12) {
    const last = bills.length ? bills[bills.length - 1] : 500
    bills = bills.concat(Array(12 - bills.length).fill(last))
  }
  bills = bills.slice(0, 12)

  const dayPct = (dayUsagePct ?? 50) / 100
  const monthlyDetail = []
  const ecoSansMonthly = []
  const ecoAvecMonthly = []
  let productionAnnuelle = 0
  let batteryShiftAnnuel = 0   // kWh réellement décalés par la batterie

  for (let i = 0; i < 12; i++) {
    const prodKwh = useProductible
      // Productible stocké (net à 14 %) ramené aux 20 % de pertes TOTALES du
      // fondateur (PRODUCTIBLE_NET_FACTOR), puis réparti par la forme GHI.
      ? (PROD * PRODUCTIBLE_NET_FACTOR * kwp) * (GHI[i] / GHI_SUM)
      : GHI[i] * kwp * EFF   // chemin historique : EFFICIENCY = 0,8 EST déjà 20 %
    productionAnnuelle += prodKwh
    const selfConsumed = prodKwh * dayPct
    const ecoSans = selfConsumed * PRICE
    // ORDRE FONDATEUR (18/08) — apport batterie en ÉNERGIE, plus le forfait
    // 60 MAD/kWh/mois : capacité × 1 cycle/jour × jours du mois, plafonné par
    // ce qu'il reste de production ce mois-là (on ne stocke que l'existant),
    // puis valorisé au tarif — même dérivation du taux que pricing.py,
    // VERROUILLÉE par les tests jumeaux solar.batterie/test_battery_autoconso.
    const stockable = Math.max(0, prodKwh - selfConsumed)
    const batteryShift = Math.min(
      Math.max(0, parseFloat(batteryKwh) || 0) * BATTERY_CYCLES_PER_DAY * DAYS_IN_MONTH[i],
      stockable)
    batteryShiftAnnuel += batteryShift
    const ecoAvec = ecoSans + batteryShift * PRICE
    ecoSansMonthly.push(ecoSans)
    ecoAvecMonthly.push(ecoAvec)
    monthlyDetail.push({
      month: CHART_MONTHS[i],
      facture: bills[i],
      eco_sans: ecoSans,
      eco_avec: ecoAvec,
    })
  }

  let ecoAnnuelleSans = ecoSansMonthly.reduce((s, v) => s + v, 0)
  let ecoAnnuelleAvec = ecoAvecMonthly.reduce((s, v) => s + v, 0)

  // QF2/QF5 — modèle « deux factures » (réel, par tranche) quand consommation
  // ET barème sont disponibles. Remplace l'estimation ci-dessus par l'économie
  // réelle facture_sans − facture_avec (jamais les deux mélangés).
  // PARITÉ ÉCRAN/PDF AU DIRHAM : le moteur PDF arrondit la production annuelle
  // à l'entier AVANT le modèle par tranches (pricing.calculate_savings_roi).
  // L'écran fait donc pareil — sinon les deux tombent de part et d'autre d'un
  // arrondi de tranche et affichent 1 MAD d'écart pour les mêmes entrées.
  const productionCanonique = Math.round(productionAnnuelle)
  // Le taux « avec batterie » est DÉRIVÉ de la capacité réelle du devis
  // (ordre fondateur 18/08) : 60 % + capacité × 1 cycle/jour, plafonné par la
  // production ET par la consommation. Sans capacité connue → repli documenté.
  const autoconsoAvec = autoconsoAvecRatio(productionCanonique, batteryKwh, {
    consoAnnuelleKwh,
  })
  // Taux EFFECTIVEMENT appliqués (pour affichage/transparence) : dans le
  // chemin « estimation » la part sans batterie est la part diurne saisie
  // (dayUsagePct) et la part avec batterie ajoute les kWh réellement décalés.
  let autoconsoSansEff = dayPct
  let autoconsoAvecEff = productionAnnuelle > 0
    ? Math.min(1, dayPct + batteryShiftAnnuel / productionAnnuelle)
    : dayPct
  // ── PLAFOND CONSOMMATION DU CÔTÉ « SANS » — MIROIR EXACT de
  // pricing.calculate_savings_roi (correctif 18/08) ────────────────────────
  // Le côté AVEC batterie est déjà borné par la consommation réelle
  // (`autoconsoAvecRatio`) ; le côté SANS, lui, était un pourcentage de la
  // seule PRODUCTION, borné par rien. Sur une petite conso face à une grosse
  // production, l'option BATTERIE « économisait » donc MOINS que l'option
  // sans batterie (8 kWc / 5 000 kWh/an / 10 kWh : 6 644 MAD sans contre
  // 6 000 MAD avec côté PDF). On borne les DEUX côtés aux kWh RÉELLEMENT
  // consommés, puis on tient l'invariant « avec ≥ sans ».
  //   sans = min(part_diurne × production, conso)
  //   avec = max(min(part_diurne × production + décalage_batterie, conso), sans)
  // Les séries mensuelles sont mises à l'échelle du MÊME facteur, pour que
  // leur somme reste l'économie annuelle affichée.
  const consoPlafond = parseFloat(consoAnnuelleKwh) || 0
  if (consoPlafond > 0 && productionAnnuelle > 0) {
    const kwhSansBrut = productionAnnuelle * dayPct
    const kwhAvecBrut = kwhSansBrut + batteryShiftAnnuel
    const kwhSans = Math.min(kwhSansBrut, consoPlafond)
    const kwhAvec = Math.max(Math.min(kwhAvecBrut, consoPlafond), kwhSans)
    const fSans = kwhSansBrut > 0 ? kwhSans / kwhSansBrut : 1
    const fAvec = kwhAvecBrut > 0 ? kwhAvec / kwhAvecBrut : 1
    if (fSans < 1 || fAvec < 1) {
      for (let i = 0; i < 12; i++) {
        ecoSansMonthly[i] *= fSans
        ecoAvecMonthly[i] *= fAvec
        monthlyDetail[i].eco_sans = ecoSansMonthly[i]
        monthlyDetail[i].eco_avec = ecoAvecMonthly[i]
      }
      ecoAnnuelleSans = ecoSansMonthly.reduce((s, v) => s + v, 0)
      ecoAnnuelleAvec = ecoAvecMonthly.reduce((s, v) => s + v, 0)
    }
    autoconsoSansEff = kwhSans / productionAnnuelle
    autoconsoAvecEff = kwhAvec / productionAnnuelle
  }
  // Modèle « factures » : même plafond, même plancher (miroir pricing.py, qui
  // passe `autoconso_sans_eff` à `two_bills_savings` et planchéise le taux
  // AVEC). Sur les factures c'est un NO-OP de VALEUR — `twoBillsSavings` borne
  // déjà les kWh autoconsommés à la conso — mais le taux AFFICHÉ devient
  // honnête et l'invariant « avec ≥ sans » est verrouillé des deux côtés.
  const autoconsoSansPlaf = (consoPlafond > 0 && productionCanonique > 0)
    ? Math.min(AUTOCONSO_SANS, consoPlafond / productionCanonique)
    : AUTOCONSO_SANS
  const autoconsoAvecPlanche = Math.max(autoconsoAvec, autoconsoSansPlaf)
  let savingsModel = 'estimation'
  let factureSans = null, factureAvecSans = null, factureAvecAvec = null
  if (productionAnnuelle > 0 && consoAnnuelleKwh > 0 && utility) {
    const tbSans = twoBillsSavings(productionCanonique, consoAnnuelleKwh, autoconsoSansPlaf, utility)
    const tbAvec = twoBillsSavings(productionCanonique, consoAnnuelleKwh, autoconsoAvecPlanche, utility)
    if (tbSans && tbAvec) {
      savingsModel = 'factures'
      autoconsoSansEff = autoconsoSansPlaf
      autoconsoAvecEff = autoconsoAvecPlanche
      ecoAnnuelleSans = tbSans.economie
      ecoAnnuelleAvec = tbAvec.economie
      factureSans = tbSans.factureSans
      factureAvecSans = tbSans.factureAvec
      factureAvecAvec = tbAvec.factureAvec
    }
  }

  // Q1 — prix TTC RÉEL des lignes onduleur de CHAQUE option (miroir builder.py
  // sans_items/avec_items : « sans » exclut batterie + onduleur hybride,
  // « avec » exclut l'onduleur réseau — mêmes filtres que optionTotalsTTC).
  // L-2OPT (fondateur 24/08) — `variante` ('' commun | 'sans' | 'avec', posée
  // par `fusionnerVariantes`) écarte D'ABORD la ligne taguée pour l'AUTRE
  // option ; F14 (26/08) — une ligne DÉCLARÉE ('sans'/'avec') TRANCHE SEULE
  // et NE repasse PLUS par le filtre mot-clé (avant F14, une batterie taguée
  // 'sans' était encore retirée du panier « sans » par le second filtre —
  // contradiction avec builder.py où la déclaration prime). Seule une ligne
  // SANS `variante` (tout devis hors « Les deux ») retombe sur les mots-clés,
  // exactement comme avant.
  const linesSans = lines.filter(l => appartientAuPanierSans(l))
  const linesAvec = lines.filter(l => appartientAuPanierAvec(l))
  const inverterCostSans = inverterCostFromLines(linesSans)
  const inverterCostAvec = inverterCostFromLines(linesAvec)

  // M9 — l'option 2 porte-t-elle RÉELLEMENT du stockage ? Dérivé des VRAIES
  // lignes (`batteryKwh` = `batteryKwhFromLines(...)` chez l'appelant), jamais
  // codé en dur : un devis sans batterie ne subit plus la perte d'un
  // équipement absent.
  const stockagePresent = (parseFloat(batteryKwh) || 0) > 0

  // Z5 — PART de l'économie qui transite RÉELLEMENT par la batterie : le
  // socle autoconsommé directement (autoconsoSansEff) n'entre jamais dans la
  // batterie ; seul le supplément apporté par la capacité batterie
  // (autoconsoAvecEff − autoconsoSansEff) est stocké puis restitué.
  let battPart = 0
  if (autoconsoAvecEff > 0) {
    battPart = Math.max(0, autoconsoAvecEff - autoconsoSansEff) / autoconsoAvecEff
  }

  // QX39 — payback par croisement du cumul du cashflow 25 ans (miroir backend),
  // pas un ratio année-1 : écran/PDF/proposition affichent le MÊME payback.
  const cfSans = computeCashflowPayback(totalSans, ecoAnnuelleSans, {
    inverterReplaceCost: inverterCostSans,
  })
  const cfAvec = computeCashflowPayback(totalAvec, ecoAnnuelleAvec, {
    battery: stockagePresent, batteryShare: battPart, inverterReplaceCost: inverterCostAvec,
  })
  const paybackSans = (ecoAnnuelleSans > 0 && totalSans > 0) ? cfSans.paybackYears : null
  const paybackAvec = (ecoAnnuelleAvec > 0 && totalAvec > 0) ? cfAvec.paybackYears : null

  return {
    production_annuelle_kwh: Math.round(productionAnnuelle * 10) / 10,
    monthly_detail: monthlyDetail,
    eco_annuelle_sans: ecoAnnuelleSans,
    eco_annuelle_avec: ecoAnnuelleAvec,
    eco_sans_monthly: ecoSansMonthly,
    eco_avec_monthly: ecoAvecMonthly,
    payback_sans: paybackSans,
    payback_avec: paybackAvec,
    // ERR-QAC-PAYBACK-JAMAIS-REMBOURSE-25-ANS — mêmes drapeaux que le PDF.
    payback_sans_jamais: paybackSans !== null && !!cfSans.jamaisRembourse,
    payback_avec_jamais: paybackAvec !== null && !!cfAvec.jamaisRembourse,
    // QX39 — cumul cashflow 25 ans + gain net (mêmes clés que le PDF).
    cashflow_sans: cfSans.cumulative,
    cashflow_avec: cfAvec.cumulative,
    net_gain_sans: cfSans.netGain,
    net_gain_avec: cfAvec.netGain,
    // QF5 — transparence : le PDF (builder.py) porte les mêmes clés
    // (savings_model/facture_sans/facture_avec_s/facture_avec_a).
    savings_model: savingsModel,
    facture_sans: factureSans,
    facture_avec_sans: factureAvecSans,
    facture_avec_avec: factureAvecAvec,
    // Transparence (mêmes clés que le PDF) : taux d'autoconsommation retenus.
    // `autoconso_avec` est DÉRIVÉ de la capacité batterie, jamais forfaitaire.
    autoconso_sans: autoconsoSansEff,
    autoconso_avec: autoconsoAvecEff,
    // kWh annuels réellement décalés par la batterie (chemin estimation).
    battery_shift_kwh: Math.round(batteryShiftAnnuel),
  }
}

// ── Classification des lignes/produits (mêmes mots-clés que le moteur PDF) ───
// STKCAT15 — exportée telle quelle (aucun nouveau module) : la recherche
// transverse du catalogue (stock/catalogue.js) la réutilise pour normaliser
// accents/casse des deux côtés (requête ET botte de foin produit), au lieu
// de dupliquer une seconde normalisation qui pourrait diverger.
export const _norm = (s) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const isBattery = (d) => _norm(d).includes('batterie')
export const isHybridInverter = (d) => _norm(d).includes('onduleur') && _norm(d).includes('hybride')
// OFFGRID (fondateur, ajout produit onduleur hors réseau) — MÊME CONTRAT que
// le backend (apps/ventes/services.py côté serveur) : mot pour mot les mêmes
// mots-clés, jamais un seul divergent. « Onduleur hors réseau » contient le
// sous-mot « reseau » : sans l'exclusion NOT hybride ci-dessous et la garde
// symétrique dans `isReseauInverter`, cette désignation était classée
// (à tort) comme onduleur RÉSEAU — la ligne partait au panier « sans »,
// jamais composée, jamais reconnue en auto-remplissage.
const OFFGRID_KEYWORDS = ['off-grid', 'off grid', 'offgrid', 'hors reseau', 'autonome']
const _isOffgridDesignation = (n) => OFFGRID_KEYWORDS.some(k => n.includes(k))
// Incident fondateur 01/09 (round 2) — les VRAIS produits catalogue s'appellent
// « Deye off-Grid 6kw », SANS le mot « onduleur » : le prédicat strict
// ci-dessus (exigeant « onduleur ») les rendait invisibles (0 onduleur
// off-grid détecté, auto-remplissage en échec permanent). Élargi SANS perdre
// la précision : un nom off-grid qui ne dit pas « onduleur » n'est retenu que
// s'il n'appartient à AUCUNE AUTRE FAMILLE de produit — sinon (« Batterie
// off-grid », « Kit solaire off-grid », « Câble off-grid ») ce n'est
// manifestement pas l'onduleur lui-même.
const OTHER_FAMILY_KEYWORDS = [
  'batterie', 'panneau', 'panneaux', 'module', 'pompe', 'variateur',
  'structure', 'cable', 'coffret', 'disjoncteur', 'differentiel',
  'parafoudre', 'compteur', 'smart meter', 'wifi', 'kit', 'chargeur',
]
export const isOffgridInverter = (d) => {
  const n = _norm(d)
  if (!_isOffgridDesignation(n) || n.includes('hybride')) return false
  if (n.includes('onduleur')) return true
  return !OTHER_FAMILY_KEYWORDS.some(k => n.includes(k))
}
export const isReseauInverter = (d) => {
  const n = _norm(d)
  return n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))
    && !_isOffgridDesignation(n)
}
// Q1 (fondateur 20/08/2026) — TOUT onduleur, hybride/réseau/non classé (ex.
// micro-onduleur) : miroir exact de builder.py `_is_inverter` (« onduleur »
// suffit). Sert à repérer la ligne dont le prix réel provisionne le
// remplacement à l'année 12 — jamais un forfait sur l'investissement.
export const isAnyInverter = (d) => _norm(d).includes('onduleur')

// ── QJR92a (29/08/2026) — DÉTECTION PANNEAU ÉLARGIE CÔTÉ ÉCRAN ──────────────
// Le seul mot « panneau » rejetait les désignations que les vendeurs écrivent
// vraiment (« Module PV 550 W », « Canadian Solar TOPHiKu7 710 Wc ») : l'écran
// comptait alors 0 panneau et REFUSAIT l'enregistrement d'un devis dont la
// seule ligne panneau s'appelle ainsi, pendant que le PDF la classait
// correctement. La table de référence est la fixture de contrat
// `apps/ventes/contract_samples/classification_lignes.json` (QJR2), et le test
// de parité QJR91 fait tourner ces prédicats sur chacun de ses cas.
// Les marques ne suffisent JAMAIS seules : Canadian Solar, Huawei et consorts
// vendent aussi des onduleurs — il faut un watt lisible en plus.
const PANEL_MODULE_QUALIFIERS = ['pv', 'photovolta', 'solaire', 'solar']
const PANEL_BRANDS = [
  'canadian solar', 'canadien solar', 'jinko', 'longi', 'trina',
  'ja solar', 'risen', 'sunpower', 'qcells', 'q cells', 'astronergy',
  'znshine',
]
export const isPanel = (d, produitNom = '') => {
  const blob = _norm(`${d ?? ''} ${produitNom ?? ''}`)
  if (blob.includes('panneau')) return true
  // Exclusions d'abord : un onduleur / une batterie / un accessoire n'est
  // jamais un panneau, quelle que soit la marque écrite dessus.
  if (blob.includes('onduleur') || blob.includes('batterie')
      || blob.includes('smart meter') || blob.includes('wifi')
      || blob.includes('dongle')) return false
  if (blob.includes('module')
      && PANEL_MODULE_QUALIFIERS.some(q => blob.includes(q))) return true
  // Marque de panneau ET puissance lisible : sans watt, une marque seule reste
  // ambiguë — on préfère l'omission à un faux positif.
  return PANEL_BRANDS.some(b => blob.includes(b)) && WATT_RE.test(blob)
}

// F14 (26/08/2026) — panier « sans »/« avec » d'UNE ligne, MIROIR EXACT du
// moteur PDF canonique (quote_engine/builder.py `_repartir_options`,
// ligne 499-541) et de son jumeau serveur (`apps/ventes/utils/options.py`
// `_garder_dans_sans`/`_garder_dans_avec`) : une ligne DÉCLARÉE
// (`variante === 'sans'`/`'avec'`) TRANCHE SEULE et ne repasse JAMAIS par le
// filtre mot-clé — avant ce correctif, une batterie taguée 'sans' était
// encore retirée du panier « sans » par un second filtre mot-clé, alors que
// le PDF la facturait dans ce panier (F14 : écran et PDF divergeaient). Une
// ligne SANS `variante` ('' — tout devis hors « Les deux ») retombe sur les
// mots-clés, mot pour mot comme avant.
export function appartientAuPanierSans(l) {
  const v = l?.variante
  if (v === 'avec') return false
  if (v === 'sans') return true
  return !isBattery(l?.designation) && !isHybridInverter(l?.designation)
    && !isOffgridInverter(l?.designation)
}
export function appartientAuPanierAvec(l) {
  const v = l?.variante
  if (v === 'sans') return false
  if (v === 'avec') return true
  return !isReseauInverter(l?.designation)
}

// Q1 — prix TTC RÉEL des lignes onduleur d'une option, ou `null` si aucune
// identifiable. Miroir exact de builder.py `_cout_onduleur` : Σ qty × prix
// unitaire TTC des lignes onduleur — jamais un pourcentage de repli.
export function inverterCostFromLines(lines) {
  let total = 0
  for (const l of lines || []) {
    if (!isAnyInverter(l.designation)) continue
    const qty = parseFloat(l.quantite) || 0
    const pu = parseFloat(l.prix_unit_ttc) || 0
    if (qty > 0 && pu > 0) total += qty * pu
  }
  return total > 0 ? Math.round(total * 100) / 100 : null
}

// ── PVOND — CONTRAT ONDULEUR & garde batterie PILOTÉ PAR LA DONNÉE ──────────
//
// MIROIR EXACT du backend (`apps/ventes/services.py` :
// `_batterie_compatible` / `_pick_batterie`, et le contrat lui-même dans
// `apps/stock/selectors.py`). Les deux côtés lisent la MÊME donnée, servie par
// l'API dans `produit.specs_solaire` :
//
//   { famille, plage_batterie_v: [min, max] | null, v_nominal, manquantes[] }
//
// Ce qui change par rapport au garde d'hier : une batterie ne s'accroche plus
// à un onduleur parce que son NOM ne dit pas « haute tension », mais parce que
// sa TENSION NOMINALE tombe dans la PLAGE BATTERIE que l'onduleur déclare.
// Le repli mot-clé reste EN PLACE et n'est pas un vestige : dès qu'une des deux
// données manque (catalogue ancien, produit saisi à la main, fixture de test),
// on retombe MOT POUR MOT sur le comportement PVG4 — jamais de régression
// silencieuse.

// Repli PVG4 : une batterie dont le nom dit « haute tension » n'est jamais
// auto-choisie pour un kit résidentiel basse tension.
// MIROIR EXACT de `_is_battery_basse_tension` (apps/ventes/services.py) : le
// prédicat Python exige AUSSI le mot « batterie » dans le nom. Le tronquer
// faisait de `batterieCompatible` — fonction EXPORTÉE, donc appelable hors du
// vivier pré-classé — une fonction qui ne se comporte pas comme sa jumelle.
const _batterieBasseTensionParMotCle = (p) => {
  const n = _norm(p?.nom)
  return n.includes('batterie') && !n.includes('haute tension')
}

// Fenêtre de tension batterie déclarée par un onduleur :
//   [min, max] → fenêtre réelle ; [0, 0] → « aucune batterie » (réseau) ;
//   null      → non déclarée (l'appelant retombe sur le mot-clé).
//
// RÈGLE CORRIGÉE (ordre fondateur 18/08/2026) — MIROIR EXACT de
// `stock.selectors.plage_batterie_onduleur` : un onduleur RÉSEAU (string
// on-grid) n'a PAS de port batterie. Rien de déclaré sur lui n'est pas un trou,
// c'est le cas nominal : sa FAMILLE vaut déclaration « aucune » ⇒ [0, 0].
// Le backend sert déjà cette valeur dans `specs_solaire.plage_batterie_v` ; ce
// repli local couvre le catalogue servi SANS bloc `specs_solaire` (produit
// saisi à la main, fixture) — sans lui, le mot-clé reprenait la main et pouvait
// accrocher une batterie à un onduleur réseau.
//
// L'ORDRE des deux mots-clés est signifiant et strictement celui de
// `stock.selectors.famille_onduleur` / `ventes.services.classer_produit` :
// « hybride » l'emporte sur « réseau », donc un « onduleur hybride injection
// réseau » reste un HYBRIDE (et sa plage reste EXIGÉE).
const _estOnduleurReseau = (nom) => isReseauInverter(nom) && !isHybridInverter(nom)

export function plageBatterieOnduleur(produit) {
  const plage = produit?.specs_solaire?.plage_batterie_v
  const replisReseau = () => (_estOnduleurReseau(produit?.nom) ? [0, 0] : null)
  if (!Array.isArray(plage) || plage.length !== 2) return replisReseau()
  const bas = Number(plage[0]); const haut = Number(plage[1])
  if (!Number.isFinite(bas) || !Number.isFinite(haut)) return replisReseau()
  return bas <= haut ? [bas, haut] : [haut, bas]
}

// La batterie entre-t-elle dans la plage de l'onduleur ? (miroir exact de
// `_batterie_compatible` côté backend, replis compris).
//
// RÈGLE CORRIGÉE (fondateur 2026-08-18) : le repli mot-clé ne s'applique QUE
// lorsque L'ONDULEUR ne déclare aucune plage. Dès qu'une plage existe, une
// candidate sans tension nominale — ou avec une tension nulle/illisible, donc
// une donnée INVALIDE — est EXCLUE. L'ancien repli acceptait, sous un onduleur
// 160-700 V, des batteries 48 V et plomb-gel 12 V sans aucune fiche technique,
// tout en écartant celles qui étaient correctement documentées : le garde-fou
// produisait exactement la composition qu'il devait empêcher.
export function batterieCompatible(batterie, plage) {
  if (!Array.isArray(plage)) return _batterieBasseTensionParMotCle(batterie)
  const [vMin, vMax] = plage
  if (!(vMax > 0)) return false        // onduleur réseau : aucune batterie
  const tension = Number(batterie?.specs_solaire?.v_nominal)
  // Plage EXIGÉE + tension inconnue/invalide ⇒ exclue (jamais le mot-clé).
  if (!Number.isFinite(tension) || tension <= 0) return false
  return tension >= vMin && tension <= vMax
}

// VERROU DE COMPLÉTUDE — les variables du contrat qui manquent à cet onduleur
// (liste vide = complet). Même patron que « prix à renseigner » : un onduleur
// incomplet est EXCLU de l'auto-composition et affiché grisé avec son motif,
// mais reste sélectionnable à la main.
//
// LA LISTE EST CALCULÉE PAR LE BACKEND (`stock.selectors.onduleur_specs_
// manquantes`, servie dans `specs_solaire.manquantes`) : c'est la source
// UNIQUE de la règle, donc les deux moitiés ne peuvent pas diverger. Depuis
// l'ordre fondateur du 18/08/2026 elle applique le contrat CONDITIONNEL —
// la « plage de tension batterie (V) » est réclamée aux onduleurs HYBRIDES
// (et aux familles indéterminées), jamais aux onduleurs RÉSEAU qui n'ont pas
// de port batterie. Un hybride sans plage reste écarté ET nommé.
export function onduleurSpecsManquantes(produit) {
  const manquantes = produit?.specs_solaire?.manquantes
  return Array.isArray(manquantes) ? manquantes : []
}

// Défauts TVA (réforme : 10 % panneaux PV, 20 % le reste).
export const TVA_PANNEAUX_DEFAUT = 10
export const TVA_STANDARD_DEFAUT = 20

// Taux TVA attendu d'après la désignation (réforme : 10 % panneaux PV, 20 % le
// reste). Sert UNIQUEMENT à signaler une incohérence à l'écran — jamais à
// recaler la valeur tapée (la frappe reste souveraine).
// DC4 — un objet {tvaPanneaux, tvaStandard} (repères société, Paramètres) peut
// surcharger les défauts ; sans lui, comportement historique inchangé.
export function expectedTvaForDesignation(designation, tvaConfig) {
  const panneaux = Number(tvaConfig?.tvaPanneaux) > 0
    ? Number(tvaConfig.tvaPanneaux) : TVA_PANNEAUX_DEFAUT
  const standard = Number(tvaConfig?.tvaStandard) > 0
    ? Number(tvaConfig.tvaStandard) : TVA_STANDARD_DEFAUT
  return isPanel(designation) ? panneaux : standard
}

// ── U1 (fondateur 20/08/2026) — LE COMPTE DE PANNEAUX EST UN PLAFOND ────────
// « 7 panneaux pour 5 kW : ça a TOUJOURS été 8 panneaux par 5 kW ». L'arrondi
// AU PLUS PROCHE (`Math.round`) sortait 7 panneaux pour 5 kWc en 710 Wc
// (round(7,042) = 7) : l'installation livrée était SOUS la puissance vendue.
// La règle est le PLAFOND : on ne descend jamais sous la cible annoncée.
//
// ÉPSILON — un compte de panneaux fait ALLER-RETOUR par le kWc
// (`kwp = nb * 710 / 1000`, puis re-dérivation), et 8 × 710 / 1000 × 1000 / 710
// vaut 8.000000000000002 en flottant : sans garde, le plafond ajouterait un
// 9ᵉ panneau fantôme à chaque aller-retour. La tolérance ramène un « à peine
// au-dessus d'un entier » sur cet entier ; elle ne peut PAS masquer un vrai
// besoin partiel (7,042 reste bien au-dessus de 7).
export const PANNEAUX_CEIL_EPS = 1e-9

export function plafondPanneaux(valeur) {
  const v = Number(valeur)
  if (!Number.isFinite(v) || v <= 0) return 0
  return Math.ceil(v - PANNEAUX_CEIL_EPS)
}

// Nombre de panneaux pour une taille cible (kWc) à la puissance panneau donnée.
// Utilisé pour préremplir depuis lead.taille_souhaitee_kwc. Au moins 1 panneau.
// QJR576 — LE wattage panneau par défaut (référence du simulateur), une
// seule constante au lieu de « 710 » recopié à chaque site.
export const PANEL_W_DEFAUT = 710

// QJR576 — inverse EXACT de `panneauxPourKwc` : kWc = n × W / 1000 (aucun
// arrondi ici — l'affichage arrondit, jamais la conversion). Compte ou
// wattage illisible → 0.
export function kwcPourPanneaux(nbPanneaux, panelW = PANEL_W_DEFAUT) {
  const n = parseFloat(nbPanneaux) || 0
  const w = parseFloat(panelW) || 0
  if (!(n > 0) || !(w > 0)) return 0
  return n * w / 1000
}

export function panneauxPourKwc(kwc, panelW = PANEL_W_DEFAUT) {
  const k = parseFloat(kwc) || 0
  const w = parseFloat(panelW) || PANEL_W_DEFAUT
  if (!(k > 0) || !(w > 0)) return 0
  return Math.max(1, plafondPanneaux(k * 1000 / w))
}

const WATT_RE = /(\d{3,4})\s*(?:wc|w)\b/i
const KW_RE = /(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b/i
const KWH_RE = /(\d+(?:[.,]\d+)?)\s*kwh\b/i

export function parseWatt(text) {
  const m = WATT_RE.exec(text || '')
  return m ? parseInt(m[1], 10) : null
}
export function parseKw(text) {
  // " 5 kWh" matcherait kW — exclure les kWh d'abord
  const cleaned = (text || '').replace(KWH_RE, ' ')
  const m = KW_RE.exec(cleaned)
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
export function parseKwh(text) {
  const m = KWH_RE.exec(text || '')
  return m ? parseFloat(m[1].replace(',', '.')) : null
}
// Phase depuis le nom produit ; défaut Monophase comme le catalogue simulateur
export function parsePhaseIsTri(text) {
  return /tri\s*phas/i.test(text || '')
}

export function classifyProduct(nom) {
  const n = _norm(nom)
  if (!n) return null
  if (n.includes('onduleur') && n.includes('hybride')) return 'onduleur_hybride'
  // Hors réseau (site isolé) — AVANT le test réseau/injection ci-dessous :
  // « onduleur hors réseau » contient le sous-mot « réseau », il faut donc le
  // détourner vers cette famille avant que le test suivant ne le happe.
  if (isOffgridInverter(n)) return 'onduleur_offgrid'
  // mêmes mots-clés que le moteur PDF : un onduleur sans « réseau/injection »
  // (ex. micro-onduleur) n'est pas classé et reste sélectionnable à la main
  if (n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))) {
    return 'onduleur_reseau'
  }
  // STKCAT22 (paire indissociable avec classer_produit côté serveur) — la
  // reconnaissance élargie isPanel (panneau, module + qualifiant PV, marque +
  // wattage) remplace le seul mot « panneau ».
  if (isPanel(nom)) return 'panneau'
  if (n.includes('batterie')) return 'batterie'
  if (n.includes('structure')) return 'structure'
  if (n.includes('socle')) return 'socle'
  // Câbles (règle fondateur 18/08) : le câble de TERRE se distingue du câble
  // solaire DC par son mot-clé, sinon tout « câble » est un câble solaire DC.
  if (n.includes('cable') && (n.includes('terre') || n.includes('mise a la terre'))) return 'cable_terre'
  if (n.includes('cable')) return 'cable_dc'
  if (n.includes('smart meter')) return 'smart_meter'
  if (n.includes('wifi') || n.includes('dongle')) return 'wifi_dongle'
  if (n.includes('accessoire')) return 'accessoires'
  if (n.includes('tableau')) return 'tableau'
  if (n.includes('suivi')) return 'suivi'
  if (n.includes('installation')) return 'installation'
  if (n.includes('transport')) return 'transport'
  return null
}

// Prix TTC affiché depuis le prix de vente HT du stock.
// DC6 — le taux 20 n'est qu'un DÉFAUT de repli ; le taux réel (10 % panneaux,
// 20 % le reste, ou le taux standard édité de la société) est toujours passé
// par l'appelant via tauxTva.
// AGR216 — un taux 0 % saisi RESTE 0 % : seuls null / '' / NaN retombent sur le
// défaut (0 est « faux » en JS, `|| 20` le réécrivait en 20).
export function tauxTvaOuDefaut(taux, defaut = TVA_STANDARD_DEFAUT) {
  const t = parseFloat(taux)
  return Number.isFinite(t) ? t : defaut
}

export function ttcFromHt(prixVenteHt, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + tauxTvaOuDefaut(tauxTva) / 100
  return Math.round((parseFloat(prixVenteHt) || 0) * factor)
}

// ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — TTC unitaire AU CENTIME d'un prix HT
// DÉJÀ PERSISTÉ (réouverture `?edit=`). `ttcFromHt` arrondit au dirham — juste
// pour un prix catalogue, faux pour un prix enregistré : l'erreur (≤ 0,5 MAD
// par unité) était multipliée par la quantité (36 828 à l'écran contre
// 36 873,11 au devis) puis PERSISTÉE au ré-enregistrement. Au centime,
// `htFromTtc` retrouve exactement le HT d'origine (erreur < 0,005 ÷ (1 + t)).
export function ttcExactFromHt(prixHt, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + tauxTvaOuDefaut(tauxTva) / 100
  return Math.round((parseFloat(prixHt) || 0) * factor * 100) / 100
}

// Taux TVA d'un produit (réforme 2024–2026 : 10 % panneaux PV, 20 % le reste).
// DC7 — `Produit.tva` est la source AUTORITAIRE par ligne ; on la prend telle
// quelle quand elle est renseignée. DC6 — le repli n'est plus 20 en dur : il
// suit le taux standard de la société (tvaStandard, Paramètres), défaut 20.
export function tauxTvaOf(produit, tvaStandard) {
  const t = parseFloat(produit?.tva)
  if (Number.isFinite(t) && t >= 0) return t
  const std = Number(tvaStandard) > 0 ? Number(tvaStandard) : TVA_STANDARD_DEFAUT
  return std
}

// Conversion inverse au moment de l'enregistrement : le modèle stocke des
// prix HT à 2 décimales. Pour tout TTC saisi à la dirham près, l'aller-retour
// TTC → HT(2 déc.) → TTC réaffiché redonne exactement la valeur tapée.
export function htFromTtc(ttc, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + tauxTvaOuDefaut(tauxTva) / 100
  return ((parseFloat(ttc) || 0) / factor).toFixed(2)
}

// Capacité batterie totale depuis les lignes (port de app.js).
// BAT5DEF (26/08/2026) — RÈGLE FONDATEUR « zéro chiffre inventé » : avant ce
// correctif, une ligne batterie dont la désignation ne portait pas de kWh
// lisible contribuait un défaut FABRIQUÉ de 5,0 kWh (jamais dérivé d'aucune
// donnée réelle). Elle contribue désormais 0 — voir `batteryCapaciteInconnue`
// ci-dessous pour SIGNALER ce cas à l'écran plutôt que de le taire.
export function batteryKwhFromLines(lines) {
  return lines.reduce((sum, l) => {
    if (!isBattery(l.designation)) return sum
    // L-2OPT — une ligne taguée 'sans' (voir fusionnerVariantes) porte une
    // quantité issue de la composition SANS batterie, jamais destinée à
    // compter dans quelque capacité que ce soit ; sans tag (comportement
    // historique) ce garde-fou est un no-op (`undefined !== 'sans'`).
    if (l.variante === 'sans') return sum
    const qty = parseFloat(l.quantite) || 0
    return sum + qty * (parseKwh(l.designation) ?? 0)
  }, 0)
}

// BAT5DEF — au moins une ligne batterie COMPTÉE (mêmes exclusions que
// `batteryKwhFromLines` : ni une ligne taguée 'sans') n'a pas de kWh lisible
// dans sa désignation → la capacité rendue par `batteryKwhFromLines`
// SOUS-ESTIME la vraie capacité (elle vaut 0 pour cette ligne, jamais un
// défaut inventé). Sert à afficher un avertissement honnête plutôt que de
// laisser croire que le chiffre est complet. `false` = soit aucune ligne
// batterie, soit toutes lisibles : comportement historique inchangé.
export function batteryCapaciteInconnue(lines) {
  return (lines || []).some(l =>
    isBattery(l.designation) && l.variante !== 'sans'
    && parseKwh(l.designation) == null)
}

// L-2OPT — nombre de PANNEAUX d'une option, avec la MÊME règle d'exclusion
// que `optionTotalsTTC`/`batteryKwhFromLines` : l'option SANS ignore les
// lignes taguées 'avec', l'option AVEC ignore celles taguées 'sans' ; une
// ligne sans tag (tout l'historique, et le cas non divergent de
// `fusionnerVariantes`) compte dans les DEUX. Sert à dériver le kWc PROPRE à
// chaque option depuis les lignes — sans quoi l'écran chiffre l'économie
// d'une composition avec le kWc de l'autre.
export function comptePanneauxOption(lines, option) {
  const exclu = option === 'avec' ? 'sans' : 'avec'
  return (lines || []).reduce((sum, l) => {
    if (!/panneau/i.test(l?.designation || '')) return sum
    if (l.variante === exclu) return sum
    return sum + (parseFloat(l.quantite) || 0)
  }, 0)
}

// QJR568 — le kWc réellement FACTURÉ par les lignes (branche SANS : commun +
// 'sans'), celui que le PDF dérive des lignes (builder.py). Le champ « nb
// panneaux » reste la CIBLE du dimensionnement (dry-run) ; ce kWc-ci alimente
// prix/kWc, prix cible, études C&I et l'aperçu horaire. `repli` (la cible)
// quand aucune ligne panneau ou aucun wattage lisible — jamais un 0 inventé.
export function kwcFactureDesLignes(lines, panelW, repli) {
  const n = comptePanneauxOption(lines, 'sans')
  const w = parseFloat(panelW) || 0
  if (!(n > 0) || !(w > 0)) return repli
  return n * w / 1000
}

// ── QJR402 — QF9 (Smart Meter / clé Wi-Fi Huawei-only) MIROIR DU NOYAU ──────
// Miroir exact de `apps/ventes/utils/options.py` `_panier_sert_huawei` /
// `retirer_accessoires_huawei` (QJR200/QF9), déclarée backend-only jusqu'ici :
// un panier dont l'onduleur n'est PAS de marque Huawei perd ses accessoires
// propres à Huawei (Smart Meter, clé Wi-Fi/dongle) — sans quoi le total
// affiché au vendeur compte un accessoire que ni le noyau monnaie ni le PDF
// ne facturent sur cette option (divergence atteinte via `autoFillLines`,
// dont la garde Huawei :2043-2047 raisonne sur le devis ENTIER, jamais
// panier par panier).
export const isSmartMeter = (d) => _norm(d).includes('smart meter')
// Miroir exact de `_WIFI_RE` (options.py) : « Wi-Fi » s'écrit de plusieurs
// façons, un simple `includes('wifi')` rate « Wi-Fi » avec trait d'union.
const _WIFI_RE = /wi[\s\-_.]*fi/
export const isWifiDongle = (d) => {
  const n = _norm(d)
  return n.includes('dongle') || _WIFI_RE.test(n)
}
const _estAccessoireHuawei = (d) => isSmartMeter(d) || isWifiDongle(d)

// True quand le panier `rows` est servi par un onduleur Huawei — miroir exact
// de `_panier_sert_huawei` : sans onduleur identifiable → False (on n'affiche
// pas ces accessoires par défaut) ; le moindre onduleur non-Huawei dans le
// panier suffit à les retirer (conservateur).
function _panierSertHuawei(rows) {
  const onduleurs = rows.filter(l => isAnyInverter(l?.designation))
  if (onduleurs.length === 0) return false
  let huaweiVu = false
  for (const l of onduleurs) {
    if (_norm(l?.designation).includes('huawei')) {
      huaweiVu = true
    } else {
      return false
    }
  }
  return huaweiVu
}

// `rows` privé de ses accessoires Huawei orphelins — miroir exact de
// `retirer_accessoires_huawei`.
function _retirerAccessoiresHuawei(rows) {
  if (_panierSertHuawei(rows)) return rows
  return rows.filter(l => !_estAccessoireHuawei(l?.designation))
}

// ── ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — miroir EXACT de
// `apps/ventes/selectors.py` `_canonical_totaux` (la chaîne que le PDF, le BC
// et la facture appliquent) sur les lignes TELLES QUE L'ÉCRAN LES PERSISTE :
// prix unitaire HT = `htFromTtc(prix_unit_ttc, taux)` (2 décimales), quantité
// au centième (DecimalField 2 déc.), taux de la ligne (repli 20). Arithmétique
// ENTIÈRE (BigInt) et arrondi ROUND_HALF_UP, comme `Decimal` côté serveur —
// jamais un flottant arrondi à la fin. Rend le TTC en MAD (2 décimales).
// QJR529 — la remise PAR LIGNE stockée (`remise`, %) entre comme côté serveur
// (`LigneDevis.total_ht` = q × pu × (1 − remise/100), exact, avant la chaîne
// d'arrondis) : les montants internes sont en 1e-8 MAD (×10 000 pour porter
// le facteur (10 000 − remise×100) sans perte). Remise absente/nulle ⇒
// résultat strictement inchangé (mise à l'échelle entière exacte).
// QJR642 — la chaîne de totaux vit dans `remise.totauxCanoniques` (UN noyau
// pour le générateur et la répartition de remise) : ici ne reste que la
// conversion TTC saisi → HT persisté, en nanos exacts (1e-8 MAD × 10).
// ARRONDI-100 — `arrondiPas` (MAD) : le TTC ramené au palier inférieur,
// exactement comme le noyau (`_absorber_arrondi`) ; absent = TTC exact.
export function totauxCanoniquesTtc(lines, discountPct = 0, arrondiPas = 0) {
  const lignes = (lines || []).map((l) => {
    const qH = BigInt(Math.round((parseFloat(l?.quantite) || 0) * 100))
    const taux = parseFloat(l?.taux_tva ?? TVA_STANDARD_DEFAUT)
    const tauxLigne = Number.isFinite(taux) ? taux : TVA_STANDARD_DEFAUT
    const htC = BigInt(Math.round(parseFloat(htFromTtc(l?.prix_unit_ttc, l?.taux_tva ?? TVA_STANDARD_DEFAUT)) * 100))
    const remH = BigInt(Math.round((parseFloat(l?.remise) || 0) * 100)) // % × 100
    return {
      // quantité ×100 · prix HT en centimes · (1 − remise) ×10 000 = 1e-8 MAD
      htNano: qH * htC * (10000n - remH) * 10n,
      taux: tauxLigne,
      typeLigne: l?.typeLigne ?? l?.type_ligne,
      optionnelle: l?.optionnelle,
    }
  })
  return totauxCanoniques(lignes, discountPct, { arrondiPas }).ttc
}

// ── Totaux par option, TTC (port exact de updateTotals de app.js) ────────────
// Option 1 SANS batterie : exclut Batterie + Onduleur hybride.
// Option 2 AVEC batterie : exclut Onduleur réseau.
// ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les trois libellés qui DÉCLARENT
// une alternative commerciale (le noyau sert alors UNE option, panier filtré
// ET règle QF9 appliquée) : la liste vit dans `quote/scenarios.js`.
export const SCENARIOS_ALTERNATIVE = SCENARIOS_VALIDES

// Miroir de `familles_des_lignes` + `familles_servables` + la condition
// « alternative déclarée » de `deux_options_depuis_paniers` (utils/options.py) :
// le scénario déclaré ne suffit pas, l'ÉQUIPEMENT doit servir les deux
// paniers (onduleur réseau d'un côté ; hybride avec batterie ou réseau, ou
// autonome avec batterie, de l'autre). Seules les lignes produit non
// optionnelles de quantité > 0 comptent, comme au noyau.
export function alternativeDeclareeServable(lines, scenario) {
  if (!SCENARIOS_ALTERNATIVE.includes(scenario)) return false
  const d = (lines || [])
    .filter(l => (parseFloat(l?.quantite) || 0) > 0 && !l?.optionnelle
      && l?.typeLigne !== 'section' && l?.typeLigne !== 'note')
    .map(l => l.designation)
  const hasReseau = d.some(isReseauInverter)
  const hasHybride = d.some(isHybridInverter)
  const hasOffgrid = d.some(isOffgridInverter)
  const hasBatterie = d.some(isBattery)
  const avecOk = (hasHybride && (hasBatterie || hasReseau)) || (hasOffgrid && hasBatterie)
  return hasReseau && avecOk
}

// `options.scenario` (facultatif) — le scénario DÉCLARÉ par l'écran. Absent :
// comportement historique inchangé (QF9 réservée aux lignes variantées).
export function optionTotalsTTC(lines, discountPct, { scenario } = {}) {
  // QJR567 — MÊME population que le noyau (`ligne_compte_dans_totaux`) : une
  // ligne optionnelle (add-on non activé) et les sections / notes ne
  // comptent JAMAIS — sans ce filtre le rail, le prix/kWc, la marge et
  // l'étude C&I persistée comptaient un add-on que le document exclut.
  lines = (lines || []).filter(ligneCompteDansTotaux)
  // F14 (26/08) — une ligne DÉCLARÉE ('sans'/'avec') tranche SEULE, plus de
  // second filtre mot-clé sur elle (voir `appartientAuPanierSans/Avec` :
  // miroir exact de builder.py `_repartir_options` et de
  // `apps/ventes/utils/options.py`). Une ligne SANS `variante` retombe sur
  // les mots-clés, mot pour mot comme avant.
  let linesSans = lines.filter(appartientAuPanierSans)
  let linesAvec = lines.filter(appartientAuPanierAvec)
  // QJR402/QJR300 — QF9 ne s'applique QUE sur un VRAI devis à deux options
  // DÉCLARÉES (miroir de `deux_options`/`alternative_declaree` au noyau) :
  // la seule trace, côté lignes, d'une alternative déclarée est `variante`
  // ('sans'/'avec'), posée uniquement par `fusionnerVariantes` pour un
  // scénario « Les deux ». Un devis SANS aucune ligne variantée (mono-
  // composition, y compris l'artefact « deux onduleurs non déclarés ») garde
  // TOUTES ses lignes, comportement historique strictement inchangé.
  // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — …ET sur un devis dont le
  // SCÉNARIO déclare l'alternative (miroir de `deux_options_declarees` :
  // `alternative_declaree or variantes`). Sans cette branche, un devis « Les
  // deux » à lignes non variantées affichait l'option AVEC avec le Smart
  // Meter + la clé Wi-Fi Huawei que le noyau et le PDF retirent (3 000 MAD
  // d'écart mesurés entre le formulaire et le devis persisté).
  if (lines.some(l => l?.variante === 'sans' || l?.variante === 'avec')
      || alternativeDeclareeServable(lines, scenario)) {
    linesSans = _retirerAccessoiresHuawei(linesSans)
    linesAvec = _retirerAccessoiresHuawei(linesAvec)
  }
  // ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — LA CHAÎNE CANONIQUE DU NOYAU, plus
  // une somme de TTC arrondis ligne à ligne remisée ensuite. Le chiffre facturé
  // (PDF/BC/facture) est `selectors._canonical_totaux` sur les lignes
  // PERSISTÉES (HT = `htFromTtc`, exactement ce que l'écran envoie) : HT brut →
  // remise globale → TVA par taux → TTC, au centime. L'écran le reproduit à
  // l'identique (`totauxCanoniquesTtc` ci-dessous) : avant, 36/200 devis du
  // corpus figé divergeaient d'un centime. Le « brut » est la même chaîne
  // sans remise (la valeur que le noyau facture à 0 %).
  // ARRONDI-100 — chaque total (avant ET après remise) est ramené au palier de
  // 100 MAD inférieur, comme le devis enregistré et son PDF : sans remise, le
  // « brut » et le « net » restent donc égaux (aucun prix barré fantôme).
  const pct = parseFloat(discountPct) || 0
  const pas = PAS_ARRONDI_DEVIS
  const totalSansBrut = totauxCanoniquesTtc(linesSans, 0, pas)
  const totalAvecBrut = totauxCanoniquesTtc(linesAvec, 0, pas)
  const totalSans = totauxCanoniquesTtc(linesSans, pct, pas)
  const totalAvec = totauxCanoniquesTtc(linesAvec, pct, pas)
  return { totalSansBrut, totalAvecBrut, totalSans, totalAvec }
}

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
    const base = { ...g, compose: true }
    if (oi == null) return base
    appariee.set(oi, gi)
    const o = olds[oi]
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

// ── QJ31 — Multi-propriétés : aperçu écran (TTC) miroir du backend QJ29 ──────
// Deux modes, tous deux additifs et mutuellement exclusifs à l'écran (un seul
// devis, jamais scindé) :
//   (A) ×N villas identiques : `nombreProprietes` multiplie le total TTC.
//   (B) villas différentes : les lignes portent `groupeIndex`/`groupeLabel`
//       (0 = commun) → sous-total par villa + total général, comme
//       `multi_villa_totaux` (selectors.py) mais en TTC (écran) plutôt qu'en
//       HT→TVA→TTC (backend, qui reste la source AUTORITAIRE au moment du PDF).
// Retourne null quand aucun des deux modes n'est utilisé (aperçu inchangé).
const _foisN = (ttc, n) => (Math.round((Number(ttc) || 0) * 100) * n) / 100
export function multiPropertyPreviewTTC(lines, { nombreProprietes, discountPct } = {}) {
  const n = parseInt(nombreProprietes, 10)
  if (Number.isFinite(n) && n > 1) {
    const { totalSans, totalAvec, totalSansBrut, totalAvecBrut } = optionTotalsTTC(lines, discountPct)
    return {
      mode: 'multiplicateur',
      nombreProprietes: n,
      totalUnitaireSans: totalSans, totalUnitaireAvec: totalAvec,
      // ERR-QAC-MULTIVILLA-TOTAL-XN — ×N AU CENTIME, comme le backend
      // (`selectors.totaux_multi_proprietes` / `builder._scale_tot`) : ce
      // total est désormais celui facturé. Unitaire en centimes entiers × N
      // (jamais un flottant arrondi au dirham).
      totalMultiSans: _foisN(totalSans, n), totalMultiAvec: _foisN(totalAvec, n),
      totalUnitaireSansBrut: totalSansBrut, totalUnitaireAvecBrut: totalAvecBrut,
    }
  }

  const grouped = lines.filter(l => l.groupeIndex != null)
  if (!grouped.length) return null

  const ttc = (l) => (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
  const byIndex = new Map()
  for (const l of grouped) {
    const idx = l.groupeIndex
    if (!byIndex.has(idx)) byIndex.set(idx, { lignes: [], label: '' })
    const bucket = byIndex.get(idx)
    bucket.lignes.push(l)
    if (!bucket.label && (l.groupeLabel || '').trim()) bucket.label = l.groupeLabel.trim()
  }
  const groupes = [...byIndex.keys()].sort((a, b) => a - b).map(idx => {
    const bucket = byIndex.get(idx)
    const totalTtc = bucket.lignes.reduce((s, l) => s + ttc(l), 0)
    return {
      index: idx,
      label: bucket.label || (idx === 0 ? 'Équipement commun' : `Villa ${idx}`),
      totalTtc: Math.round(totalTtc),
    }
  })
  const grandTotalTtc = Math.round(groupes.reduce((s, g) => s + g.totalTtc, 0))
  return { mode: 'villas', groupes, grandTotalTtc }
}

// ── Catégories du catalogue simulateur (clés de brand_catalog.json) ──────────
// Le sélecteur de produits est groupé exactement selon ces catégories.
export const PRODUCT_CATEGORIES = [
  ['onduleur_reseau', 'Onduleur Injection'],
  ['onduleur_hybride', 'Onduleur Hybride'],
  ['onduleur_offgrid', 'Onduleurs hors réseau'],
  ['panneau', 'Panneaux'],
  ['batterie', 'Batterie'],
  // STKCAT2 — rôle GÉNÉRIQUE de structure (émis pour un produit dont le nom
  // ne dit ni « acier » ni « alu »), puis ses deux alias DÉPRÉCIÉS, conservés
  // pour toujours : un réglage de marque enregistré hier reste lisible.
  ['structure', 'Structures'],
  ['structure_acier', 'Structures acier'],
  ['structure_alu', 'Structures aluminium'],
  ['socle', 'Socles'],
  ['cable_dc', 'Câble solaire DC'],
  ['cable_terre', 'Câble de terre AC'],
  ['smart_meter', 'Smart Meter'],
  ['wifi_dongle', 'Wifi Dongle'],
  ['accessoires', 'Accessoires'],
  ['tableau', 'Tableau De Protection AC/DC'],
  ['installation', 'Installation'],
  ['transport', 'Transport'],
  ['suivi', 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans'],
]

// STKCAT24 — bucket sur le rôle EFFECTIF résolu côté serveur
// (`role_devis_effectif`, STKCAT21 : déclaré → catégorie → mots-clés du nom)
// quand il est présent ; repli sur `classifyProduct(nom)` sinon — un produit
// sans ce champ (fixture ancienne, écran pas encore rechargé) garde un
// comportement BYTE-IDENTIQUE à avant STKCAT24.
export function groupProduitsByCategory(produits) {
  const buckets = new Map(PRODUCT_CATEGORIES.map(([key]) => [key, []]))
  const autres = []
  for (const p of produits) {
    const effectif = p.role_devis_effectif
    let type = effectif ?? classifyProduct(p.nom)
    if (type === 'structure') {
      if (effectif) {
        // Rôle EFFECTIF générique : la matière (acier/alu) ne se lit QUE dans
        // le nom, jamais un défaut « acier » silencieux — sans l'un ni
        // l'autre mot-clé, la ligne reste dans le seau générique `structure`
        // (label PRODUCT_CATEGORIES ci-dessus : « Structures »).
        if (_norm(p.nom).includes('acier')) type = 'structure_acier'
        else if (_norm(p.nom).includes('alu')) type = 'structure_alu'
      } else {
        // Repli mots-clés historique (rôle effectif absent/null) — byte-
        // identique à avant STKCAT24 : défaut ACIER sans mot-clé « alu ».
        type = _norm(p.nom).includes('alu') ? 'structure_alu' : 'structure_acier'
      }
    }
    if (type && buckets.has(type)) buckets.get(type).push(p)
    else autres.push(p)
  }
  const groups = PRODUCT_CATEGORIES
    .map(([key, label]) => ({ label, items: buckets.get(key) }))
    .filter(g => g.items.length)
  if (autres.length) groups.push({ label: 'Autres', items: autres })
  return groups
}

// Libellé FR d'un rôle ROLES_AUTO_COMPOSITION (mirroir des clés PRODUCT_CATEGORIES).
// STKCAT2 — le repli ne montre JAMAIS la clé BRUTE au commercial : avant que
// le rôle générique `structure` n'entre dans PRODUCT_CATEGORIES,
// `roleLabel('structure')` affichait « structure » en toutes lettres dans le
// message « marque épinglée introuvable au stock ». Un rôle hors miroir est
// désormais humanisé en français (underscores → espaces, capitale initiale).
export function roleLabel(role) {
  const trouve = PRODUCT_CATEGORIES.find(([key]) => key === role)
  if (trouve) return trouve[1]
  const brut = String(role ?? '').replace(/_/g, ' ').trim()
  if (!brut) return 'Équipement'
  return brut.charAt(0).toUpperCase() + brut.slice(1)
}

// ── PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes de devis ──────
// Frontend de `ParametresGammes.ordre_lignes` (apps/ventes/models.py) : une
// liste de rôles PRODUCT_CATEGORIES/ROLES_AUTO_COMPOSITION dans l'ordre voulu
// pour les PROCHAINS devis. Sans préférence (absente/vide) : ordre CANONIQUE
// de composition inchangé — zéro régression tant que rien n'est enregistré.

// Trie une liste de lignes TAGUÉES `[role, ligne]` par préférence de rôle.
// Un rôle PRÉSENT dans `ordreLignes` est classé à sa position ; un rôle
// ABSENT garde son rang canonique mais TOUJOURS après tout rôle
// explicitement préféré — tri STABLE (jamais un ex-æquo aléatoire) : les
// deux lignes « batterie » (5 kWh / 10 kWh) gardent leur ordre relatif entre
// elles quand leur rôle est préféré, ou l'un envers l'autre à la fin sinon.
export function orderLinesByRolePreference(taggedLines, ordreLignes) {
  if (!Array.isArray(ordreLignes) || !ordreLignes.length) {
    return taggedLines.map(([, ligne]) => ligne)
  }
  const rang = (role) => {
    const idx = ordreLignes.indexOf(role)
    return idx === -1 ? Infinity : idx
  }
  return taggedLines
    .map((entree, i) => ({ entree, i }))
    .sort((a, b) => {
      const ra = rang(a.entree[0])
      const rb = rang(b.entree[0])
      return ra !== rb ? ra - rb : a.i - b.i
    })
    .map(({ entree }) => entree[1])
}

// Dérive la séquence de rôles depuis les lignes COURANTES de l'écran (bouton
// « Enregistrer cet ordre comme ordre par défaut ») : classification RÉUTILISÉE
// (aucun nouveau mot-clé — même classifyProduct que groupProduitsByCategory),
// dédupliquée en gardant la PREMIÈRE occurrence (l'ordre écran des DEUX lignes
// batterie 5/10 kWh ne compte que pour un seul rang « batterie »), et les
// lignes sans classification reconnue (section/note, désignation libre) sont
// simplement ignorées — jamais un rôle inventé.
export function deriveRoleOrderFromLines(lines) {
  const seen = new Set()
  const order = []
  for (const l of (lines ?? [])) {
    let role = classifyProduct(l.designation)
    if (!role) continue
    // STKCAT10 — MÊME règle d'émission que la composition (écran ET serveur) :
    // un libellé qui ne dit ni « acier » ni « alu » (une pergola) donne le rôle
    // GÉNÉRIQUE `structure`, jamais `structure_acier` par défaut — sinon
    // l'ordre enregistré ne retrouverait jamais la ligne réellement composée.
    if (role === 'structure') role = structureRoleForName(l.designation)
    if (seen.has(role)) continue
    seen.add(role)
    order.push(role)
  }
  return order
}

// ── PVMRQ — marque préférée par gamme/rôle (fondateur 18/08/2026) ────────────
// Frontend de `ParametresGammes.marques` (backend, ROLES_AUTO_COMPOSITION —
// MIROIR EXACT des clés `PRODUCT_CATEGORIES` ci-dessus) : quand une marque est
// épinglée pour un rôle, elle GAGNE TOUJOURS — le vivier de candidats de ce
// rôle est restreint À ELLE SEULE avant toute autre logique (wattage/prix/
// compatibilité). Sans marque réglée pour ce rôle (clé absente ou vide),
// comportement byte-identique à l'historique.

// Marque épinglée pour ce rôle dans la carte `marques` ({role: marque}) de la
// gamme active, ou '' si aucune préférence — ne lève jamais.
function _marqueEpinglee(marques, role) {
  const carte = marques && typeof marques === 'object' ? marques : null
  const m = carte ? carte[role] : null
  return typeof m === 'string' ? m.trim() : ''
}

// Le produit porte-t-il la marque épinglée ? MIROIR EXACT de
// `_marque_correspond` (apps/ventes/services.py) : `produit.marque` (champ
// structuré) prioritaire, égalité EXACTE une fois normalisée ; à défaut (marque
// non renseignée sur la fiche), son `nom` DOIT seulement CONTENIR la marque,
// jamais l'égaler. Réutilise `_norm` (accents/casse) — le backend ne compare
// que la casse (`casefold`), mais un accent divergent ne doit pas non plus
// faire manquer une marque bien réelle côté écran.
function _marqueCorrespond(produit, marque) {
  const cible = _norm(marque)
  if (!cible) return false
  const marqueProduit = _norm(produit?.marque)
  if (marqueProduit) return marqueProduit === cible
  return _norm(produit?.nom).includes(cible)
}

// Restreint un vivier de candidats à la marque épinglée pour `role` (carte
// `marques` de la gamme active). Sans préférence réglée : vivier RENVOYÉ TEL
// QUEL (comportement historique). Marque réglée mais AUCUN candidat ne la
// porte : vivier VIDE — JAMAIS un repli silencieux sur une autre marque — et
// l'entrée `{ role, marque }` est consignée dans `manquantes` (dédupliquée par
// rôle, même patron que `onduleursIncomplets`).
function _filtrerParMarque(pool, role, marques, manquantes, vusRoles) {
  const source = pool ?? []
  const marque = _marqueEpinglee(marques, role)
  if (!marque) return source
  const filtres = source.filter(p => _marqueCorrespond(p, marque))
  if (!filtres.length && vusRoles && !vusRoles.has(role)) {
    vusRoles.add(role)
    manquantes.push({ role, marque })
  }
  return filtres
}

// ── Indexation par type des produits du stock ─────────────────────────────────
// STKCAT24 — même repli que `groupProduitsByCategory` : `role_devis_effectif`
// (STKCAT21) d'abord, mots-clés du nom ENSUITE, seulement quand le champ est
// absent/null — un produit sans ce champ indexe exactement comme avant.
function indexProduits(produits) {
  const byType = {}
  for (const p of produits) {
    const type = p.role_devis_effectif ?? classifyProduct(p.nom)
    if (!type) continue
    if (!byType[type]) byType[type] = []
    byType[type].push(p)
  }
  return byType
}

const lineFrom = (p, quantite, ttcOverride = null) => ({
  produit: p ? String(p.id) : '',
  designation: p ? p.nom : '',
  quantite,
  prix_unit_ttc: p || ttcOverride != null
    ? (ttcOverride != null ? ttcOverride : ttcFromHt(p.prix_vente, tauxTvaOf(p)))
    : 0,
  taux_tva: p ? tauxTvaOf(p) : 20,
})

// Ligne vide placeholder (désignation canonique, pas de produit)
const placeholder = (designation, quantite) => ({
  produit: '', designation, quantite, prix_unit_ttc: 0, taux_tva: 20,
})

// ── Table par défaut au chargement (port de getDefaultProductLines) ──────────
// Quantités par défaut du simulateur ; les lignes « spéciales » (onduleurs,
// panneaux, batteries) restent à choisir, les autres pointent sur le produit
// canonique du stock avec son prix TTC (équivalent de autofillRowPrice).
// PVORD — `ordreLignes` (optionnel, `ParametresGammes.ordre_lignes`) réordonne
// le résultat par rôle préféré ; absent/vide = ordre canonique ci-dessous,
// byte-identique à l'historique (voir `orderLinesByRolePreference`).
export function defaultProductLines(produits, ordreLignes) {
  const byType = indexProduits(produits)
  const first = (type) => (byType[type] ?? [])[0] ?? null
  const exactOr = (type, needle) => {
    const pool = byType[type] ?? []
    return pool.find(p => _norm(p.nom).includes(needle)) ?? null
  }
  const row = (p, designation, quantite) =>
    p ? lineFrom(p, quantite) : placeholder(designation, quantite)

  const tagged = [
    ['onduleur_reseau', placeholder('Onduleur réseau', 1)],
    ['onduleur_hybride', placeholder('Onduleur hybride', 1)],
    ['smart_meter', row(first('smart_meter'), 'Smart Meter', 0)],
    ['wifi_dongle', row(first('wifi_dongle'), 'Wifi Dongle', 0)],
    ['panneau', placeholder('Panneaux', 0)],
    ['batterie', placeholder('Batterie', 1)],
    ['batterie', placeholder('Batterie', 0)],
    ['structure_acier', row(exactOr('structure', 'acier'), 'Structures acier', 0)],
    ['structure_alu', row(exactOr('structure', 'alu'), 'Structures aluminium', 0)],
    ['socle', row(first('socle'), 'Socles', 0)],
    ['accessoires', row(first('accessoires'), 'Accessoires', 1)],
    ['tableau', row(first('tableau'), 'Tableau De Protection AC/DC', 1)],
    ['installation', row(first('installation'), 'Installation', 1)],
    ['transport', row(first('transport'), 'Transport', 1)],
    ['suivi', row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 1)],
  ]
  return orderLinesByRolePreference(tagged, ordreLignes)
}

/* STKCAT10 — LE RÔLE ÉMIS POUR LA LIGNE STRUCTURE, MIROIR EXACT DU SERVEUR
   (`apps/ventes/domain/composition.py::role_structure_du_produit`, règle
   d'émission écrite au contrat `contract_samples/devis_composition.json`) :
   le rôle suit le NOM DU PRODUIT RETENU, jamais le bouton demandé.
     · le nom porte encore « acier »          ⇒ `structure_acier` ;
     · le nom porte encore « alu »/« aluminium » ⇒ `structure_alu` ;
     · ni l'un ni l'autre (pergola, carport, bac lesté…) ⇒ le rôle GÉNÉRIQUE
       `structure` (déjà inscrit dans PRODUCT_CATEGORIES par STKCAT2).
   `voulu` départage un nom qui porterait LES DEUX mots-clés, et c'est aussi
   le rôle rendu quand aucun nom n'est lisible — comportement d'hier, au
   caractère près. */
export function structureRoleForName(nom, voulu = 'acier') {
  const prefere = _norm(voulu).startsWith('alu') ? 'alu' : 'acier'
  const autre = prefere === 'alu' ? 'acier' : 'alu'
  const role = { alu: 'structure_alu', acier: 'structure_acier' }
  const n = _norm(nom)
  if (!n) return role[prefere]
  if (n.includes(prefere)) return role[prefere]
  if (n.includes(autre)) return role[autre]
  return 'structure'
}

/* STKCAT10 — LE PRODUIT DE STRUCTURE EXPLICITEMENT CHOISI, résolu comme le
   serveur le résout : dans le catalogue COMPLET déjà scopé société (pas dans
   le vivier « structures nommées », sinon une pergola resterait invisible) et
   APRÈS la garde de prix — un id qui désignerait un produit non tarifé, ou
   celui d'une autre société, ne résout RIEN et la composition retombe sur le
   bouton acier/alu. Ni le filtre par mot-clé ni la marque épinglée du rôle ne
   s'y appliquent : un choix explicite ne se re-choisit pas. */
export function structureChoisie(produits, structureProduitId) {
  if (structureProduitId == null || structureProduitId === '') return null
  const cible = String(structureProduitId)
  return (produits ?? []).find(
    (p) => String(p?.id) === cible && _hasPrix(p)) ?? null
}

// ── Auto-remplissage (port exact de auto_fill_from_power + autofill_router) ───
// Retourne la table complète dans l'ordre canonique du simulateur (ou l'ordre
// PVORD `ordreLignes` s'il est fourni — voir `orderLinesByRolePreference`),
// lignes à quantité nulle comprises (elles s'affichent mais ne sont pas
// enregistrées).
// `mpptPaires` (PVCBL, 19/08) — nombre de paires de câble DC (voir
// `metreCableDcParPaires`) ; absent = repli fondateur à 1 paire.
// OFFGRID — composition hors réseau (site isolé), UNE SEULE option (panneaux
// + onduleur hors réseau + batterie), jamais fusionnée avec réseau/hybride :
// `offgrid: true` réutilise TOUT le pipeline de `autoFillLines` (structures,
// câblage, accessoires, sélection batterie) en substituant seulement la
// famille d'onduleur retenue — `offgrid` absent/faux reste BYTE-IDENTIQUE au
// comportement historique (aucune branche ci-dessous ne s'active).
// STKCAT10 — `structureProduitId` (optionnel) est LE PRODUIT DE STRUCTURE
// choisi à l'écran dans le catalogue : il est PRIORITAIRE sur `structureType`
// (devenu l'alias déprécié), les deux ne se combinent JAMAIS, et il fait
// émettre UNE SEULE ligne structure au lieu de la paire acier/alu figée.
// Absent ⇒ comportement BYTE-IDENTIQUE à l'historique (paire acier + alu,
// l'une à `nbPanneaux`, l'autre à 0) — épinglé par test.
export function autoFillLines(produits, { kwp, panelW, structureType, nbPanneaux: nbOverride, marques, ordreLignes, mpptPaires, offgrid, structureProduitId }) {
  if (!kwp || kwp <= 0) return []
  const byType = indexProduits(produits)
  // PVMRQ — marques préférées par rôle (gamme active) : sans réglage, `marques`
  // est absent/vide et le comportement reste byte-identique à l'historique.
  // `marquesManquantes` consigne chaque rôle épinglé sans AUCUN candidat en
  // stock (même patron que `onduleursIncomplets`) — jamais un repli silencieux.
  const marquesManquantes = []
  const vuMarqueManquante = new Set()
  const parMarque = (pool, role) =>
    _filtrerParMarque(pool, role, marques, marquesManquantes, vuMarqueManquante)

  // QX19 — nombre de panneaux : override explicite (dérivé d'une taille kWc
  // souhaitée) sinon dérivé de la puissance. Le kWc RÉEL est recalculé plus bas
  // depuis la puissance du panneau EFFECTIVEMENT retenu (jamais une divergence
  // silencieuse 550W-pour-710W).
  // U1 (fondateur 20/08/2026) — dérivation AU PLAFOND, même règle que
  // `panneauxPourKwc` : 5 kWc en 710 Wc font 8 panneaux, jamais 7. Un compte
  // fourni explicitement (`nbOverride`) est déjà un ENTIER de panneaux : il
  // garde son arrondi au plus proche (il ne dérive d'aucune puissance).
  const nbPanneaux = (Number(nbOverride) > 0)
    ? Math.round(Number(nbOverride))
    : Math.max(1, plafondPanneaux(kwp * 1000 / panelW))
  const threshold = kwp * 0.8

  // PVOND — VERROU DE COMPLÉTUDE : un onduleur auquel il manque une variable
  // du CONTRAT (puissance AC, phases, MPPT, tensions, courant, rendement,
  // plage batterie, garantie) est EXCLU de l'auto-composition et remonté à
  // l'écran avec son motif — exactement le patron de « prix à renseigner » :
  // on ne chiffre pas un appareil qu'on ne sait pas dimensionner, et on DIT
  // pourquoi. Il reste sélectionnable à la main.
  const onduleursIncomplets = []
  const vuIncomplet = new Set()
  const retenirIncomplet = (p) => {
    const manquantes = onduleurSpecsManquantes(p)
    if (!manquantes.length) return false
    if (!vuIncomplet.has(p.id)) {
      vuIncomplet.add(p.id)
      onduleursIncomplets.push({ id: p.id, nom: p.nom, manquantes })
    }
    return true
  }

  // Sélection onduleur : plus petit modèle >= 80 % de la puissance, sinon le
  // plus gros du catalogue ; à puissance égale, Triphasé si >= 10 kW sinon Mono.
  const pickInverter = (pool) => {
    const cands = (pool ?? [])
      .filter(p => !retenirIncomplet(p))
      .map(p => ({ p, kw: parseKw(p.nom), tri: parsePhaseIsTri(p.nom) }))
      .filter(x => x.kw != null && x.kw > 0)
      .sort((a, b) => a.kw - b.kw || a.p.id - b.p.id)
    if (!cands.length) return null
    let valid = cands.filter(x => x.kw >= threshold)
    if (!valid.length) valid = [cands[cands.length - 1]]
    const bestPower = valid[0].kw
    const same = valid.filter(x => x.kw === bestPower)
    const preferTri = bestPower >= 10
    const preferred = same.filter(x => x.tri === preferTri)
    return (preferred[0] ?? same[0])
  }
  const inverterQty = (kw) =>
    (!kw || kw >= threshold) ? 1 : Math.max(1, Math.ceil(kwp / kw))

  // OFFGRID — une composition hors réseau ne pose JAMAIS d'onduleur réseau ni
  // hybride (troisième famille exclusive des deux autres) : ces deux picks
  // restent `null` plutôt que de polluer `onduleursIncomplets` avec des
  // onduleurs qu'on ne va de toute façon pas composer.
  const reseau = offgrid ? null : pickInverter(parMarque(byType.onduleur_reseau, 'onduleur_reseau'))
  const hybride = offgrid ? null : pickInverter(parMarque(byType.onduleur_hybride, 'onduleur_hybride'))
  // OFFGRID — même sélection (plus petit modèle >= 80 % de la cible), MAIS
  // jamais un produit SANS PRIX (règle fondateur « zéro chiffre inventé » —
  // même patron que `_hasPrix`/`selectPompeByCurve` pour le pompage) : un
  // onduleur hors réseau non tarifé au catalogue ne doit jamais se retrouver
  // composé à 0 MAD sur un devis.
  const offgridInv = offgrid
    ? pickInverter(parMarque(
        (byType.onduleur_offgrid ?? []).filter(p => (parseFloat(p.prix_vente) || 0) > 0),
        'onduleur_offgrid'))
    : null
  if (offgrid && !offgridInv) {
    const vide = []
    // Incident fondateur 01/09 round 2 — le motif seul (« Aucun onduleur
    // hors réseau… ») laissait le vendeur deviner POURQUOI un produit qu'il
    // voit bien au catalogue (ex. « Deye off-Grid 6kw ») n'est pas trouvé :
    // le plus souvent, ce produit n'a simplement AUCUN prix de vente renseigné
    // (filtré ci-dessus AVANT ce message). Le rappel du contrat de nommage
    // partagé avec le backend (OFFGRID_KEYWORDS) rend l'erreur actionnable.
    vide.offgridErreur = 'Aucun onduleur hors réseau avec prix au catalogue. '
      + 'Le NOM du produit doit contenir « off-grid », « off grid », '
      + '« hors réseau » ou « autonome » (ex. « Deye Off-Grid 6kW »), '
      + 'avec un prix de vente.'
    vide.onduleursIncomplets = onduleursIncomplets
    return vide
  }

  // Panneaux : wattage saisi (défaut 710 → Canadien Solar 710 du catalogue)
  // PVMRQ — la marque épinglée restreint le vivier AVANT le rapprochement de
  // wattage : la substitution « wattage le plus proche » ne joue donc plus que
  // DANS le vivier de la marque retenue, jamais hors d'elle.
  const panels = parMarque(byType.panneau, 'panneau')
    .map(p => ({ p, w: parseWatt(p.nom) }))
    .filter(x => x.w != null)
  let panel = panels.filter(x => x.w === parseFloat(panelW))
    .sort((a, b) => (_norm(a.p.nom).includes('canadien') ? -1 : 1) - (_norm(b.p.nom).includes('canadien') ? -1 : 1))[0]
  if (!panel && panels.length) {
    panel = [...panels].sort((a, b) =>
      Math.abs(a.w - panelW) - Math.abs(b.w - panelW))[0]
  }

  // Batteries : cible = kWc arrondi au multiple de 5 (min 5 kWh),
  // ligne 1 = Dyness 5 kWh (qté nb_5), ligne 2 = Dyness 10 kWh (qté nb_10).
  // TOLÉRANCE DEUX ORTHOGRAPHES (miroir exact de services.py) : la marque
  // s'écrit « Dyness » (correction fondateur 2026-08-18) ; un produit encore
  // nommé « Deyness » (base non migrée, saisie manuelle) reste reconnu, sans
  // quoi le vivier retomberait sur TOUTES les batteries du catalogue.
  const target = Math.max(5, Math.round(kwp / 5) * 5)
  // PVOND — GARDE BATTERIE PILOTÉ PAR LA DONNÉE (remplace le garde par mot-clé
  // PVG4 ; miroir EXACT de `_batterie_compatible` côté backend
  // apps/ventes/services.py). Une batterie n'entre au vivier que si sa TENSION
  // NOMINALE tombe dans la PLAGE BATTERIE déclarée par l'onduleur HYBRIDE
  // retenu ci-dessus — c'est la vraie règle électrique, pas un nom de produit.
  // Repli intégral sur le mot-clé « haute tension » dès qu'une des deux données
  // manque : un catalogue non renseigné se comporte exactement comme hier.
  // L'exclusion se fait AVANT l'appariement par capacité 5/10 kWh ; une
  // batterie écartée reste sélectionnable à la main.
  // OFFGRID — la batterie s'accroche à l'onduleur HORS RÉSEAU retenu ci-dessus
  // (même règle électrique, même donnée `specs_solaire.plage_batterie_v`),
  // jamais à l'hybride qui est `null` dans cette branche.
  const plageBatterie = plageBatterieOnduleur(offgrid ? offgridInv?.p : hybride?.p)
  // PVMRQ — la compatibilité ÉLECTRIQUE (plage de tension) reste calculée sur
  // le vivier COMPLET (elle alimente aussi `avertissementsBatterie` ci-dessous,
  // un motif distinct de « marque introuvable ») ; la marque épinglée ne
  // restreint le vivier électriquement compatible QU'APRÈS, jamais avant — même
  // ordre que le backend `_pick_product` (garde métier avant marque).
  const batsCompatibles = (byType.batterie ?? [])
    .filter(p => batterieCompatible(p, plageBatterie))
  const bats = parMarque(batsCompatibles, 'batterie')
    .map(p => ({ p, cap: parseKwh(p.nom) }))
  const dyness = bats.filter(x => {
    const n = _norm(x.p.nom)
    return n.includes('dyness') || n.includes('deyness')
  })
  const batPool = dyness.length ? dyness : bats
  // Le vivier peut être VIDE alors que le catalogue porte des batteries : elles
  // sont toutes incompatibles avec l'onduleur hybride retenu. Le dire vaut
  // mieux que livrer un kit silencieusement sans stockage (miroir de
  // `avertissement_vivier_batterie_vide`, apps/ventes/services.py).
  const avertissementsBatterie = []
  if (!batPool.length && (byType.batterie ?? []).length
      && Array.isArray(plageBatterie) && plageBatterie[1] > 0) {
    avertissementsBatterie.push(
      `Aucune batterie compatible tarifée pour cet onduleur `
      + `(plage ${plageBatterie[0]}-${plageBatterie[1]} V) : `
      + `la composition part SANS batterie. Ajoutez une batterie compatible `
      + `au catalogue, ou changez d'onduleur.`)
  }
  // BATHOMO (fondateur 26/08/2026, F4 — revue adversariale) — MIROIR EXACT de
  // `composition_residentielle` (apps/ventes/services.py) : l'ancien calcul
  // (`nb10 = floor(cible/10)` + `nb5 = 1` si le reste ≥ 5) composait une
  // banque MÉLANGÉE 5+10 kWh en parallèle — électriquement interdit, le MÊME
  // incident qui a fait retirer le Dyness 10 kWh du stock de production côté
  // serveur. Cet écran étant l'« Auto-remplir » de secours au premier échec
  // du dry-run serveur (jamais un devis existant qu'on re-dénomme — pas de
  // pin ici, seulement une NOUVELLE sélection), la RÈGLE ÉCONOMIQUE
  // s'applique directement, comme le repli économique serveur :
  //   1. EN STOCK SEULEMENT (`quantite_stock` — un module à 0 en stock n'est
  //      composable ni serveur ni écran) ;
  //   2. UNE candidate homogène par calibre : le plus petit N de modules
  //      IDENTIQUES qui ATTEINT OU DÉPASSE la cible (jamais un manque) ;
  //   3. plafonnée par `specs_solaire.max_modules_par_banc` (le plafond
  //      fondateur — REJETÉE si dépassée, jamais tronquée) ;
  //   4. le prix TTC TOTAL le plus bas gagne, égalité tranchée par le moins
  //      de modules — jamais une préférence de calibre fixe.
  const enStock = (p) => (Number(p?.quantite_stock) || 0) > 0
  const batPoolStock = batPool.filter(x => enStock(x.p))
  const bat5Stock = batPoolStock.find(x => x.cap === 5)
  const bat10Stock = batPoolStock.find(x => x.cap === 10)
  const candidatBatterie = (cap, entry) => {
    if (!entry) return null
    const n = Math.max(1, Math.ceil(target / cap - 1e-9))
    const plafond = Number(entry.p?.specs_solaire?.max_modules_par_banc)
    if (Number.isFinite(plafond) && plafond > 0 && n > plafond) return null
    const puTtc = ttcFromHt(entry.p.prix_vente, tauxTvaOf(entry.p))
    return { cap, n, prixTtc: puTtc * n, entry }
  }
  const candidatsBatterie = [
    candidatBatterie(5, bat5Stock),
    candidatBatterie(10, bat10Stock),
  ].filter(Boolean)
  candidatsBatterie.sort((a, b) => (a.prixTtc - b.prixTtc) || (a.n - b.n))
  const batterieRetenue = candidatsBatterie[0] ?? null
  // OFFGRID — « un système hors réseau porte toujours sa batterie » (ordre
  // fondateur) : sans candidate retenue — OU une candidate à prix TOTAL nul
  // (aucune batterie du calibre gagnant n'est réellement tarifée : `prixTtc`
  // vaut 0 puisqu'il dérive du prix unitaire) — on N'INVENTE PAS un kit sans
  // stockage réel (contrairement au repli hybride ci-dessus, qui compose
  // quand même avec un avertissement) : on arrête, motif FRANÇAIS clair,
  // jamais un repli silencieux sur un onduleur hybride ni une ligne à 0 MAD.
  if (offgrid && !(batterieRetenue?.prixTtc > 0)) {
    const vide = []
    vide.offgridErreur = 'Aucune batterie compatible tarifée au catalogue pour cet onduleur hors réseau.'
    vide.onduleursIncomplets = onduleursIncomplets
    vide.avertissementsBatterie = avertissementsBatterie
    return vide
  }
  const nb5 = batterieRetenue?.cap === 5 ? batterieRetenue.n : 0
  const nb10 = batterieRetenue?.cap === 10 ? batterieRetenue.n : 0
  // `bat5`/`bat10` restent les produits du vivier COMPATIBLE (comme avant ce
  // correctif) — jamais restreints au seul calibre RETENU : la ligne du
  // calibre perdant reste une VRAIE ligne produit à quantité 0 (le tableau
  // éditable de l'écran doit pouvoir la faire remonter à la main), jamais un
  // placeholder générique.
  const bat5 = batPool.find(x => x.cap === 5)
  const bat10 = batPool.find(x => x.cap === 10)
  // F3/F5 — un vivier compatible NON VIDE qui n'aboutit quand même à AUCUNE
  // candidate (rupture de stock des deux calibres, ou plafond qui rejette la
  // seule candidate possible) reste HONNÊTE : même canal d'avertissement,
  // jamais un hybride sans batterie composé en silence.
  if (batPool.length && !batterieRetenue) {
    avertissementsBatterie.push(
      `Batterie(s) compatibles indisponibles pour la cible visée (rupture `
      + `de stock, ou plafond de modules par banc dépassé) : la composition `
      + `part SANS batterie. Réapprovisionnez, augmentez le plafond, ou `
      + `choisissez un autre module.`)
  }

  // Structures : type choisi par radio, 1 par panneau (prix catalogue).
  // PVMRQ — deux rôles DISTINCTS (`structure_acier`/`structure_alu`, comme
  // PRODUCT_CATEGORIES) : chacun a sa propre marque épinglée, appliquée sur le
  // sous-vivier déjà filtré par mot-clé acier/alu (même patron que les câbles
  // ci-dessous).
  // STKCAT10 — L'ID EXPLICITE D'ABORD (miroir de `composition.py` : « un
  // choix explicite ne se re-choisit pas »), le bouton acier/alu ensuite.
  // Avec un id, NI le filtre par mot-clé NI la marque épinglée du rôle ne
  // s'appliquent — le serveur n'appelle `par_marque` que dans SA branche
  // `else`, donc il ne consigne aucune « marque introuvable » pour la
  // structure quand le commercial a déjà choisi son produit. On ne l'appelle
  // donc pas non plus ici : sinon une marque épinglée sans candidat acier
  // ferait REFUSER un devis à pergola, pour un rôle qu'il n'utilise pas.
  const structureExplicite = structureChoisie(produits, structureProduitId)
  const structures = structureExplicite ? [] : (byType.structure ?? [])
  const structuresAcier = structureExplicite ? [] : parMarque(
    structures.filter(p => _norm(p.nom).includes('acier')), 'structure_acier')
  const structuresAlu = structureExplicite ? [] : parMarque(
    structures.filter(p => _norm(p.nom).includes('alu')), 'structure_alu')
  const structChosen = (structureType === 'aluminium' ? structuresAlu : structuresAcier)[0] ?? null
  const structOther = (structureType === 'aluminium' ? structuresAcier : structuresAlu)[0] ?? null

  // L-FORFAIT (fondateur 24/08/2026) — Accessoires / Tableau / Installation
  // se cotent AU PANNEAU : partie fixe + par-panneau, MIROIR TTC des champs
  // Stock seedés (HT : installation 2 000 + 250×n ; accessoires 52,0833×n ;
  // tableau 203,125×n — TVA 20 % sur ces items). Repli d'écran hors-ligne :
  // si le fondateur édite les champs dans Stock, c'est l'aperçu SERVEUR qui
  // fait foi (CJ2b — les chiffres serveur priment à l'écran).
  const prixAccessoires = 62.5 * nbPanneaux
  const prixTableau = 243.75 * nbPanneaux
  const prixInstallation = 2400 + 300 * nbPanneaux
  // Le MÉTRAGE du câble de terre reste indexé sur les blocs de 5 kWc :
  // l'ordre forfaits-au-panneau ne couvrait qu'Installation/Tableau/
  // Accessoires — les métrés de câble sont inchangés.
  const blocks = Math.max(1, Math.round(kwp / 5))

  // QF8 — Smart Meter + Clé Wifi : UNIQUEMENT quand l'onduleur retenu (réseau
  // OU hybride) est de marque Huawei (miroir du garde `info_hw` de l'ancien
  // simulateur Python). Un onduleur Deye — ou toute autre marque — ne les
  // ajoute jamais : qté 0. Vérifie `marque` (catalogue seedé) ET le nom (les
  // fixtures/anciens produits sans champ `marque` structuré) pour ne rien
  // manquer.
  const isHuawei = (p) => !!p && (
    _norm(p.marque).includes('huawei') || _norm(p.nom).includes('huawei'))
  const huaweiRetenu = isHuawei(reseau?.p) || isHuawei(hybride?.p) || isHuawei(offgridInv?.p)
  const smQty = huaweiRetenu ? 1 : 0
  const wifiQty = huaweiRetenu ? 1 : 0

  // PVMRQ — `first(type)` sert socle/smart_meter/wifi_dongle/accessoires/
  // tableau/installation/transport/suivi : le rôle épingle exactement la
  // MÊME clé que la catégorie (`type`), donc une seule ligne suffit à couvrir
  // les huit.
  const first = (type) => parMarque(byType[type], type)[0] ?? null
  const row = (p, designation, quantite, ttcOverride = null) =>
    p ? lineFrom(p, quantite, ttcOverride)
      : { ...placeholder(designation, quantite), prix_unit_ttc: ttcOverride ?? 0 }

  // Câbles : on préfère le NEXANS explicitement (marque confirmée fondateur
  // — un fournisseur, pas la préférence de gamme), sinon le premier câble du
  // type QUI PORTE UN PRIX. PVMRQ — la marque épinglée (si réglée pour
  // cable_dc/cable_terre) restreint le vivier avant cette préférence Nexans.
  // PVCBL (fondateur 19/08/2026) — VERROU DE CONDITIONNEMENT : le câble est
  // TOUJOURS acheté/vendu AU MÈTRE (le métrage plus bas est en MÈTRES), donc
  // un produit conditionné en rouleau/touret (ex. « Câble solaire 6mm²
  // (100m) ») ne doit JAMAIS entrer au vivier — même chiffré, même moins
  // cher, même seul candidat. Sans candidat « au mètre », le vivier est VIDE
  // et la ligne part en placeholder à 0 (même patron que « prix à
  // renseigner ») — jamais un repli silencieux sur un autre conditionnement.
  const chiffre = (p) => !!p && parseFloat(p.prix_vente) > 0
  const auMetre = (p) => _norm(p?.nom).includes('au metre')
  const pickCable = (type) => {
    const pool = parMarque((byType[type] ?? []).filter(chiffre).filter(auMetre), type)
    return pool.find(p => _norm(p.nom).includes('nexans')) ?? pool[0] ?? null
  }
  const cableDc = pickCable('cable_dc')
  const cableTerre = pickCable('cable_terre')

  const acierRow = structureType === 'aluminium'
    ? row(structOther, 'Structures acier', 0)
    : row(structChosen, 'Structures acier', nbPanneaux)
  const aluRow = structureType === 'aluminium'
    ? row(structChosen, 'Structures aluminium', nbPanneaux)
    : row(structOther, 'Structures aluminium', 0)
  // STKCAT10 — UNE SEULE ligne quand le produit est choisi (son libellé est
  // le NOM du produit, son rôle suit ce nom comme côté serveur) ; sinon la
  // paire acier/alu d'hier, inchangée au caractère près.
  const lignesStructure = structureExplicite
    ? [[structureRoleForName(structureExplicite.nom, structureType),
        row(structureExplicite, structureExplicite.nom, nbPanneaux)]]
    : [['structure_acier', acierRow], ['structure_alu', aluRow]]

  // PVORD — chaque ligne est TAGUÉE de son rôle avant l'assemblage final :
  // `orderLinesByRolePreference` réordonne selon `ordreLignes`
  // (`ParametresGammes.ordre_lignes`) si fourni, sinon renvoie EXACTEMENT
  // cet ordre canonique — comportement historique inchangé.
  // OFFGRID — UNE seule ligne onduleur (famille hors réseau), jamais réseau
  // ni hybride sur cette composition (mirroir : task 2, « compose ONE option »).
  const inverterRows = offgrid
    ? [['onduleur_offgrid', row(offgridInv?.p ?? null, 'Onduleur hors réseau',
        offgridInv ? Math.max(1, inverterQty(offgridInv.kw)) : 1)]]
    : [
        ['onduleur_reseau', row(reseau?.p ?? null, 'Onduleur réseau', reseau ? inverterQty(reseau.kw) : 1)],
        ['onduleur_hybride', row(hybride?.p ?? null, 'Onduleur hybride', hybride ? Math.max(1, inverterQty(hybride.kw)) : 1)],
      ]
  const lignesTaguees = [
    ...inverterRows,
    ['smart_meter', row(first('smart_meter'), 'Smart Meter', smQty)],
    ['wifi_dongle', row(first('wifi_dongle'), 'Wifi Dongle', wifiQty)],
    ['panneau', row(panel?.p ?? null, 'Panneaux', nbPanneaux)],
    ['batterie', row(bat5?.p ?? null, 'Batterie', nb5)],
    ['batterie', row(bat10?.p ?? null, 'Batterie', nb10)],
    ...lignesStructure,
    ['socle', row(first('socle'), 'Socles', nbPanneaux * 2)],
    // Câbles Nexans 6 mm² au mètre (règle fondateur 18/08). On ne retient qu'un
    // câble RÉELLEMENT chiffré : un produit sans prix n'entre jamais dans une
    // auto-composition (même patron que « prix à renseigner »).
    // PVCBL (19/08) — métrage PAR PAIRE de MPPT (voir metreCableDcParPaires),
    // plus lié au palier de 5 kWc. Quantité éditable à la main ensuite,
    // jamais re-forcée (aucun effet ne rejoue l'auto-composition après une
    // frappe manuelle sur le champ Qté).
    ['cable_dc', row(cableDc, 'Câble solaire Nexans 6 mm² (au mètre)', cableDc ? metreCableDcParPaires(mpptPaires) : 0)],
    ['cable_terre', row(cableTerre, 'Câble de terre Nexans 6 mm² (au mètre)', cableTerre ? metreCableTerre(blocks) : 0)],
    ['accessoires', row(first('accessoires'), 'Accessoires', 1, prixAccessoires)],
    ['tableau', row(first('tableau'), 'Tableau De Protection AC/DC', 1, prixTableau)],
    ['installation', row(first('installation'), 'Installation', 1, prixInstallation)],
    ['transport', row(first('transport'), 'Transport', 1)],
    ['suivi', row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 0)],
  ]
  const lignes = orderLinesByRolePreference(lignesTaguees, ordreLignes)
  // QX19 — puissance du panneau EFFECTIVEMENT retenu (peut différer de panelW
  // quand le catalogue n'a pas exactement panelW → substitution la plus proche)
  // + nb de panneaux : l'écran recalcule le kWc RÉEL depuis ces valeurs plutôt
  // que d'afficher un kWc théorique divergent. Métadonnées portées sur le
  // tableau (les consommateurs qui itèrent les lignes ne les voient pas).
  // PVORD — rattachées APRÈS le tri : `orderLinesByRolePreference` renvoie un
  // tableau NEUF (jamais les métadonnées attachées à `lignesTaguees`, qui n'en
  // porte aucune de toute façon).
  lignes.actualPanelW = panel?.w ?? panelW
  lignes.nbPanneaux = nbPanneaux
  lignes.kwcReel = Math.round(nbPanneaux * (panel?.w ?? panelW) / 10) / 100
  // PVOND — les onduleurs ÉCARTÉS faute de contrat complet, avec leur motif.
  // Métadonnée portée par le tableau (les consommateurs qui itèrent les lignes
  // ne la voient pas), lue par le générateur pour afficher le bandeau.
  lignes.onduleursIncomplets = onduleursIncomplets
  // PVOND — vivier batterie VIDE sous un onduleur à plage déclarée : même
  // métadonnée, même patron que les onduleurs incomplets ci-dessus.
  lignes.avertissementsBatterie = avertissementsBatterie
  // PVMRQ — rôles dont la marque épinglée n'a AUCUN candidat en stock (jamais
  // un repli silencieux sur une autre marque) : même patron de métadonnée que
  // ci-dessus, lue par le générateur pour afficher le bandeau dédié.
  lignes.marquesManquantes = marquesManquantes
  return lignes
}

// ══ Multi-marchés (2026-06) ═══════════════════════════════════════════════════

// CIQ228 — la valorisation C&I écran (rachat 82-21 net, injection) est
// SUPPRIMÉE : la revente MT et ses mentions viennent UNIQUEMENT du serveur
// (`economie_ci.revente`). `KWH_PRICE` reste : le RÉSIDENTIEL le lit encore
// (repli de `computeROI` et défaut `quoteLogic.kwhPrice` du générateur).

// ── Pompage solaire (mode Agricole) ───────────────────────────────────────────
// Heures de pompage effectives par défaut (champ 1.4× surdimensionné →
// la pompe tourne à régime nominal bien au-delà des heures équivalentes
// plein-soleil ; ~7 h/jour est l'hypothèse marché retenue — modifiable).
export const HEURES_POMPAGE_DEFAUT = 7

// QJR546 — exporté : le générateur saute (et nomme) les lignes d'un modèle
// dont le produit n'a plus de prix, avec la MÊME garde que l'auto-remplissage.
export const _hasPrix = (p) => (parseFloat(p.prix_vente) || 0) > 0

const _isPompe = (n) => n.includes('pompe ') || n.startsWith('pompe')

// QX20 — classification « pompe » exposée (garde d'équipement du générateur) :
// une désignation de ligne est une pompe si son nom normalisé le dit. Utilise
// le même _norm que les autres classificateurs.
export function isPompe(designation) {
  return _isPompe(_norm(designation || ''))
}
// ── Prix par kWc, prix cible et marge ─────────────────────────────────────────
export function prixParKwc(totalTtc, kwp) {
  if (!(kwp > 0) || !(totalTtc > 0)) return null
  return Math.round(totalTtc / kwp)
}

// Remise (%) impliquée par un prix cible /kWc — appliquée via la remise
// globale existante, jamais en réécrivant les prix des lignes.
export function discountForTarget(cibleKwc, kwp, totalBrutTtc) {
  const implied = (parseFloat(cibleKwc) || 0) * kwp
  if (!(implied > 0) || !(totalBrutTtc > 0)) return null
  const pct = (1 - implied / totalBrutTtc) * 100
  return Math.round(pct * 100) / 100
}

// Coût d'achat TTC des lignes dont le produit a un prix d'achat renseigné,
// ET le nombre de lignes CHIFFRÉES (prix de vente > 0) qui n'en ont pas
// (AGR134) : la marge est alors PARTIELLE (le coût y est sous-estimé).
// `cost` est null si AUCUN prix d'achat n'existe (alors on n'affiche rien).
// Le TTC d'achat suit le taux TVA du produit (10 % panneaux, 20 % le reste).
export function computeBuyCostDetail(lines, produits) {
  const byId = new Map(produits.map(p => [String(p.id), p]))
  let cost = 0
  let any = false
  let sansAchat = 0
  // QJR567 — même population que les totaux : ni optionnelle, ni section/note.
  for (const l of (lines || []).filter(ligneCompteDansTotaux)) {
    const p = byId.get(String(l.produit))
    const achat = p ? (parseFloat(p.prix_achat) || 0) : 0
    if (achat > 0) {
      any = true
      cost += (parseFloat(l.quantite) || 0) * achat * (1 + tauxTvaOf(p) / 100)
    } else if ((parseFloat(l.quantite) || 0) > 0 && (parseFloat(l.prix_unit_ttc) || 0) > 0) {
      sansAchat += 1
    }
  }
  return { cost: any ? Math.round(cost) : null, sansAchat }
}

// Appelants inchangés : le seul coût (ou null).
export function computeBuyCost(lines, produits) {
  return computeBuyCostDetail(lines, produits).cost
}

// ── Disponibilité de l'option « avec batterie » ───────────────────────────────
// Règle dure (alignée moteur PDF) : une option ne se rend jamais sans onduleur.
// Composer des hybrides en parallèle est raisonnable jusqu'à MAX_HYBRID_UNITS.
export const MAX_HYBRID_UNITS = 8

export function avecBatterieAvailability(lines, produits, kwp) {
  const hasHyb = lines.some(l =>
    isHybridInverter(l.designation) && parseFloat(l.quantite) > 0)
  const hasBat = lines.some(l =>
    isBattery(l.designation) && parseFloat(l.quantite) > 0)
  const hasRes = lines.some(l =>
    isReseauInverter(l.designation) && parseFloat(l.quantite) > 0)
  if (hasHyb && hasBat) return { available: true, batterieDifferee: false }
  // BAT-DIFF (fondateur, 17/09/2026) — même règle que le noyau
  // (`utils.options.familles_servables`, testée là-bas et ici par
  // `solar.avecBatterieAvailability.test.jsx`) : un hybride FACE à un réseau sert
  // l'option « avec » même sans batterie chiffrée (le client l'ajoutera plus
  // tard). Le document la nomme « Hybride, batterie plus tard » et calcule
  // ses économies sans stockage. Un hybride SEUL reste mono-option (Z1).
  if (hasHyb && hasRes) return { available: true, batterieDifferee: true }
  // Diagnostic : le plus gros hybride du stock suffit-il, même composé ?
  const maxKw = Math.max(0, ...produits
    .filter(p => isHybridInverter(p.nom))
    .map(p => parseKw(p.nom) || 0))
  const unitsNeeded = maxKw > 0 ? Math.ceil((kwp || 0) / maxKw) : Infinity
  let reason
  if (!hasHyb && maxKw > 0 && unitsNeeded > MAX_HYBRID_UNITS) {
    reason = `puissance requise ${kwp} kWc — il faudrait ${unitsNeeded} onduleurs `
      + `hybrides de ${maxKw} kW en parallèle (déraisonnable au-delà de ${MAX_HYBRID_UNITS})`
  } else if (!hasHyb) {
    reason = 'aucun onduleur hybride dans la liste'
  } else {
    reason = 'aucune batterie dans la liste'
  }
  return { available: false, reason }
}
