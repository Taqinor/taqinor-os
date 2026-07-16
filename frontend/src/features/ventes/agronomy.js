// Calcul du besoin en EAU agricole (méthode FAO-56) pour le devis pompage solaire.
// Sert à dimensionner la pompe sur le mois de POINTE : ETc = ET0 × Kc (besoin net
// cultural en mm/j), 1 mm sur 1 ha = 10 m³, volume brut pompé = net ÷ rendement
// d'irrigation. Fonctions pures, sans I/O, défensives : jamais d'exception sur une
// entrée invalide (on renvoie null / 0 raisonnablement). Aligné sur solar.js
// (mode Agricole / pompage) — le débit choisi alimente ensuite selectPompeByCurve.

// ── Coefficients culturaux mi-saison Kc (FAO-56, valeurs Maroc) ───────────────
// Clé culture → Kc mid-season. Valeurs « molles » à affiner par région/variété.
export const KC_MID = {
  olivier: 0.70,      // à confirmer (olivier conduit, sol couvert partiel)
  agrumes: 0.65,      // à confirmer (verger adulte)
  maraichage: 1.05,   // à confirmer (cultures maraîchères plein développement)
  luzerne: 0.95,      // à confirmer (entre deux coupes)
  dattier: 0.95,      // à confirmer (palmier dattier adulte)
  cereales: 1.15,     // à confirmer (céréales à épiaison)
  arganier: 0.55,     // à confirmer (arganeraie, peu exigeant)
}
export const KC_MID_DEFAUT = 0.85 // culture inconnue → Kc moyen prudent

// ── ET0 de pointe estivale (mm/jour) par région agricole marocaine ────────────
// Clé région → ET0 max d'été (juillet-août). Valeurs indicatives à confirmer.
export const ET0_PEAK_MM_J = {
  'souss-massa': 7.5,      // à confirmer (Agadir / plaine du Souss)
  doukkala: 7.0,          // à confirmer (El Jadida / Doukkala)
  tadla: 8.0,             // à confirmer (Béni Mellal / Tadla, très chaud)
  saiss: 7.0,             // à confirmer (Fès-Meknès / plateau du Saïss)
  oriental: 7.5,          // à confirmer (Berkane / Oriental)
  'draa-tafilalet': 8.0,  // à confirmer (oasis présahariennes, très chaud)
}
export const ET0_PEAK_DEFAUT = 7.5 // région inconnue → valeur médiane Maroc

// ── Rendement d'irrigation selon la technique ─────────────────────────────────
// Goutte-à-goutte le plus efficient, gravitaire le moins. Valeurs FAO classiques.
export const IRRIGATION_EFFICIENCY = {
  goutte: 0.90,      // goutte-à-goutte / micro-irrigation
  aspersion: 0.75,   // aspersion
  gravitaire: 0.55,  // irrigation gravitaire (à la raie / submersion)
}
export const IRRIGATION_EFFICIENCY_DEFAUT = 0.75

// ── Abreuvement du cheptel (litres/tête/jour, en pointe) ──────────────────────
// Besoin d'eau de boisson par tête en période chaude. À confirmer (varie selon
// production laitière, climat, alimentation).
export const LIVESTOCK_L_PER_DAY = {
  vache_laitiere: 150, // à confirmer (vache en lactation, forte chaleur)
  bovin: 55,          // à confirmer (bovin viande / génisse)
  mouton: 12,         // à confirmer
  chevre: 10,         // à confirmer
  volaille: 0.35,     // à confirmer (par sujet)
}

// ── Consommation annuelle brute typique (m³/ha/an) ────────────────────────────
// Pour donner un ordre de grandeur et le calcul inverse (ha irrigables depuis un
// volume annuel disponible). Hypothèses marché à confirmer culture par culture.
export const CROP_ANNUAL_M3_HA = {
  olivier: 7000,      // à confirmer
  agrumes: 10000,     // à confirmer
  maraichage: 6000,   // à confirmer
  luzerne: 12000,     // à confirmer (très gourmande, plusieurs coupes)
  dattier: 18000,     // à confirmer (palmeraie en zone aride)
  cereales: 5500,     // à confirmer
  arganier: 4000,     // à confirmer
}
export const CROP_ANNUAL_M3_HA_DEFAUT = 8000

