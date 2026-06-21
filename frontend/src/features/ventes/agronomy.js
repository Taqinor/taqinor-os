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
