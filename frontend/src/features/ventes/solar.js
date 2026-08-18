// Solar math + catalogue auto-fill, ported 1:1 from RedaSolar/devis-simulator
// (constants.py, roi_router.py, autofill.py / autofill_router.py, app.js).
// The simulator is the source of truth: prices are handled in TTC (like the
// simulator UI) and only converted to HT at save time. Pure functions, no I/O.
// The premium PDF engine computes its own figures server-side — never fed here.

import { formatMAD } from '../../lib/format.js'

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

// Autoconsommation par défaut selon le type d'installation
export const DAY_USAGE_DEFAULTS = {
  'Résidentielle': 60,
  'Commerciale': 80,
  'Industrielle': 80,
  'Agricole': 100,
}

// ── QX44 — Étude COMMERCIALE par catégorie ────────────────────────────────────
// Chaque marché commercial a une signature de consommation DIURNE distincte : un
// bureau consomme le jour (autoconsommation élevée), un hôtel/restaurant a un pic
// du soir. Le « day-share » (part de la conso pendant les heures solaires)
// remplace l'unique DAY_USAGE_DEFAULTS['Commerciale']=80 par une table par
// catégorie. SOURCE = archétype de charge documenté ; EST. = estimation marché à
// vérifier fondateur (QXG6 durcira ces valeurs). Réglable société (override).
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

// Day-share (%) par catégorie — part de la consommation consommée en journée.
export const COMMERCIAL_DAY_SHARE = {
  bureau: 80,      // SOURCE archétype bureau : conso ~9h-18h alignée au solaire
  ecole: 85,       // SOURCE école (période scolaire) : forte conso diurne
  commerce: 75,    // EST. supermarché : froid + éclairage jour, pic soir modéré
  sante: 70,       // EST. clinique : diurne dominant, garde de nuit résiduelle
  restaurant: 70,  // EST. restaurant : services midi + soir → part solaire moyenne
  hammam: 65,      // EST. hammam/spa/gym : chauffe jour + soirée
  hotel: 55,       // EST. hôtel : occupation soir/nuit, base diurne (clim/piscine)
  froid: 50,       // EST. entrepôt froid : base 24 h, part solaire ≈ heures de jour
  boulangerie: 45, // EST. boulangerie : cuisson souvent nocturne → faible part solaire
  autre: 80,       // repli = ancien défaut Commerciale
}
export const COMMERCIAL_DAY_SHARE_DEFAUT = 80

// Day-share effectif d'une catégorie (override société optionnel, borné 10-100).
export function commercialDayShare(category, { override } = {}) {
  if (override && typeof override === 'object' && override[category] != null) {
    const v = parseFloat(override[category])
    if (Number.isFinite(v) && v > 0) return Math.min(100, Math.max(10, v))
  }
  return COMMERCIAL_DAY_SHARE[category] ?? COMMERCIAL_DAY_SHARE_DEFAUT
}

// Questions 2-4 par catégorie (recherche 2026-07-16). key = clé snake_case
// stockée dans etude_params (et acceptée par le webhook QX51). type =
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

// 8 panneaux par tranche de 900 MAD de facture hiver. Le ratio est éditable
// (Paramètres → Avancé) ; sans argument il garde le défaut historique (8).
// NB : depuis la règle fondateur du 18/08 le dimensionnement passe par les kWc
// (`estimerKwcDepuisFacture` ci-dessous) ; cette fonction reste pour les appels
// historiques et les paramétrages explicites en nombre de panneaux.
export function estimerPanneaux(factureHiver, perTranche = 8) {
  const n = Number(perTranche)
  return Math.floor(factureHiver / 900) * (Number.isFinite(n) && n > 0 ? n : 8)
}

// ── Règle de dimensionnement fondateur (18/08) ───────────────────────────────
// 1. Une installation se vend par PALIERS de 5 kWc — jamais une taille
//    intermédiaire (5, 10, 15, 20 …).
// 2. Le besoin se lit sur la facture d'hiver : 5 kWc par tranche de 900 MAD.
// 3. La taille RETENUE est celle qui minimise le retour sur investissement
//    (`optimalKwcByPayback`), pas la plus grosse qui rentre sur le toit.
export const KWC_STEP = 5
export const MAD_PAR_PALIER = 900

// ── Métrés de câble (règle fondateur 18/08) ──────────────────────────────────
// Câble solaire DC 6 mm² : 60 m par palier de 5 kWc (strictement proportionnel).
// Câble de terre AC 6 mm² : 25 m de base + 15 m par palier de 5 kWc — soit 40 m
// pour 5 kWc et 55 m pour 10 kWc, les deux cotes données par le fondateur.
export const CABLE_DC_M_PAR_PALIER = 60
export const CABLE_TERRE_M_BASE = 25
export const CABLE_TERRE_M_PAR_PALIER = 15

/** Longueur de câble solaire DC (m) pour `paliers` blocs de 5 kWc. */
export function metreCableDc(paliers) {
  const n = Math.max(1, Math.round(Number(paliers) || 0))
  return n * CABLE_DC_M_PAR_PALIER
}

/** Longueur de câble de terre AC (m) pour `paliers` blocs de 5 kWc. */
export function metreCableTerre(paliers) {
  const n = Math.max(1, Math.round(Number(paliers) || 0))
  return CABLE_TERRE_M_BASE + n * CABLE_TERRE_M_PAR_PALIER
}

/** Besoin en kWc lu sur la facture d'hiver : 5 kWc par tranche de 900 MAD. */
export function estimerKwcDepuisFacture(factureHiver, { step = KWC_STEP, madParPalier = MAD_PAR_PALIER } = {}) {
  const f = Number(factureHiver)
  if (!Number.isFinite(f) || f <= 0) return 0
  const pas = (Number.isFinite(Number(step)) && Number(step) > 0) ? Number(step) : KWC_STEP
  const tranche = (Number.isFinite(Number(madParPalier)) && Number(madParPalier) > 0) ? Number(madParPalier) : MAD_PAR_PALIER
  return Math.floor(f / tranche) * pas
}