// ── Nombre fini et positif ? (garde commune) ──────────────────────────────────
const _num = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

// ── Besoin en eau d'une exploitation (cultures + cheptel), mois de POINTE ──────
// Renvoie le détail du dimensionnement sur le mois le plus exigeant :
//   { etcPeakMm, netM3HaDay, grossM3HaDay, cropM3Day, livestockM3Day,
//     m3DayPeak, inputs:{...} }.
// Ne renvoie null QUE si ni surface positive ni cheptel n'est fourni.
export function waterDemandFromFarm({ crop, region, surfaceHa, method, trees, livestock } = {}) {
  const surface = _num(surfaceHa)
  const livestockObj = (livestock && typeof livestock === 'object') ? livestock : {}

  // Cheptel : somme des têtes × litres/tête/jour ÷ 1000 (→ m³/jour)
  let livestockM3Day = 0
  for (const key of Object.keys(livestockObj)) {
    const lParTete = LIVESTOCK_L_PER_DAY[key]
    if (!(lParTete > 0)) continue
    const count = _num(livestockObj[key])
    if (count > 0) livestockM3Day += count * lParTete / 1000
  }

  // Rien à dimensionner → null (entrée vide, on ne devine pas)
  if (!(surface > 0) && livestockM3Day <= 0) return null

  // ETc de pointe = ET0 de pointe régional × Kc mi-saison de la culture
  const et0 = ET0_PEAK_MM_J[region] ?? ET0_PEAK_DEFAUT
  const kc = KC_MID[crop] ?? KC_MID_DEFAUT
  const etcPeakMm = et0 * kc

  // Besoin net (mm/j → m³/ha/j : 1 mm sur 1 ha = 10 m³) puis brut (÷ rendement)
  const netM3HaDay = etcPeakMm * 10
  const eff = IRRIGATION_EFFICIENCY[method] ?? IRRIGATION_EFFICIENCY_DEFAUT
  const grossM3HaDay = eff > 0 ? netM3HaDay / eff : 0

  const cropM3Day = grossM3HaDay * (surface > 0 ? surface : 0)
  const m3DayPeak = Math.round(cropM3Day + livestockM3Day)

  return {
    etcPeakMm: Math.round(etcPeakMm * 1000) / 1000,
    netM3HaDay: Math.round(netM3HaDay * 100) / 100,
    grossM3HaDay: Math.round(grossM3HaDay * 100) / 100,
    cropM3Day: Math.round(cropM3Day * 100) / 100,
    livestockM3Day: Math.round(livestockM3Day * 100) / 100,
    m3DayPeak,
    inputs: {
      crop: crop ?? null,
      region: region ?? null,
      surfaceHa: surface,
      method: method ?? null,
      trees: _num(trees) || null,
      kc,
      et0,
      efficiency: eff,
    },
  }
}

// ── Débit pompe requis (m³/h) pour livrer le volume jour en N heures ──────────
// Garde : heures de pompage strictement positives, sinon null. Arrondi 1 déc.
export function requiredFlow(m3Day, hours) {
  const v = _num(m3Day)
  const h = _num(hours)
  if (!(h > 0) || v <= 0) return null
  return Math.round((v / h) * 10) / 10
}

// ── Calcul inverse : hectares irrigables avec un volume annuel disponible ──────
// ha = volume annuel / consommation annuelle brute typique de la culture.
export function hectaresIrrigable(m3Year, crop) {
  const v = _num(m3Year)
  const perHa = CROP_ANNUAL_M3_HA[crop] ?? CROP_ANNUAL_M3_HA_DEFAUT
  if (!(v > 0) || !(perHa > 0)) return null
  return Math.round((v / perHa) * 10) / 10
}

