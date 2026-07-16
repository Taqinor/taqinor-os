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
export function estimerPanneaux(factureHiver, perTranche = 8) {
  const n = Number(perTranche)
  return Math.floor(factureHiver / 900) * (Number.isFinite(n) && n > 0 ? n : 8)
}

// Taux d'autoconsommation par option — miroir pricing.py AUTOCONSO_SANS/AVEC.
// Utilisés UNIQUEMENT par le modèle « deux factures » (QF5) ; l'estimation
// historique ci-dessous continue d'utiliser dayUsagePct (comportement inchangé).
export const AUTOCONSO_SANS = 0.60
export const AUTOCONSO_AVEC = 0.85

// ── QX39 — cashflow 25 ans honnête (MIROIR backend pricing.py) ───────────────
// Mêmes hypothèses documentées : dégradation panneau, escalade tarifaire,
// rendement batterie, remplacement onduleur optionnel. Le payback = croisement
// du cumul à zéro. Écran, PDF et proposition web affichent le MÊME payback.
export const CASHFLOW_YEARS = 25
export const PANEL_DEGRADATION = 0.005
export const TARIFF_ESCALATION = 0.02
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

  for (let i = 0; i < 12; i++) {
    const prodKwh = useProductible
      ? (PROD * kwp) * (GHI[i] / GHI_SUM)   // productible réparti par forme GHI
      : GHI[i] * kwp * EFF
    productionAnnuelle += prodKwh
    const selfConsumed = prodKwh * dayPct
    const ecoSans = selfConsumed * PRICE
    const ecoAvec = ecoSans + (batteryKwh ?? 0) * 60 // 60 MAD/kWh batterie/mois
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
  let savingsModel = 'estimation'
  let factureSans = null, factureAvecSans = null, factureAvecAvec = null
  if (productionAnnuelle > 0 && consoAnnuelleKwh > 0 && utility) {
    const tbSans = twoBillsSavings(productionAnnuelle, consoAnnuelleKwh, AUTOCONSO_SANS, utility)
    const tbAvec = twoBillsSavings(productionAnnuelle, consoAnnuelleKwh, AUTOCONSO_AVEC, utility)
    if (tbSans && tbAvec) {
      savingsModel = 'factures'
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

  // Sélection onduleur : plus petit modèle >= 80 % de la puissance, sinon le
  // plus gros du catalogue ; à puissance égale, Triphasé si >= 10 kW sinon Mono.
  const pickInverter = (pool) => {
    const cands = (pool ?? [])
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
  // ligne 1 = Deyness 5 kWh (qté nb_5), ligne 2 = Deyness 10 kWh (qté nb_10).
  const target = Math.max(5, Math.round(kwp / 5) * 5)
  let nb10 = Math.floor(target / 10)
  let nb5 = (target % 10) >= 5 ? 1 : 0
  const bats = (byType.batterie ?? []).map(p => ({ p, cap: parseKwh(p.nom) }))
  const deyness = bats.filter(x => _norm(x.p.nom).includes('deyness'))
  const batPool = deyness.length ? deyness : bats
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
  return lignes
}

// ══ Multi-marchés (2026-06) ═══════════════════════════════════════════════════

// ── Étude industrielle / commerciale (autoconsommation) ──────────────────────
// DC3 — kwhPrice/efficiency sont threadés EXACTEMENT comme computeROI : le tarif
// ONEE et le rendement de la société (Paramètres → Avancé) pilotent l'étude à
// l'écran, plus seulement le PDF. Sans valeur → constantes historiques
// (parité simulateur garantie).
export function computeEtudeIndustrielle({ kwp, consoMensuelleKwh, dayUsagePct, totalTtc, kwhPrice, efficiency }) {
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
  const economies = autoconsomme * PRICE
  const payback = (economies > 0 && totalTtc > 0)
    ? Math.round(totalTtc / economies * 10) / 10 : null
  return {
    kwc: Math.round(kwp * 100) / 100,
    production_annuelle: Math.round(prodA),
    conso_annuelle: consoA ? Math.round(consoA) : null,
    taux_autoconso: Math.round(tauxAuto * 10) / 10,
    taux_couverture: tauxCouv != null ? Math.round(tauxCouv * 10) / 10 : null,
    economies_annuelles: Math.round(economies),
    payback,
    prix_kwc: (kwp > 0 && totalTtc > 0) ? Math.round(totalTtc / kwp) : null,
    prod_mensuelle: prodM.map(v => Math.round(v)),
    conso_mensuelle: consoA ? Array(12).fill(Math.round(consoMois)) : null,
  }
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