/** Ramène une taille quelconque au PALIER de 5 kWc le plus proche (jamais 0). */
export function arrondirAuPasKwc(kwc, step = KWC_STEP) {
  const k = Number(kwc)
  const pas = (Number.isFinite(Number(step)) && Number(step) > 0) ? Number(step) : KWC_STEP
  if (!Number.isFinite(k) || k <= 0) return pas
  return Math.max(pas, Math.round(k / pas) * pas)
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
export const INVERTER_REPLACE_YEAR = 12
export const INVERTER_REPLACE_FRACTION = 0.08

export function computeCashflowPayback(investment, economieAnnee1, { battery = false } = {}) {
  const inv = parseFloat(investment) || 0
  const base = parseFloat(economieAnnee1) || 0
  if (base <= 0 || inv <= 0) {
    return { paybackYears: null, cumulative: [], netGain: 0, years: CASHFLOW_YEARS }
  }
  const cumulative = []
  let cumul = -inv
  let payback = null
  let prev = -inv
  for (let y = 1; y <= CASHFLOW_YEARS; y++) {
    const prodFactor = (1 - PANEL_DEGRADATION) ** (y - 1)
    const tarifFactor = (1 + TARIFF_ESCALATION) ** (y - 1)
    let yearSaving = base * prodFactor * tarifFactor
    if (battery) yearSaving *= BATTERY_ROUNDTRIP
    let yearCf = yearSaving
    if (INVERTER_REPLACE_YEAR && y === INVERTER_REPLACE_YEAR) {
      yearCf -= inv * INVERTER_REPLACE_FRACTION
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
  if (payback === null) payback = CASHFLOW_YEARS
  return { paybackYears: payback, cumulative, netGain: Math.round(cumul), years: CASHFLOW_YEARS }
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
    // puis valorisé au tarif. Miroir de la dérivation du taux côté PDF.
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
  let savingsModel = 'estimation'
  let factureSans = null, factureAvecSans = null, factureAvecAvec = null
  if (productionAnnuelle > 0 && consoAnnuelleKwh > 0 && utility) {
    const tbSans = twoBillsSavings(productionCanonique, consoAnnuelleKwh, AUTOCONSO_SANS, utility)
    const tbAvec = twoBillsSavings(productionCanonique, consoAnnuelleKwh, autoconsoAvec, utility)
    if (tbSans && tbAvec) {
      savingsModel = 'factures'
      autoconsoSansEff = AUTOCONSO_SANS
      autoconsoAvecEff = autoconsoAvec
      ecoAnnuelleSans = tbSans.economie
      ecoAnnuelleAvec = tbAvec.economie
      factureSans = tbSans.factureSans
      factureAvecSans = tbSans.factureAvec
      factureAvecAvec = tbAvec.factureAvec
    }
  }

  // QX39 — payback par croisement du cumul du cashflow 25 ans (miroir backend),
  // pas un ratio année-1 : écran/PDF/proposition affichent le MÊME payback.
  const cfSans = computeCashflowPayback(totalSans, ecoAnnuelleSans)
  const cfAvec = computeCashflowPayback(totalAvec, ecoAnnuelleAvec, { battery: true })
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

// ── QF4/QF5 — Modèle « deux factures » par tranche (MIROIR JS) ───────────────
// Port fidèle de backend apps/ventes/quote_engine/pricing.py : mêmes tables de
// tranches, mêmes formules. Permet à l'écran d'afficher EXACTEMENT le même
// calcul que le PDF (facture sans vs avec solaire, économie réelle) au lieu
// d'une approximation production × autoconsommation × prix moyen.
//
// QF5 — divergence de tarif corrigée : `KWH_PRICE` (1.75) reste le défaut
// historique de `computeROI` (aligné sur CompanyProfile.onee_tarif_kwh, le
// repli RÉEL en pratique) ; `FALLBACK_KWH_PRICE` (1.20) mirror l'ultime repli
// `_FALLBACK_KWH_PRICE` de pricing.py, utilisé UNIQUEMENT quand ni tranche ni
// tarif société ne sont disponibles (repli en cascade, comme le backend).
export const FALLBACK_KWH_PRICE = 1.20 // MAD/kWh — miroir pricing.py._FALLBACK_KWH_PRICE

// Tables de tranches (miroir pricing.py — mêmes valeurs, mêmes plafonds).
// Format : [plafond_kWh_mensuel | null, prix_MAD_kWh_TTC].
// QX38 — plafonds cumulatifs alignés sur les vraies bandes ONEE (0-100 /
// 101-250 / 251-400 / >400), miroir EXACT de pricing.py ONEE_TRANCHES. Prix
// inchangés ; seuls les plafonds 150/200 → 250/400 sont corrigés (ils
// contredisaient leurs libellés et sous-tarifaient les foyers 150-400 kWh/mois).
export const ONEE_TRANCHES = [
  [100, 0.9010],
  [250, 1.0258],
  [400, 1.2515],
  [null, 1.4017],
]
export const LYDEC_TRANCHES = [
  [100, 0.9500],
  [200, 1.1500],
  [null, 1.4500],
]
export const REDAL_TRANCHES = [
  [100, 0.9300],
  [200, 1.1200],
  [null, 1.4200],
]
export const UTILITY_TABLES = {
  onee: ONEE_TRANCHES, lydec: LYDEC_TRANCHES, redal: REDAL_TRANCHES,
}
export const APPROX_UTILITIES = new Set(['lydec', 'redal'])

function resolveTranches(utility, tranchesOverride) {
  if (tranchesOverride && tranchesOverride.length) return { table: tranchesOverride, approx: false }
  const key = (utility || '').toLowerCase()
  if (key && UTILITY_TABLES[key]) return { table: UTILITY_TABLES[key], approx: APPROX_UTILITIES.has(key) }
  return { table: null, approx: false }
}

// Facture mensuelle TTC (MAD) d'une consommation, valorisée PAR TRANCHE
// (barème progressif) — miroir _monthly_bill_from_kwh.
export function monthlyBillFromKwh(kwhMensuel, tranches) {
  if (!(kwhMensuel > 0)) return 0
  let remaining = kwhMensuel
  let prevCeiling = 0
  let totalCost = 0
  for (const [ceiling, price] of tranches) {
    if (ceiling == null) { totalCost += remaining * price; remaining = 0; break }
    const width = ceiling - prevCeiling
    const consumed = Math.min(remaining, width)
    totalCost += consumed * price
    remaining -= consumed
    prevCeiling = ceiling
    if (remaining <= 0) break
  }
  if (remaining > 0) totalCost += remaining * tranches[tranches.length - 1][1]
  return totalCost
}

// QF1 — inverse du barème progressif : facture mensuelle (MAD TTC) → kWh/mois.
// Miroir kwh_from_bill. Retourne { kwhMensuel, approximatif, estimation }.
export function kwhFromBill(billMad, utility, tranchesOverride) {
  const bill = parseFloat(billMad) || 0
  if (bill <= 0) return { kwhMensuel: 0, approximatif: false, estimation: true }
  const { table, approx } = resolveTranches(utility, tranchesOverride)
  if (!table) {
    return { kwhMensuel: Math.round((bill / FALLBACK_KWH_PRICE) * 10) / 10, approximatif: true, estimation: true }
  }
  let prevCeiling = 0
  let costSoFar = 0
  let kwh = null
  for (const [ceiling, price] of table) {
    if (ceiling == null) { kwh = prevCeiling + (bill - costSoFar) / price; break }
    const trancheCost = (ceiling - prevCeiling) * price
    if (costSoFar + trancheCost >= bill) { kwh = prevCeiling + (bill - costSoFar) / price; break }
    costSoFar += trancheCost
    prevCeiling = ceiling
  }
  if (kwh == null) kwh = prevCeiling + (bill - costSoFar) / table[table.length - 1][1]
  return { kwhMensuel: Math.round(kwh * 10) / 10, approximatif: approx, estimation: false }
}

// QF2 — modèle « deux factures » : économie = facture_sans − facture_avec,
// valorisée par tranche (self-consumption-first, loi 82-21). Miroir
// two_bills_savings. Retourne null quand une vraie donnée manque (l'appelant
// dégrade alors vers l'estimation, jamais un chiffre inventé).
export function twoBillsSavings(productionKwh, consoAnnuelleKwh, autoconsoRatio, utility, tranchesOverride) {
  const { table } = resolveTranches(utility, tranchesOverride)
  if (!table) return null
  const conso = parseFloat(consoAnnuelleKwh) || 0
  const prod = parseFloat(productionKwh) || 0
  const ratio = parseFloat(autoconsoRatio) || 0
  if (conso <= 0 || prod <= 0 || ratio <= 0) return null
  const factureSans = Math.round(monthlyBillFromKwh(conso / 12, table) * 12)
  const autoconsoKwh = Math.min(prod * ratio, conso)
  const residuel = Math.max(0, conso - autoconsoKwh)
  const factureAvec = Math.round(monthlyBillFromKwh(residuel / 12, table) * 12)
  return {
    factureSans, factureAvec,
    economie: Math.max(0, factureSans - factureAvec),
    autoconsoKwh: Math.round(autoconsoKwh),
  }
}

// ── Classification des lignes/produits (mêmes mots-clés que le moteur PDF) ───
const _norm = (s) =>
  (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const isBattery = (d) => _norm(d).includes('batterie')
export const isHybridInverter = (d) => _norm(d).includes('onduleur') && _norm(d).includes('hybride')
export const isReseauInverter = (d) => {
  const n = _norm(d)
  return n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))
}
export const isPanel = (d) => _norm(d).includes('panneau')

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
export function plageBatterieOnduleur(produit) {
  const plage = produit?.specs_solaire?.plage_batterie_v
  if (!Array.isArray(plage) || plage.length !== 2) return null
  const bas = Number(plage[0]); const haut = Number(plage[1])
  if (!Number.isFinite(bas) || !Number.isFinite(haut)) return null
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
export function onduleurSpecsManquantes(produit) {
  const manquantes = produit?.specs_solaire?.manquantes
  return Array.isArray(manquantes) ? manquantes : []
}

export const onduleurComplet = (produit) =>
  onduleurSpecsManquantes(produit).length === 0

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

// La désignation tapée correspond-elle encore au produit choisi du stock ?
// (la frappe libre peut diverger du nom produit ; on le signale sans bloquer).
export function designationMatchesProduct(designation, produit) {
  if (!produit) return true
  const d = _norm(designation)
  const n = _norm(produit.nom)
  if (!d || !n) return true
  if (d === n) return true
  // Tolérance : l'une contient l'autre, ou la classification est identique.
  if (n.includes(d) || d.includes(n)) return true
  const cd = classifyProduct(designation)
  const cn = classifyProduct(produit.nom)
  return cd != null && cd === cn
}

// Nombre de panneaux pour une taille cible (kWc) à la puissance panneau donnée.
// Utilisé pour préremplir depuis lead.taille_souhaitee_kwc. Au moins 1 panneau.
export function panneauxPourKwc(kwc, panelW = 710) {
  const k = parseFloat(kwc) || 0
  const w = parseFloat(panelW) || 710
  if (!(k > 0) || !(w > 0)) return 0
  return Math.max(1, Math.round(k * 1000 / w))
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
  // mêmes mots-clés que le moteur PDF : un onduleur sans « réseau/injection »
  // (ex. micro-onduleur) n'est pas classé et reste sélectionnable à la main
  if (n.includes('onduleur') && (n.includes('reseau') || n.includes('injection'))) {
    return 'onduleur_reseau'
  }
  if (n.includes('panneau')) return 'panneau'
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
export function ttcFromHt(prixVenteHt, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + (parseFloat(tauxTva) || TVA_STANDARD_DEFAUT) / 100
  return Math.round((parseFloat(prixVenteHt) || 0) * factor)
}

// Taux TVA d'un produit (réforme 2024–2026 : 10 % panneaux PV, 20 % le reste).
// DC7 — `Produit.tva` est la source AUTORITAIRE par ligne ; on la prend telle
// quelle quand elle est renseignée. DC6 — le repli n'est plus 20 en dur : il
// suit le taux standard de la société (tvaStandard, Paramètres), défaut 20.
export function tauxTvaOf(produit, tvaStandard) {
  const t = parseFloat(produit?.tva)
  if (Number.isFinite(t) && t > 0) return t
  const std = Number(tvaStandard) > 0 ? Number(tvaStandard) : TVA_STANDARD_DEFAUT
  return std
}

// Conversion inverse au moment de l'enregistrement : le modèle stocke des
// prix HT à 2 décimales. Pour tout TTC saisi à la dirham près, l'aller-retour
// TTC → HT(2 déc.) → TTC réaffiché redonne exactement la valeur tapée.
export function htFromTtc(ttc, tauxTva = TVA_STANDARD_DEFAUT) {
  const factor = 1 + (parseFloat(tauxTva) || TVA_STANDARD_DEFAUT) / 100
  return ((parseFloat(ttc) || 0) / factor).toFixed(2)
}

// Capacité batterie totale depuis les lignes (port de app.js — défaut 5 kWh/ligne)
export function batteryKwhFromLines(lines) {
  return lines.reduce((sum, l) => {
    if (!isBattery(l.designation)) return sum
    const qty = parseFloat(l.quantite) || 0
    return sum + qty * (parseKwh(l.designation) ?? 5.0)
  }, 0)
}

// ── Totaux par option, TTC (port exact de updateTotals de app.js) ────────────
// Option 1 SANS batterie : exclut Batterie + Onduleur hybride.
// Option 2 AVEC batterie : exclut Onduleur réseau.
export function optionTotalsTTC(lines, discountPct) {
  const ttc = (l) => (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
  const totalSansBrut = lines
    .filter(l => !isBattery(l.designation) && !isHybridInverter(l.designation))
    .reduce((s, l) => s + ttc(l), 0)
  const totalAvecBrut = lines
    .filter(l => !isReseauInverter(l.designation))
    .reduce((s, l) => s + ttc(l), 0)

  const pct = parseFloat(discountPct) || 0
  const totalSans = pct > 0 ? Math.round(totalSansBrut * (1 - pct / 100)) : totalSansBrut
  const totalAvec = pct > 0 ? Math.round(totalAvecBrut * (1 - pct / 100)) : totalAvecBrut
  return { totalSansBrut, totalAvecBrut, totalSans, totalAvec }
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
export function multiPropertyPreviewTTC(lines, { nombreProprietes, discountPct } = {}) {
  const n = parseInt(nombreProprietes, 10)
  if (Number.isFinite(n) && n > 1) {
    const { totalSans, totalAvec, totalSansBrut, totalAvecBrut } = optionTotalsTTC(lines, discountPct)
    return {
      mode: 'multiplicateur',
      nombreProprietes: n,
      totalUnitaireSans: totalSans, totalUnitaireAvec: totalAvec,
      totalMultiSans: Math.round(totalSans * n), totalMultiAvec: Math.round(totalAvec * n),
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
  ['panneau', 'Panneaux'],
  ['batterie', 'Batterie'],
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

export function groupProduitsByCategory(produits) {
  const buckets = new Map(PRODUCT_CATEGORIES.map(([key]) => [key, []]))
  const autres = []
  for (const p of produits) {
    let type = classifyProduct(p.nom)
    if (type === 'structure') {
      type = _norm(p.nom).includes('alu') ? 'structure_alu' : 'structure_acier'
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

// ── Indexation par type des produits du stock ─────────────────────────────────
function indexProduits(produits) {
  const byType = {}
  for (const p of produits) {
    const type = classifyProduct(p.nom)
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
export function defaultProductLines(produits) {
  const byType = indexProduits(produits)
  const first = (type) => (byType[type] ?? [])[0] ?? null
  const exactOr = (type, needle) => {
    const pool = byType[type] ?? []
    return pool.find(p => _norm(p.nom).includes(needle)) ?? null
  }
  const row = (p, designation, quantite) =>
    p ? lineFrom(p, quantite) : placeholder(designation, quantite)

  return [
    placeholder('Onduleur réseau', 1),
    placeholder('Onduleur hybride', 1),
    row(first('smart_meter'), 'Smart Meter', 0),
    row(first('wifi_dongle'), 'Wifi Dongle', 0),
    placeholder('Panneaux', 0),
    placeholder('Batterie', 1),
    placeholder('Batterie', 0),
    row(exactOr('structure', 'acier'), 'Structures acier', 0),
    row(exactOr('structure', 'alu'), 'Structures aluminium', 0),
    row(first('socle'), 'Socles', 0),
    row(first('accessoires'), 'Accessoires', 1),
    row(first('tableau'), 'Tableau De Protection AC/DC', 1),
    row(first('installation'), 'Installation', 1),
    row(first('transport'), 'Transport', 1),
    row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 1),
  ]
}

// ── Auto-remplissage (port exact de auto_fill_from_power + autofill_router) ───
// Retourne la table complète dans l'ordre canonique du simulateur, lignes à
// quantité nulle comprises (elles s'affichent mais ne sont pas enregistrées).
export function autoFillLines(produits, { kwp, panelW, structureType, nbPanneaux: nbOverride }) {
  if (!kwp || kwp <= 0) return []
  const byType = indexProduits(produits)

  // QX19 — nombre de panneaux : override explicite (dérivé d'une taille kWc
  // souhaitée) sinon dérivé de la puissance. Le kWc RÉEL est recalculé plus bas
  // depuis la puissance du panneau EFFECTIVEMENT retenu (jamais une divergence
  // silencieuse 550W-pour-710W).
  const nbPanneaux = (Number(nbOverride) > 0)
    ? Math.round(Number(nbOverride))
    : Math.max(1, Math.round(kwp * 1000 / panelW))
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

  const reseau = pickInverter(byType.onduleur_reseau)
  const hybride = pickInverter(byType.onduleur_hybride)

  // Panneaux : wattage saisi (défaut 710 → Canadien Solar 710 du catalogue)
  const panels = (byType.panneau ?? [])
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
  let nb10 = Math.floor(target / 10)
  let nb5 = (target % 10) >= 5 ? 1 : 0
  // PVOND — GARDE BATTERIE PILOTÉ PAR LA DONNÉE (remplace le garde par mot-clé
  // PVG4 ; miroir EXACT de `_batterie_compatible` côté backend
  // apps/ventes/services.py). Une batterie n'entre au vivier que si sa TENSION
  // NOMINALE tombe dans la PLAGE BATTERIE déclarée par l'onduleur HYBRIDE
  // retenu ci-dessus — c'est la vraie règle électrique, pas un nom de produit.
  // Repli intégral sur le mot-clé « haute tension » dès qu'une des deux données
  // manque : un catalogue non renseigné se comporte exactement comme hier.
  // L'exclusion se fait AVANT l'appariement par capacité 5/10 kWh ; une
  // batterie écartée reste sélectionnable à la main.
  const plageBatterie = plageBatterieOnduleur(hybride?.p)
  const bats = (byType.batterie ?? [])
    .filter(p => batterieCompatible(p, plageBatterie))
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
  const bat5 = batPool.find(x => x.cap === 5)
  const bat10 = batPool.find(x => x.cap === 10)
  if (!bat10 && bat5 && nb10 > 0) {
    // pas de module 10 kWh au catalogue → tout en modules 5 kWh
    nb5 = Math.max(1, Math.round(target / 5))
    nb10 = 0
  }

  // Structures : type choisi par radio, 1 par panneau (prix catalogue)
  const structures = byType.structure ?? []
  const wanted = structureType === 'aluminium' ? 'alu' : 'acier'
  const other = structureType === 'aluminium' ? 'acier' : 'alu'
  const structChosen = structures.find(p => _norm(p.nom).includes(wanted)) ?? null
  const structOther = structures.find(p => _norm(p.nom).includes(other)) ?? null

  // Accessoires / Tableau / Installation : prix indexés sur la puissance
  // (blocs de 5 kWc), exactement comme auto_fill_from_power. TTC.
  const blocks = Math.max(1, Math.round(kwp / 5))
  const prixAccessoires = blocks * 1000
  const prixTableau = blocks * 1500
  const prixInstallation = (blocks + 1) * 2400

  // QF8 — Smart Meter + Clé Wifi : UNIQUEMENT quand l'onduleur retenu (réseau
  // OU hybride) est de marque Huawei (miroir du garde `info_hw` de l'ancien
  // simulateur Python). Un onduleur Deye — ou toute autre marque — ne les
  // ajoute jamais : qté 0. Vérifie `marque` (catalogue seedé) ET le nom (les
  // fixtures/anciens produits sans champ `marque` structuré) pour ne rien
  // manquer.
  const isHuawei = (p) => !!p && (
    _norm(p.marque).includes('huawei') || _norm(p.nom).includes('huawei'))
  const huaweiRetenu = isHuawei(reseau?.p) || isHuawei(hybride?.p)
  const smQty = huaweiRetenu ? 1 : 0
  const wifiQty = huaweiRetenu ? 1 : 0

  const first = (type) => (byType[type] ?? [])[0] ?? null
  const row = (p, designation, quantite, ttcOverride = null) =>
    p ? lineFrom(p, quantite, ttcOverride)
      : { ...placeholder(designation, quantite), prix_unit_ttc: ttcOverride ?? 0 }

  // Câbles : on préfère le NEXANS explicitement (marque confirmée fondateur),
  // sinon le premier câble du type QUI PORTE UN PRIX.
  const chiffre = (p) => !!p && parseFloat(p.prix_vente) > 0
  const pickCable = (type) => {
    const pool = (byType[type] ?? []).filter(chiffre)
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

  const lignes = [
    row(reseau?.p ?? null, 'Onduleur réseau', reseau ? inverterQty(reseau.kw) : 1),
    row(hybride?.p ?? null, 'Onduleur hybride', hybride ? Math.max(1, inverterQty(hybride.kw)) : 1),
    row(first('smart_meter'), 'Smart Meter', smQty),
    row(first('wifi_dongle'), 'Wifi Dongle', wifiQty),
    row(panel?.p ?? null, 'Panneaux', nbPanneaux),
    row(bat5?.p ?? null, 'Batterie', nb5),
    row(bat10?.p ?? null, 'Batterie', nb10),
    acierRow,
    aluRow,
    row(first('socle'), 'Socles', nbPanneaux * 2),
    // Câbles Nexans 6 mm² au mètre (règle fondateur 18/08). On ne retient qu'un
    // câble RÉELLEMENT chiffré : un produit sans prix n'entre jamais dans une
    // auto-composition (même patron que « prix à renseigner »).
    row(cableDc, 'Câble solaire Nexans 6 mm² (au mètre)', cableDc ? metreCableDc(blocks) : 0),
    row(cableTerre, 'Câble de terre Nexans 6 mm² (au mètre)', cableTerre ? metreCableTerre(blocks) : 0),
    row(first('accessoires'), 'Accessoires', 1, prixAccessoires),
    row(first('tableau'), 'Tableau De Protection AC/DC', 1, prixTableau),
    row(first('installation'), 'Installation', 1, prixInstallation),
    row(first('transport'), 'Transport', 1),
    row(first('suivi'), 'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', 0),
  ]
  // QX19 — puissance du panneau EFFECTIVEMENT retenu (peut différer de panelW
  // quand le catalogue n'a pas exactement panelW → substitution la plus proche)
  // + nb de panneaux : l'écran recalcule le kWc RÉEL depuis ces valeurs plutôt
  // que d'afficher un kWc théorique divergent. Métadonnées portées sur le
  // tableau (les consommateurs qui itèrent les lignes ne les voient pas).
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
  return lignes
}

// ── Taille OPTIMALE par retour sur investissement (règle fondateur 18/08) ────
// On ne vend plus « la plus grosse installation qui rentre » ni « la taille lue
// sur la facture » : on BALAIE les paliers de 5 kWc, on chiffre CHAQUE palier
// avec le catalogue réel (`autoFillLines` — jamais un barème au kWc inventé,
// il n'en existe aucun), on calcule le payback 25 ans de chacun
// (`computeCashflowPayback`, le MÊME que l'écran, le PDF et la proposition) et
// on garde le palier dont le payback est le plus court.
//
// Pourquoi un vrai optimum existe : en descendant, les coûts fixes (onduleur,
// structure, pose) se diluent moins bien ; en montant, la production dépasse
// l'autoconsommation et mord sur des tranches ONEE moins chères. Les deux
// forces se croisent — c'est ce croisement qu'on cherche.
//
// `besoinKwc` (facture d'hiver, 900 MAD → 5 kWc) PLAFONNE le balayage : on ne
// propose JAMAIS plus gros que le besoin lu sur la facture. C'est volontaire —
// le modèle d'économie hérité du simulateur ne sature pas à la consommation
// réelle, donc sans ce plafond « payback minimal » dériverait mécaniquement
// vers le haut et sur-vendrait le client. L'optimisation joue donc SOUS le
// besoin : elle retient un palier plus petit quand il rembourse plus vite.
// `maxKwc` (surface de toit réelle) resserre encore la borne.
//
// Retourne { kwcOptimal, nbPanneaux, paliers[] } — `paliers` porte le détail
// chiffré de chaque candidat pour que l'écran puisse JUSTIFIER le choix.
export function optimalKwcByPayback({
  produits, factures, dayUsagePct, panelW = 710, structureType,
  discountPct, kwhPrice, efficiency, productible, consoAnnuelleKwh, utility,
  besoinKwc, maxKwc, avecBatterie = false, step = KWC_STEP,
}) {
  const pas = (Number.isFinite(Number(step)) && Number(step) > 0) ? Number(step) : KWC_STEP
  const besoin = Number(besoinKwc) > 0 ? Number(besoinKwc) : 0
  // Plafond : le besoin lui-même (jamais au-dessus), resserré par le toit.
  let plafond = besoin > 0 ? arrondirAuPasKwc(besoin, pas) : pas
  if (Number(maxKwc) > 0) plafond = Math.min(plafond, Math.floor(Number(maxKwc) / pas) * pas)
  plafond = Math.max(pas, plafond)

  const paliers = []
  for (let k = pas; k <= plafond + 1e-9; k += pas) {
    const lignes = autoFillLines(produits, { kwp: k, panelW, structureType })
    if (!lignes || !lignes.length) continue
    const { totalSans, totalAvec } = optionTotalsTTC(lignes, discountPct)
    const roi = computeROI({
      kwp: lignes.kwcReel || k,
      factures, dayUsagePct, totalSans, totalAvec,
      batteryKwh: batteryKwhFromLines(lignes),
      kwhPrice, efficiency, consoAnnuelleKwh, utility, productible,
    })
    const payback = avecBatterie ? roi.payback_avec : roi.payback_sans
    paliers.push({
      kwc: k,
      kwcReel: lignes.kwcReel || k,
      nbPanneaux: lignes.nbPanneaux,
      totalTtc: avecBatterie ? totalAvec : totalSans,
      economieAnnuelle: avecBatterie ? roi.eco_annuelle_avec : roi.eco_annuelle_sans,
      payback,
    })
  }

  const chiffrables = paliers.filter(p => Number.isFinite(p.payback) && p.payback > 0)
  if (!chiffrables.length) {
    // Aucun palier chiffrable (catalogue incomplet, pas de facture) : on retombe
    // sur le besoin arrondi au palier — jamais sur un chiffre inventé.
    const repli = besoin > 0 ? arrondirAuPasKwc(besoin, pas) : pas
    return { kwcOptimal: repli, nbPanneaux: panneauxPourKwc(repli, panelW), paliers }
  }
  // Payback le plus court ; à égalité stricte on garde le palier le PLUS PETIT
  // (même retour, moins d'argent immobilisé chez le client).
  const meilleur = chiffrables.reduce((best, p) => (
    p.payback < best.payback - 1e-9 ? p : best
  ), chiffrables[0])
  return {
    kwcOptimal: meilleur.kwc,
    nbPanneaux: meilleur.nbPanneaux ?? panneauxPourKwc(meilleur.kwc, panelW),
    paliers,
  }
}

// ══ Multi-marchés (2026-06) ═══════════════════════════════════════════════════

// ── Étude industrielle / commerciale (autoconsommation) ──────────────────────
// DC3 — kwhPrice/efficiency sont threadés EXACTEMENT comme computeROI : le tarif
// ONEE et le rendement de la société (Paramètres → Avancé) pilotent l'étude à
// l'écran, plus seulement le PDF. Sans valeur → constantes historiques
// (parité simulateur garantie).
// ── QX50 — Injection 82-21 (miroir de quote_engine/constants_82_21.py) ────────
// Décret 82-21 (2-25-100, BO 09/03/2026, en vigueur 09/06/2026). TOUTES ces
// valeurs sont ESTIMÉES (recherche 2026-07-16) et à VÉRIFIER FONDATEUR (QXG6) :
// elles pilotent une ligne OFF par défaut, activée devis par devis, et ne
// s'affichent JAMAIS sans la mention réglementaire INJECTION_82_21.MENTION.
export const INJECTION_82_21 = {
  TARIF_POINTE: 0.21,        // DH/kWh — à vérifier fondateur
  TARIF_HORS_POINTE: 0.18,   // DH/kWh — à vérifier fondateur
  FRAIS_RESEAU_C1: 6.07,     // c/kWh — à vérifier fondateur
  FRAIS_RESEAU_C2: 6.38,     // c/kWh — à vérifier fondateur
  PLAFOND_PCT: 20,           // % de la production — décret en révision (à vérifier)
  MENTION: 'Tarif ANRE 03/2026-02/2027, plafond en révision',
}
INJECTION_82_21.FRAIS_RESEAU_DH = (INJECTION_82_21.FRAIS_RESEAU_C1 + INJECTION_82_21.FRAIS_RESEAU_C2) / 100

// Tarif NET (rachat − frais réseau), DH/kWh, jamais négatif. Injection diurne →
// tarif HORS POINTE net par défaut (prudent, jamais la pointe sans stockage).
export function netTarif8221(pointe = false) {
  const base = pointe ? INJECTION_82_21.TARIF_POINTE : INJECTION_82_21.TARIF_HORS_POINTE
  return Math.max(0, base - INJECTION_82_21.FRAIS_RESEAU_DH)
}

// Surplus injectable (kWh) plafonné à 20 % de la prod + sa valeur nette (DH).
// Retourne { kwh, dh }, ≥ 0, arrondis. Miroir de injection_annuelle().
export function injection8221(productionKwh, autoconsommeKwh, pointe = false) {
  const prod = Math.max(0, parseFloat(productionKwh) || 0)
  const auto = Math.max(0, parseFloat(autoconsommeKwh) || 0)
  const surplus = Math.max(0, prod - auto)
  const plafond = prod * INJECTION_82_21.PLAFOND_PCT / 100
  const kwh = Math.min(surplus, plafond)
  const dh = kwh * netTarif8221(pointe)
  return { kwh: Math.round(kwh), dh: Math.round(dh) }
}

// ══ QXMT — Tarifs MOYENNE TENSION ONEE (raccordement MT, dossiers > 50 kW) ═══
// Miroir STRICT de quote_engine/constants_82_21.py `TARIF_MT_ONEE` — un test de
// parité backend (test_qx50_injection_82_21.py) échoue si l'un des deux dérive.
//
// RÈGLE FONDATEUR — ZÉRO CHIFFRE INVENTÉ (PLAN2 QXG6, contrainte « chaque
// constante tarifaire porte sa source en commentaire »). Une valeur n'apparaît
// ici QUE si une source OFFICIELLE ou de premier rang la publie (ONEE
// one.org.ma, Bulletin officiel, ministère de l'énergie, ANRE), avec sa source
// et sa date citées sur la ligne. Toute valeur non sourcée reste `null` :
// l'étude OMET alors le calcul correspondant (économies / payback) au lieu
// d'afficher un chiffre douteux. JAMAIS de placeholder chiffré, JAMAIS de
// reprise d'une estimation « ordre de grandeur » (le site porte un blend
// indicatif TARIF_MT_MAD_KWH = 1,15 dans apps/web/src/lib/estimatorPro.ts —
// explicitement une hypothèse, donc INUTILISABLE pour une étude chiffrée).
//
// SOURCE DES TROIS PRIX + DE LA PRIME (relevée ET vérifiée le 18/08/2026) :
//   ONEE — Branche Électricité, page officielle « Tarif Général (MT) »
//   https://www.one.org.ma/fr/pages/interne.asp?esp=1&id1=14&id2=114&t2=1
//   La page précise : « Les tarifs sont exprimés en dirhams TVA comprise
//   (TVA est de 18 %) ». Elle n'affiche NI date d'entrée en vigueur NI numéro
//   d'arrêté — d'où la mention de consultation portée par MENTION ci-dessous.
// NON RETENU volontairement : la page ONEE « Grands Comptes » sans tag de
// tension (494,09 DH/kVA ; 1,3645 / 0,9736 / 0,7131) est citée ailleurs comme
// « MT » mais ne porte aucun libellé de tension et vit dans l'arborescence
// THT/HT — ambiguë, donc écartée. Le TURD ANRE (5,92 c/kWh, décision
// n°02-25-TURD, BO n°7400 du 01/05/2025) est un tarif d'ACCÈS au réseau payé
// entre opérateurs, PAS un tarif de vente au client final : jamais mélangé ici.
export const TARIF_MT_ONEE = {
  // Redevance de consommation par poste horaire, DH/kWh TVA (18 %) comprise.
  // ONEE « Tarif Général (MT) », one.org.ma, consulté le 18/08/2026.
  POINTE: 1.4157,
  PLEINES: 1.0101,
  CREUSES: 0.7398,
  // Prime fixe / redevance de puissance, DH par kVA souscrit et par an.
  // Même source et même date. DÉLIBÉRÉMENT NON déduite des économies : le
  // solaire ne réduit pas la puissance souscrite, la compter en économie
  // gonflerait le gain. Exposée pour que personne n'ait à la réinventer.
  PRIME_PUISSANCE_DH_KVA_AN: 512.62,
  TVA_INCLUSE_PCT: 18,
  // Durées officielles des plages horaires (heures/jour). Elles serviraient à
  // répartir une consommation à profil plat quand le client ne fournit pas sa
  // propre répartition. La page MT ne les publie QUE dans un diagramme image
  // (non extractible) — plages MT à fournir par le fondateur (source
  // officielle introuvable au 18/08/2026). `null` = AUCUNE répartition par
  // défaut n'est inventée : le client doit saisir la sienne, sinon l'étude
  // OMET la valorisation. (Les seules plages publiées en clair sur one.org.ma
  // — 17h-22h etc. — appartiennent au tarif Optionnel « Super Pointe » THT/HT,
  // explicitement PAS à la MT : les transposer serait un chiffre inventé.)
  PLAGES_H: null,
  // Mention affichée avec TOUT chiffre issu de ce barème (jamais un chiffre nu).
  MENTION: 'Barème ONEE « Tarif Général (MT) », TVA 18 % comprise — '
    + 'one.org.ma, consulté le 18/08/2026 (la page ne publie pas de date '
    + "d'entrée en vigueur)",
}

// Le barème MT est-il exploitable ? true seulement si les TROIS postes horaires
// portent un prix > 0 sourcé. Tant que c'est false, l'étude MT omet toute
// valorisation monétaire plutôt que d'utiliser un chiffre de repli.
export function tarifMtDisponible() {
  return ['POINTE', 'PLEINES', 'CREUSES'].every((k) => {
    const v = Number(TARIF_MT_ONEE[k])
    return Number.isFinite(v) && v > 0
  })
}

// Répartition horaire du client `{ pointe, pleines, creuses }` (en %, saisie
// libre) → parts normalisées à 100 %. Retourne `null` si rien d'exploitable
// n'est saisi : les plages MT officielles n'étant pas publiées, AUCUNE
// répartition par défaut n'est inventée. Les valeurs non numériques ou
// négatives comptent pour 0 (la saisie de l'utilisateur n'est jamais rejetée
// ni corrigée à l'écran — seul le calcul les ignore).
export function normaliserRepartitionMt(repartition) {
  const part = (v) => {
    const n = parseFloat(v)
    return Number.isFinite(n) && n > 0 ? n : 0
  }
  const pointe = part(repartition?.pointe)
  const pleines = part(repartition?.pleines)
  const creuses = part(repartition?.creuses)
  const somme = pointe + pleines + creuses
  if (!(somme > 0)) return null
  const pct = (v) => Math.round((v / somme) * 1000) / 10
  return { pointe: pct(pointe), pleines: pct(pleines), creuses: pct(creuses) }
}

// Prix moyen pondéré (DH/kWh TTC) du barème MT pour une répartition horaire.
// Retourne `null` — jamais un nombre de repli — si le barème n'est pas sourcé
// ou si la répartition est absente/vide. C'est ce `null` qui fait OMETTRE le
// calcul dans l'étude plutôt que d'inventer un tarif.
export function tarifMtMoyen(repartition) {
  if (!tarifMtDisponible()) return null
  const parts = normaliserRepartitionMt(repartition)
  if (!parts) return null
  const moyen = (parts.pointe * TARIF_MT_ONEE.POINTE
    + parts.pleines * TARIF_MT_ONEE.PLEINES
    + parts.creuses * TARIF_MT_ONEE.CREUSES) / 100
  return Number.isFinite(moyen) && moyen > 0 ? moyen : null
}

// QX50 — `injectionEnabled` (défaut false, OFF) ajoute la ligne d'injection
// 82-21 SANS toucher l'étude d'autoconsommation : étude avec = étude sans + ligne.
// QXMT — `tensionRaccordement` ('bt' par défaut) : tant qu'il vaut autre chose
// que 'mt', CHAQUE sortie de cette fonction est identique à l'historique (le
// comportement BT est strictement inchangé). En 'mt', l'énergie est valorisée
// au barème MT pondéré par `repartitionMt` ; si ce barème OU cette répartition
// manque, les économies et le payback sont OMIS (null) et l'étude porte le
// motif — jamais un chiffre BT déguisé en chiffre MT.
export function computeEtudeIndustrielle({ kwp, consoMensuelleKwh, dayUsagePct, totalTtc, kwhPrice, efficiency, injectionEnabled = false, tensionRaccordement = 'bt', repartitionMt = null }) {
  if (!kwp || kwp <= 0) return null
  const PRICE = (Number.isFinite(Number(kwhPrice)) && Number(kwhPrice) > 0) ? Number(kwhPrice) : KWH_PRICE
  const EFF = (Number.isFinite(Number(efficiency)) && Number(efficiency) > 0) ? Number(efficiency) : EFFICIENCY
  const prodM = GHI.map(g => g * kwp * EFF)
  const prodA = prodM.reduce((a, b) => a + b, 0)
  const consoMois = parseFloat(consoMensuelleKwh) || 0
  const consoA = consoMois > 0 ? consoMois * 12 : 0
  const dayPct = ((parseFloat(dayUsagePct) || 80)) / 100
  let autoconsomme, tauxAuto, tauxCouv = null
  if (consoA > 0) {
    // énergie solaire réellement consommée sur site (part diurne de la conso)
    autoconsomme = Math.min(prodA, consoA * dayPct)
    tauxAuto = prodA > 0 ? (autoconsomme / prodA) * 100 : 0
    tauxCouv = (autoconsomme / consoA) * 100
  } else {
    autoconsomme = prodA * dayPct
    tauxAuto = dayPct * 100
  }
  // QXMT — valorisation de l'énergie autoconsommée.
  //  · BT (défaut) : tarif ONEE historique — chemin STRICTEMENT inchangé, et
  //    aucune clé MT n'est ajoutée à la sortie.
  //  · MT : barème ONEE « Tarif Général (MT) » pondéré par la répartition
  //    horaire du client. Sans répartition exploitable, le prix vaut `null` et
  //    les économies + le payback sont OMIS (jamais un chiffre BT déguisé).
  const estMt = String(tensionRaccordement || '').toLowerCase() === 'mt'
  const prixMt = estMt ? tarifMtMoyen(repartitionMt) : null
  const prixEnergie = estMt ? prixMt : PRICE
  const economies = prixEnergie != null ? autoconsomme * prixEnergie : null
  const payback = (economies > 0 && totalTtc > 0)
    ? Math.round(totalTtc / economies * 10) / 10 : null
  const out = {
    kwc: Math.round(kwp * 100) / 100,
    production_annuelle: Math.round(prodA),
    conso_annuelle: consoA ? Math.round(consoA) : null,
    taux_autoconso: Math.round(tauxAuto * 10) / 10,
    taux_couverture: tauxCouv != null ? Math.round(tauxCouv * 10) / 10 : null,
    economies_annuelles: economies != null ? Math.round(economies) : null,
    payback,
    prix_kwc: (kwp > 0 && totalTtc > 0) ? Math.round(totalTtc / kwp) : null,
    prod_mensuelle: prodM.map(v => Math.round(v)),
    conso_mensuelle: consoA ? Array(12).fill(Math.round(consoMois)) : null,
  }
  // QXMT — traçabilité MT : le barème, la répartition retenue et la mention
  // réglementaire voyagent avec l'étude (etude_params → écran, PDF, proposition)
  // pour qu'aucun chiffre MT ne circule jamais sans sa source.
  if (estMt) {
    out.tension_raccordement = 'mt'
    out.tarif_mt_mention = TARIF_MT_ONEE.MENTION
    out.tarif_mt_dh_kwh = prixMt != null ? Math.round(prixMt * 10000) / 10000 : null
    const parts = normaliserRepartitionMt(repartitionMt)
    if (parts) out.repartition_mt = parts
    if (prixMt == null) {
      // L'étude reste publiée (production, taux, prix/kWc) : SEUL le calcul qui
      // dépend d'un tarif manquant est omis, avec son motif explicite.
      out.etude_mt_incomplete = true
      out.etude_mt_motif = tarifMtDisponible()
        ? 'Raccordement MT : renseignez la répartition horaire (pointe / '
          + 'pleines / creuses) — économies et payback omis sans elle, les '
          + 'plages horaires MT officielles n’étant pas publiées.'
        : 'Raccordement MT : barème MT ONEE indisponible en source officielle '
          + '— économies et payback omis (à fournir par le fondateur).'
    }
  }
  // QX50 — injection 82-21 : ligne SÉPARÉE (ne modifie pas l'étude ci-dessus).
  // OFF par défaut ; activée par devis. La mention est portée par le renderer.
  if (injectionEnabled) {
    const inj = injection8221(prodA, autoconsomme)
    out.injection_kwh_an = inj.kwh
    out.injection_dh_an = inj.dh
    out.injection_82_21 = true
  }
  return out
}

// ── QF7 — fusion des paramètres d'étude + choix scénario/option, TOUS modes ──
// Fonction pure isolée pour rendre testable la garantie : `scenario` /
// `recommended_option` sont TOUJOURS persistés dans etude_params, quel que
// soit le mode (résidentiel/industriel/agricole) et même quand aucune étude
// dégénérée ne peut être construite (ex. industriel kwp=0 avec des lignes
// manuelles). `baseEtudeParams` peut être null/undefined — le résultat est
// TOUJOURS un objet non-null qui porte au moins le choix scénario/option.
export function buildEtudeParamsChoice(baseEtudeParams, {
  scenario, recommendedChoice, recommendedOption, distributeur, consoAnnuelleReelle,
}) {
  const realBillParams = consoAnnuelleReelle > 0
    ? { distributeur, conso_annuelle: consoAnnuelleReelle }
    : (distributeur && distributeur !== 'onee' ? { distributeur } : {})
  return {
    ...(baseEtudeParams || {}),
    ...(baseEtudeParams?.conso_annuelle ? { distributeur } : realBillParams),
    scenario,
    recommended_choice: recommendedChoice,
    recommended_option: recommendedOption,
  }
}

// ── Pompage solaire (mode Agricole) ───────────────────────────────────────────
export const CV_TO_KW = 0.7355
// Heures de pompage effectives par défaut (champ 1.4× surdimensionné →
// la pompe tourne à régime nominal bien au-delà des heures équivalentes
// plein-soleil ; ~7 h/jour est l'hypothèse marché retenue — modifiable).
export const HEURES_POMPAGE_DEFAUT = 7

// ── QX48(f) — garde de suffisance hydraulique du repli CV ─────────────────────
// Puissance hydraulique P(kW) = ρ·g·Q·H / 3,6e6 = Q·H·0,002725 (Q m³/h, H m,
// ρ=1000, g=9,81). La puissance ARBRE/électrique = hydraulique ÷ η (rendement
// wire-to-water). On compare la pompe SAISIE (CV→kW) au minimum requis quand
// HMT + débit sont renseignés, et on AVERTIT si sous-dimensionnée — JAMAIS un
// blocage. η défaut 0,5 (EST. wire-to-water pompe solaire immergée, à vérifier
// fondateur : la plage réaliste est ~0,35-0,55).
export const PUMP_WIRE_TO_WATER_ETA = 0.5 // EST. — à vérifier fondateur

export function pumpHydraulicKwMin(debit, hmt, eta = PUMP_WIRE_TO_WATER_ETA) {
  const Q = parseFloat(debit)
  const H = parseFloat(hmt)
  const e = parseFloat(eta)
  if (!(Q > 0) || !(H > 0) || !(e > 0)) return null
  return Math.round((Q * H * 2.725 / (1000 * e)) * 100) / 100
}

// Avertissement (string) si la pompe saisie (kW) est sous le minimum hydraulique
// requis, sinon null. Ne bloque JAMAIS le devis.
export function pumpSufficiencyWarning({ hmt, debit, cvKw, eta = PUMP_WIRE_TO_WATER_ETA } = {}) {
  const kwMin = pumpHydraulicKwMin(debit, hmt, eta)
  const kw = parseFloat(cvKw)
  if (kwMin == null || !(kw > 0)) return null
  if (kw < kwMin * 0.98) {
    return `Pompe possiblement sous-dimensionnée : ~${kwMin.toFixed(1)} kW requis `
      + `pour ${parseFloat(debit)} m³/h à ${parseFloat(hmt)} m HMT `
      + `(η≈${eta}), pompe saisie ${Math.round(kw * 100) / 100} kW. `
      + 'Vérifiez le CV ou la HMT.'
  }
  return null
}

// Champ PV ≈ 1.4 × puissance pompe (approche marché 1.3–1.5×), panneaux 710 W
export function champFromKw(kw) {
  const champKw = Math.round(kw * 1.4 * 100) / 100
  const nbPanneaux = Math.max(2, Math.ceil(champKw * 1000 / 710))
  return {
    kw: Math.round(kw * 100) / 100,
    champKw,
    nbPanneaux,
    champKwc: Math.round(nbPanneaux * 710 / 10) / 100,
  }
}

export function computePompage(cv) {
  return champFromKw((parseFloat(cv) || 0) * CV_TO_KW)
}

// ── Courbe de performance : débit délivré (m³/h) à une HMT donnée ─────────────
// courbe = { debits_m3h: [0, 12, ...], hmt_m: [91, 85, ...] } — la HMT décroît
// quand le débit monte. Interpolation linéaire entre les points constructeur.
export function debitAtHmt(courbe, hmt) {
  const H = parseFloat(hmt)
  if (!courbe || !Array.isArray(courbe.debits_m3h) || !Array.isArray(courbe.hmt_m)) return null
  const d = courbe.debits_m3h.map(Number)
  const h = courbe.hmt_m.map(Number)
  if (d.length < 2 || d.length !== h.length || !(H > 0)) return null
  if (H > h[0]) return 0                       // au-delà de la capacité de la pompe
  if (H <= h[h.length - 1]) return d[d.length - 1]  // borné au dernier point mesuré
  for (let i = 0; i < h.length - 1; i++) {
    if (H <= h[i] && H > h[i + 1]) {
      const t = (h[i] - H) / (h[i] - h[i + 1])
      return Math.round((d[i] + t * (d[i + 1] - d[i])) * 10) / 10
    }
  }
  return null
}

const _hasPrix = (p) => (parseFloat(p.prix_vente) || 0) > 0

// QX40 — tension d'un produit (pompe/variateur) : champ tension_v prioritaire,
// sinon lecture « 220V »/« 380V » dans le nom, sinon null (inconnu).
export function tensionOf(p) {
  if (p && p.tension_v) return Number(p.tension_v)
  const nom = (p && p.nom) || ''
  if (/220\s*v/i.test(nom)) return 220
  if (/380\s*v/i.test(nom)) return 380
  return null
}

// Tension attendue selon l'alimentation demandée : mono → 220 V, tri → 380 V.
export function tensionForAlim(alim) {
  return alim === 'mono' ? 220 : 380
}

// Pompe à courbe : la plus petite (kW) qui délivre ≥ le débit souhaité (m³/h)
// à la HMT demandée. Jamais de produit sans prix sur un devis : si seules des
// pompes « prix à renseigner » conviennent, on le dit au lieu d'en chiffrer une.
// QX40 — filtre de compatibilité PHASE/TENSION avant sélection : une demande
// mono/220 V ne peut JAMAIS renvoyer une pompe 380 V (et inversement). Une pompe
// de tension inconnue reste candidate (aucune régression pour les données
// existantes sans tension). Quand aucune pompe à courbe PRICÉE et compatible
// n'existe, `phaseMismatch` signale le repli attendu vers le chemin CV.
export function selectPompeByCurve(produits, { hmt, debit, typePompe, alim }) {
  const H = parseFloat(hmt)
  const Q = parseFloat(debit)
  if (!(H > 0) || !(Q > 0)) return { pump: null, sansPrix: [], phaseMismatch: false }
  const wantSurface = typePompe === 'surface'
  const wantV = alim ? tensionForAlim(alim) : null
  const base = produits
    .map(p => ({
      p, n: _norm(p.nom),
      kw: parseFloat(p.pompe_kw) || 0,
      q: debitAtHmt(p.courbe_pompe, H),
      v: tensionOf(p),
    }))
    .filter(x => x.p.courbe_pompe && x.kw > 0 && x.q != null && x.q >= Q)
    .filter(x => wantSurface ? x.n.includes('surface') : x.n.includes('immerg'))
  // Compat phase : quand une alim est demandée, on écarte les tensions
  // INCOMPATIBLES (une tension inconnue reste tolérée). Sans alim, comportement
  // historique (aucun filtre de tension).
  const cands = base
    .filter(x => wantV == null || x.v == null || x.v === wantV)
    .sort((a, b) => a.kw - b.kw
      || (parseFloat(a.p.prix_vente) || 0) - (parseFloat(b.p.prix_vente) || 0))
  const priced = cands.filter(x => _hasPrix(x.p))
  if (priced.length) {
    const best = priced[0]
    return { pump: best.p, kw: best.kw, debitHmt: best.q, sansPrix: [],
      phaseMismatch: false }
  }
  // QX40 — signale un mismatch de phase : des pompes à courbe convenaient
  // (débit/type) mais AUCUNE compatible+pricée → on dégradera vers le CV avec
  // un avertissement visible plutôt que de chiffrer une tension incompatible.
  const phaseMismatch = wantV != null && priced.length === 0
    && base.some(x => _hasPrix(x.p) && x.v != null && x.v !== wantV)
  return { pump: null, sansPrix: cands.map(x => x.p.nom), phaseMismatch }
}

// Variateur VEICHI : le plus petit dont kW ≥ kW pompe, tension assortie
// (mono 220 V / tri 380 V). L'afficheur (sans kW) n'est jamais candidat.
export function selectVariateurVeichi(produits, kw, alim) {
  const want = alim === 'mono' ? 220 : 380
  const volts = (p) => {
    if (p.tension_v) return Number(p.tension_v)
    if (/220\s*v/i.test(p.nom)) return 220
    if (/380\s*v/i.test(p.nom)) return 380
    return null
  }
  const cands = produits
    .map(p => ({ p, n: _norm(p.nom), kw: parseFloat(p.pompe_kw) || 0, v: volts(p) }))
    .filter(x => x.n.includes('variateur') && !x.n.includes('afficheur')
      && x.kw > 0 && x.v === want && _hasPrix(x.p))
    .sort((a, b) => a.kw - b.kw
      || (parseFloat(a.p.prix_vente) || 0) - (parseFloat(b.p.prix_vente) || 0))
  return cands.find(x => x.kw >= kw)?.p ?? cands[cands.length - 1]?.p ?? null
}

export function findAfficheurVariateur(produits) {
  return produits.find(p =>
    _norm(p.nom).includes('afficheur') && _hasPrix(p)) ?? null
}

// ── Dimensionnement pompage unifié (source unique écran + devis + PDF) ────────
// Si HMT + débit souhaité sont renseignés et qu'une pompe à courbe convient,
// elle pilote tout (kW réels, débit interpolé, m³/jour). Sinon : sélection
// historique par CV, débit manuel, pas de m³/jour (jamais de chiffre inventé).
export function pompageSelection(produits, { cv, typePompe, hmt, debit, heures, alim }) {
  const sel = selectPompeByCurve(produits, { hmt, debit, typePompe, alim })
  if (sel.pump) {
    const kw = sel.kw
    const cvP = parseFloat(sel.pump.pompe_cv)
      || Math.round(kw / CV_TO_KW * 10) / 10
    const hrs = parseFloat(heures) || 0
    return {
      mode: 'courbe',
      pump: sel.pump,
      cv: cvP,
      kw,
      dims: champFromKw(kw),
      debitHmt: sel.debitHmt,
      m3Jour: hrs > 0 ? Math.round(sel.debitHmt * hrs) : null,
      sansPrix: [],
      warning: null,
    }
  }
  const cvNum = parseFloat(cv) || 0
  // QX40 — dégradation VERS LE CHEMIN CV avec avertissement visible quand une
  // pompe à courbe convenait mais aucune n'était compatible avec la phase/
  // tension demandée (jamais une pompe 380 V pour une demande mono/220 V).
  const phaseWarn = sel.phaseMismatch
    ? `Aucune pompe à courbe compatible ${alim === 'mono' ? 'monophasée 220 V'
        : 'triphasée 380 V'} n'est disponible et pricée : dimensionnement par CV `
      + '(vérifiez la tension de la pompe et du variateur).'
    : null
  // QX48(f) — garde de suffisance hydraulique : si HMT + débit sont saisis, on
  // compare la pompe CV saisie au minimum requis et on avertit si sous-
  // dimensionnée (jamais bloquant). Cumulable avec l'avertissement de phase.
  const cvKw = Math.round(cvNum * CV_TO_KW * 100) / 100
  const suffWarn = pumpSufficiencyWarning({ hmt, debit, cvKw })
  const warning = [phaseWarn, suffWarn].filter(Boolean).join(' ') || null
  return {
    mode: 'cv',
    pump: null,
    cv: cvNum,
    kw: Math.round(cvNum * CV_TO_KW * 100) / 100,
    dims: computePompage(cv),
    debitHmt: null,
    m3Jour: null,
    sansPrix: sel.sansPrix,
    warning,
  }
}

const _isPompe = (n) => n.includes('pompe ') || n.startsWith('pompe')

// QX20 — classification « pompe » exposée (garde d'équipement du générateur) :
// une désignation de ligne est une pompe si son nom normalisé le dit. Utilise
// le même _norm que les autres classificateurs.
export function isPompe(designation) {
  return _isPompe(_norm(designation || ''))
}
const _isVfdPompage = (n) =>
  (n.includes('variateur') || n.includes('coffret')) && n.includes('pompage')
const _isCableMetre = (n) => n.includes('cable') && n.includes('metre')

// Équipement pompage : pompe + variateur assorti (+ afficheur) + champ PV
// + structures/socles + câble à la distance — PAS de batterie ni d'onduleur
// réseau/hybride. Jamais de produit « prix à renseigner » sur un devis.
export function autoFillPompage(produits, { cv, alim, typePompe, distance, structureType,
                                            hmt, debit, heures }) {
  const sel = pompageSelection(produits, { cv, alim, typePompe, hmt, debit, heures })
  const cvNum = sel.cv
  if (cvNum <= 0) return []
  const wantTri = alim === 'tri'
  const wantSurface = typePompe === 'surface'

  let pump = null
  if (sel.pump) {
    pump = { p: sel.pump }
  } else if (!sel.sansPrix.length) {
    // Sélection historique par CV (pompes sans courbe, débit manuel)
    const pumps = produits
      .map(p => ({ p, n: _norm(p.nom), cv: parseFloat(p.pompe_cv) || null, tri: parsePhaseIsTri(p.nom) }))
      .filter(x => _isPompe(x.n) && !_isVfdPompage(x.n) && x.cv != null && _hasPrix(x.p))
      .filter(x => wantSurface ? x.n.includes('surface') : x.n.includes('immerg'))
      .sort((a, b) => a.cv - b.cv || a.p.id - b.p.id)
    pump = pumps.find(x => x.cv === cvNum && x.tri === wantTri)
      ?? pumps.find(x => x.cv === cvNum)
      ?? pumps.find(x => x.cv >= cvNum)
      ?? pumps[pumps.length - 1] ?? null
  }
  // sel.sansPrix non vide → seules des pompes sans prix conviennent :
  // on n'en chiffre AUCUNE (l'écran l'explique), le reste du système est rempli.

  // Variateur : VEICHI par kW + tension d'abord, anciens coffrets par CV sinon
  let vfdP = selectVariateurVeichi(produits, sel.kw, alim)
  if (!vfdP) {
    const vfds = produits
      .map(p => ({ p, n: _norm(p.nom), cv: parseFloat(p.pompe_cv) || null, tri: parsePhaseIsTri(p.nom) }))
      .filter(x => _isVfdPompage(x.n) && x.cv != null && _hasPrix(x.p))
      .sort((a, b) => a.cv - b.cv || a.p.id - b.p.id)
    vfdP = (vfds.find(x => x.cv >= cvNum && x.tri === wantTri)
      ?? vfds.find(x => x.cv >= cvNum)
      ?? vfds[vfds.length - 1] ?? null)?.p ?? null
  }
  const afficheur = vfdP && /veichi/i.test(vfdP.nom) ? findAfficheurVariateur(produits) : null

  // QX40 — garde-fou de tension : pompe et variateur DOIVENT partager la même
  // tension. Si les deux ont une tension connue et qu'elles divergent (ex.
  // pompe 380 V + variateur 220 V), on n'assortit PAS la pompe (on ne chiffre
  // jamais un couple incompatible). Une tension inconnue est tolérée.
  if (pump && vfdP) {
    const vp = tensionOf(pump.p)
    const vv = tensionOf(vfdP)
    if (vp != null && vv != null && vp !== vv) {
      pump = null
    }
  }

  const dims = sel.dims
  const byType = {}
  for (const p of produits) {
    const t = classifyProduct(p.nom)
    if (!t) continue
    if (!byType[t]) byType[t] = []
    byType[t].push(p)
  }
  const panels = (byType.panneau ?? [])
    .map(p => ({ p, w: parseWatt(p.nom) }))
    .filter(x => x.w === 710)
  const panel = panels[0]?.p ?? (byType.panneau ?? [])[0] ?? null

  const structures = byType.structure ?? []
  const wanted = structureType === 'aluminium' ? 'alu' : 'acier'
  const struct = structures.find(p => _norm(p.nom).includes(wanted)) ?? structures[0] ?? null

  const cable = produits.find(p => _isCableMetre(_norm(p.nom))) ?? null
  const distM = parseFloat(distance) || 0

  const line = (p, designation, quantite) => ({
    produit: p ? String(p.id) : '',
    designation: p ? p.nom : designation,
    quantite,
    prix_unit_ttc: p ? ttcFromHt(p.prix_vente, tauxTvaOf(p)) : 0,
    taux_tva: p ? tauxTvaOf(p) : 20,
  })

  const rows = []
  if (pump?.p) rows.push(line(pump.p, 'Pompe solaire', 1))
  if (vfdP) rows.push(line(vfdP, 'Variateur solaire', 1))
  if (afficheur) rows.push(line(afficheur, 'Afficheur variateur', 1))
  rows.push(
    line(panel, 'Panneaux', dims.nbPanneaux),
    line(struct, 'Structures', dims.nbPanneaux),
  )
  if ((byType.socle ?? []).length) rows.push(line(byType.socle[0], 'Socles', dims.nbPanneaux * 2))
  if (cable && distM > 0) rows.push(line(cable, 'Câble solaire (m)', distM))
  if ((byType.installation ?? []).length) rows.push(line(byType.installation[0], 'Installation', 1))
  if ((byType.transport ?? []).length) rows.push(line(byType.transport[0], 'Transport', 1))
  return rows
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

// Coût d'achat TTC des lignes dont le produit a un prix d'achat renseigné.
// Retourne null si AUCUN prix d'achat n'existe (alors on n'affiche rien).
// Le TTC d'achat suit le taux TVA du produit (10 % panneaux, 20 % le reste).
export function computeBuyCost(lines, produits) {
  const byId = new Map(produits.map(p => [String(p.id), p]))
  let cost = 0
  let any = false
  for (const l of lines) {
    const p = byId.get(String(l.produit))
    const achat = p ? (parseFloat(p.prix_achat) || 0) : 0
    if (achat > 0) {
      any = true
      cost += (parseFloat(l.quantite) || 0) * achat * (1 + tauxTvaOf(p) / 100)
    }
  }
  return any ? Math.round(cost) : null
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
  if (hasHyb && hasBat) return { available: true }
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