// ── Estimation du volume ANNUEL depuis le besoin de pointe ────────────────────
// Le jour de pointe est ramené à une moyenne annuelle (peakToAvg) sur le nombre
// de jours de pompage. peakToAvg ≈ 0.62 : à confirmer (dépend du climat et de la
// répartition saisonnière des cultures).
export function annualWater(m3Day, pumpingDaysPerYear = 300, peakToAvg = 0.62) {
  const v = _num(m3Day)
  const days = _num(pumpingDaysPerYear)
  const ratio = _num(peakToAvg)
  if (v <= 0 || !(days > 0) || !(ratio > 0)) return 0
  return Math.round(v * ratio * days)
}

// ═══════════════════════════════════════════════════════════════════════════
// QX48 — Moteur agronomique v2 (FAO-56 réel, série MENSUELLE partagée)
// ═══════════════════════════════════════════════════════════════════════════
// Le v1 ci-dessus (mois de POINTE) reste inchangé pour compatibilité. Le v2
// produit une SÉRIE mensuelle d'ETc (le graphe QX47) via des stades Kc FAO-56
// (ini/dev/mid/late), des ET0 MENSUELS régionaux, crédite la pluie efficace par
// région (le v1 surestimait le Gharb) et annualise par INTÉGRALE de la série
// (plus le forfait plat 0,62×300 j). CHAQUE constante porte sa source ; « EST. »
// = valeur estimée à vérifier fondateur. Miroir strict de agronomy.py (test de
// parité). Le mois est indexé 0 = janvier … 11 = décembre.

export const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

// ET0 de référence MENSUEL (mm/jour) par région — Penman-Monteith, stations FAO
// CLIMWAT représentatives. Valeurs ESTIMÉES (station proxy), à vérifier fondateur.
export const ET0_MONTHLY = {
  'souss-massa':    [2.4, 3.0, 4.0, 4.7, 5.4, 5.9, 6.2, 6.0, 5.0, 4.0, 3.0, 2.3], // Agadir — EST.
  doukkala:         [2.2, 2.8, 3.8, 4.5, 5.2, 5.8, 6.3, 6.1, 5.0, 3.9, 2.8, 2.1], // El Jadida — EST.
  tadla:            [2.0, 2.9, 4.2, 5.4, 6.6, 7.6, 8.2, 7.7, 5.9, 4.2, 2.8, 2.0], // Béni Mellal — EST.
  saiss:            [1.8, 2.5, 3.7, 4.8, 6.0, 7.0, 7.6, 7.1, 5.3, 3.7, 2.4, 1.7], // Fès-Meknès — EST.
  oriental:         [2.0, 2.7, 3.9, 5.0, 6.2, 7.1, 7.7, 7.2, 5.5, 3.9, 2.6, 1.9], // Berkane/Oujda — EST.
  'draa-tafilalet': [2.2, 3.1, 4.5, 5.8, 7.0, 8.0, 8.5, 7.9, 6.2, 4.4, 2.9, 2.1], // Errachidia — EST.
  'gharb-loukkos':  [2.0, 2.6, 3.6, 4.4, 5.3, 6.0, 6.5, 6.2, 5.0, 3.7, 2.6, 1.9], // Kénitra/Larache — EST.
  haouz:            [2.3, 3.1, 4.4, 5.6, 6.8, 7.8, 8.4, 7.8, 6.0, 4.3, 2.9, 2.2], // Marrakech — EST.
}
export const ET0_MONTHLY_DEFAUT = [2.1, 2.8, 4.0, 5.0, 6.1, 7.0, 7.6, 7.1, 5.5, 4.0, 2.7, 2.0] // médiane MA — EST.

// Pluie EFFICACE mensuelle (mm/mois) par région — méthode USDA-SCS simplifiée
// sur les normales pluviométriques MA. Créditée au besoin net (le Gharb, humide,
// était surestimé par le forfait v1). Valeurs ESTIMÉES, à vérifier fondateur.
export const RAIN_EFF_MONTHLY = {
  'gharb-loukkos':  [60, 55, 50, 40, 20, 5, 0, 0, 10, 40, 60, 65], // ~405 mm/an eff — EST.
  saiss:            [45, 42, 45, 40, 22, 6, 1, 1, 10, 30, 48, 50], // EST.
  oriental:         [30, 28, 30, 30, 20, 6, 1, 2, 10, 28, 32, 30], // EST.
  doukkala:         [35, 30, 28, 18, 8, 1, 0, 0, 5, 20, 35, 40],   // EST.
  tadla:            [30, 30, 30, 25, 12, 3, 0, 0, 5, 22, 33, 35],  // EST.
  haouz:            [25, 25, 28, 25, 12, 3, 0, 1, 6, 22, 28, 26],  // EST.
  'souss-massa':    [25, 20, 20, 12, 5, 0, 0, 0, 3, 12, 22, 28],   // EST.
  'draa-tafilalet': [8, 8, 10, 8, 5, 2, 1, 3, 6, 8, 8, 7],         // EST.
}
export const RAIN_EFF_DEFAUT = [20, 18, 20, 16, 8, 2, 0, 0, 5, 15, 22, 22] // EST.

// Stades culturaux FAO-56 (Table 11 durées / Table 12 Kc) adaptés au calendrier
// marocain. `evergreen:true` = pérenne à feuillage permanent (Kc ~constant).
// Sinon cycle démarrant à `start` (mois 1-12), durées de stades en MOIS
// [ini, dev, mid, late] et Kc ini/mid/end. `kcEstimated:true` = hors FAO / estimé.
export const CROP_STAGES = {
  // Pérennes à feuillage permanent (Kc ~constant toute l'année).
  agrumes:   { evergreen: true, kcMid: 0.65 }, // FAO-56 T12 citrus (no ground cover)
  olivier:   { evergreen: true, kcMid: 0.65 }, // FAO-56 T12 olive (40-60 % couverture)
  dattier:   { evergreen: true, kcMid: 0.95 }, // FAO-56 T12 date palm ; MA 51 m³/arbre/an
  avocatier: { evergreen: true, kcMid: 0.85 }, // FAO-56 T12 avocado ; MA Gharb 8-12 000 m³/ha/an
  arganier:  { evergreen: true, kcMid: 0.55, kcEstimated: true }, // EST. (pas d'entrée FAO)
  'banane-serre': { evergreen: true, kcMid: 1.10 }, // FAO-56 T12 banana (récolte étalée)
  luzerne:   { evergreen: true, kcMid: 0.95, kcEstimated: true }, // EST. (moyenne inter-coupes, pas le pic FAO)
  myrtille:  { evergreen: true, kcMid: 1.05, kcEstimated: true }, // EST. proxy petits fruits ; MA pics ~80 m³/ha/j
  // Pérennes DÉCIDUS : feuillage ~printemps→automne, dormance hiver (Kc 0).
  amandier:  { start: 3, stages: [1, 1, 5, 2], kcIni: 0.40, kcMid: 0.90, kcEnd: 0.65 }, // FAO-56 T12 almond
  vigne:     { start: 4, stages: [1, 1, 3, 2], kcIni: 0.30, kcMid: 0.70, kcEnd: 0.45 }, // FAO-56 T12 grape (table)
  grenadier: { start: 3, stages: [1, 2, 4, 2], kcIni: 0.35, kcMid: 0.85, kcEnd: 0.55, kcEstimated: true }, // EST.
  figuier:   { start: 3, stages: [1, 2, 4, 2], kcIni: 0.35, kcMid: 0.70, kcEnd: 0.50, kcEstimated: true }, // EST.
  // Annuelles / maraîchage (cycle FAO-56, calendrier MA).
  'tomate-serre':  { start: 9, stages: [1, 2, 3, 1], kcIni: 0.60, kcMid: 1.10, kcEnd: 0.80 }, // FAO-56 T12 tomato
  'poivron-serre': { start: 9, stages: [1, 2, 3, 1], kcIni: 0.60, kcMid: 1.05, kcEnd: 0.90 }, // FAO-56 T12 bell pepper
  'pomme-de-terre': { start: 1, stages: [1, 1, 2, 1], kcIni: 0.50, kcMid: 1.15, kcEnd: 0.75 }, // FAO-56 T12 potato
  oignon:    { start: 10, stages: [1, 2, 3, 1], kcIni: 0.70, kcMid: 1.05, kcEnd: 0.75 }, // FAO-56 T12 onion (dry)
  'melon-pasteque': { start: 3, stages: [1, 1, 2, 1], kcIni: 0.50, kcMid: 1.00, kcEnd: 0.75 }, // FAO-56 T12 melon/watermelon
  cereales:  { start: 11, stages: [1, 2, 2, 1], kcIni: 0.40, kcMid: 1.15, kcEnd: 0.40 }, // FAO-56 T12 wheat (semis auto MA)
  fraise:    { start: 10, stages: [1, 2, 3, 1], kcIni: 0.40, kcMid: 1.00, kcEnd: 0.75, kcEstimated: true }, // EST.
  cannabis:  { start: 5, stages: [1, 1, 2, 1], kcIni: 0.40, kcMid: 1.00, kcEnd: 0.60, kcEstimated: true }, // EST. (cannabis licite, flag ANRAC)
}

// Valeurs Maroc CITÉES (recherche 2026-07-16) — référence de CALAGE : chaque
// nombre porte sa source ; elles ne remplacent pas le calcul, elles le VALIDENT.
export const CROP_CITED = {
  avocatier: { annual_m3_ha: [8000, 12000], region: 'gharb-loukkos', source: 'MA Gharb 8-12 000 m³/ha/an (recherche 2026-07-16)' },
  myrtille:  { peak_m3_ha_day: 80, source: 'MA pics ~80 m³/ha/j (recherche 2026-07-16)' },
  dattier:   { m3_per_tree_year: 51, trees_per_ha: 100, source: 'MA 51 m³/arbre/an (recherche 2026-07-16)' },
}

// Kc mensuel (0=janvier … 11=décembre) construit depuis les stades FAO-56 de la
// culture. Culture inconnue → Kc plat prudent (KC_MID_DEFAUT). Pérenne évergreen
// → Kc constant. Déciduous/annuel → 0 hors cycle, ramp ini→mid puis mid→end.
export function cropKcMonthly(cropKey) {
  const kc = new Array(12).fill(0)
  const spec = CROP_STAGES[cropKey]
  if (!spec) return kc.fill(KC_MID_DEFAUT)
  if (spec.evergreen) return kc.fill(spec.kcMid)
  const { start = 1, stages = [1, 1, 1, 1], kcIni = 0.4, kcMid = 1.0, kcEnd = 0.6 } = spec
  const [ini, dev, mid, late] = stages
  let m = (start - 1) % 12
  const put = (v) => { kc[m] = Math.round(v * 1000) / 1000; m = (m + 1) % 12 }
  for (let i = 0; i < ini; i++) put(kcIni)
  for (let i = 0; i < dev; i++) put(kcIni + (kcMid - kcIni) * ((i + 1) / (dev + 1)))
  for (let i = 0; i < mid; i++) put(kcMid)
  for (let i = 0; i < late; i++) put(kcMid + (kcEnd - kcMid) * ((i + 1) / (late + 1)))
  return kc
}

// ── Besoin en eau MENSUEL d'une culture (le graphe QX47) ──────────────────────
// Renvoie la série mensuelle d'ETc + besoins net/brut, l'annualisation par
// INTÉGRALE de la série, et le pic. Défensif : jamais d'exception.
export function monthlyWaterDemand({ crop, region, surfaceHa, method } = {}) {
  const surface = _num(surfaceHa)
  const et0 = ET0_MONTHLY[region] || ET0_MONTHLY_DEFAUT
  const rain = RAIN_EFF_MONTHLY[region] || RAIN_EFF_DEFAUT
  const eff = IRRIGATION_EFFICIENCY[method] ?? IRRIGATION_EFFICIENCY_DEFAUT
  const kc = cropKcMonthly(crop)
  const etcMmDay = []        // ETc mm/jour (besoin cultural instantané)
  const cropNeedMmMonth = [] // besoin cultural mm/mois AVANT pluie (courbe « besoin culture »)
  const netMmMonth = []      // besoin net mm/mois APRÈS crédit pluie efficace
  const grossM3HaMonth = []  // besoin brut m³/ha/mois (net ÷ rendement)
  const grossM3FarmDay = []  // besoin brut m³/jour à l'échelle exploitation (courbe « eau livrée »)
  for (let m = 0; m < 12; m++) {
    const etc = et0[m] * kc[m]
    const grossMm = etc * DAYS_IN_MONTH[m]
    const netMm = Math.max(0, grossMm - rain[m])
    const grossHa = eff > 0 ? (netMm * 10) / eff : 0
    etcMmDay.push(Math.round(etc * 1000) / 1000)
    cropNeedMmMonth.push(Math.round(grossMm * 10) / 10)
    netMmMonth.push(Math.round(netMm * 10) / 10)
    grossM3HaMonth.push(Math.round(grossHa * 10) / 10)
    grossM3FarmDay.push(surface > 0
      ? Math.round((grossHa * surface / DAYS_IN_MONTH[m]) * 10) / 10 : 0)
  }
  const annualNetM3Ha = Math.round(netMmMonth.reduce((s, v) => s + v, 0) * 10)
  const annualGrossM3Ha = Math.round(grossM3HaMonth.reduce((s, v) => s + v, 0))
  const annualGrossM3Farm = surface > 0 ? Math.round(annualGrossM3Ha * surface) : 0
  const peakM3HaDay = Math.round(
    Math.max(...grossM3HaMonth.map((v, m) => v / DAYS_IN_MONTH[m])) * 10) / 10
  const peakM3FarmDay = Math.round(Math.max(0, ...grossM3FarmDay) * 10) / 10
  return {
    kc, etcMmDay, cropNeedMmMonth, netMmMonth, grossM3HaMonth, grossM3FarmDay,
    annualNetM3Ha, annualGrossM3Ha, annualGrossM3Farm,
    peakM3HaDay, peakM3FarmDay,
    kcEstimated: !!(CROP_STAGES[crop] && CROP_STAGES[crop].kcEstimated),
    inputs: {
      crop: crop ?? null, region: region ?? null, surfaceHa: surface,
      method: method ?? null, efficiency: eff,
    },
  }
}

// ── (e) Annualisation par INTÉGRALE de la série mensuelle ──────────────────────
// Remplace le forfait plat annualWater(0,62×300 j) sur le chemin agricole v2 :
// somme des besoins bruts journaliers × jours du mois. m³/an à l'échelle
// exploitation. Le forfait v1 reste le repli quand la culture/région est inconnue.
export function annualWaterFromMonthly(monthly) {
  if (!monthly || !Array.isArray(monthly.grossM3FarmDay)) return 0
  const total = DAYS_IN_MONTH.reduce(
    (s, d, m) => s + (_num(monthly.grossM3FarmDay[m]) * d), 0)
  return Math.round(total)
}

// Volume annuel CITÉ par arbre (dattier) — la valeur MA de référence, pas un
// calcul. Densité de plantation par défaut lue de CROP_CITED.
export function datePalmCitedPerTree() {
  return CROP_CITED.dattier.m3_per_tree_year
}
