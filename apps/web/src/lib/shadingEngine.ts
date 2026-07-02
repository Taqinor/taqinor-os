/**
 * WJ19 — MOTEUR D'OMBRAGE PUR (« shadow-tracing shading → honest production »).
 *
 * Méthode « Pylon » (sans API payante) : l'utilisateur trace une ombre VISIBLE sur
 * l'image satellite (pied de l'obstacle → bout de l'ombre). De la longueur d'ombre
 * et de la position du soleil AU MOMENT DE LA PRISE DE VUE, on déduit la hauteur de
 * l'obstruction (h = L × tan(élévation)) — trigonométrie pure, quasi-LIDAR quand
 * l'heure de prise de vue est connue. L'obstruction (position + hauteur) est ensuite :
 *   1. dessinée dans la scène Three.js (elle projette une VRAIE ombre) ;
 *   2. utilisée pour DÉRATER la production horaire PVGIS : pour chaque (mois, heure)
 *      on calcule la position du soleil (astronomie standard, sunDirection) et, si
 *      l'obstruction masque le disque solaire vu du champ, l'heure est ramenée à sa
 *      part DIFFUSE (le rayonnement direct est perdu, le diffus reste).
 *
 * HONNÊTETÉS ÉNONCÉES (aucun chiffre inventé — voir ESTIMATOR_WJ19_24_NOTES.md) :
 *  - L'heure de prise de vue n'est PAS fournie par les tuiles → hypothèse PAR DÉFAUT
 *    « ~10 h 30 solaire, mi-saison » : les satellites d'imagerie THR (Maxar WorldView,
 *    Airbus Pléiades…) sont sur orbite HÉLIOSYNCHRONE à nœud descendant ~10 h 30
 *    locale — c'est un fait documenté d'ingénierie orbitale, affiché comme hypothèse
 *    ajustable, jamais une précision inventée.
 *  - Part diffuse conservée quand le direct est masqué : 25 % (fraction diffuse
 *    annuelle typique du rayonnement global au Maroc, climat clair, d'après les
 *    rapports PVGIS-SARAH DNI/GHI ; prudent : on ne met jamais l'heure à zéro, on ne
 *    garde jamais plus que le diffus).
 *  - La hauteur déduite est au-dessus du SOL ; le champ est sur un toit (~2 étages).
 *    Seule la hauteur au-dessus du plan du toit masque le soleil (hEff = h − hToit).
 *
 * Module PUR : aucun DOM, aucun réseau. Le dérate s'applique aux profils PVGIS
 * (PerKwcProduction / ScaledProduction du moteur de production).
 */
import { sunDirection } from './roofPro2';
import { type LngLat } from './roof';
import { DAYS_IN_MONTH, type PerKwcProduction } from './productionEngine';

const DEG2RAD = Math.PI / 180;
const WGS84_RADIUS = 6378137;
const DEG2M = DEG2RAD * WGS84_RADIUS;

/** Hypothèse PAR DÉFAUT du moment de prise de vue de l'imagerie : ~10 h 30 solaire
 *  (orbites héliosynchrones des satellites d'imagerie), mi-saison (équinoxe ≈ jour 80 —
 *  ni le pire ni le meilleur soleil, l'hypothèse la plus neutre). Ajustable par
 *  l'utilisateur, TOUJOURS étiquetée comme hypothèse. */
export const IMAGERY_SUN_DEFAULT = { dayOfYear: 80, solarHour: 10.5 } as const;

/** Part DIFFUSE du rayonnement conservée quand l'obstruction masque le soleil direct.
 *  ~25 % : fraction diffuse annuelle typique du global au Maroc (climat clair, ratios
 *  DNI/GHI des données PVGIS-SARAH) — on perd le direct, on garde le diffus. */
export const DIFFUSE_FRACTION_WHEN_SHADED = 0.25;

/** Demi-largeur PAR DÉFAUT (m) d'une obstruction tracée (couronne d'arbre / pignon
 *  étroit). L'utilisateur ne trace qu'une ligne d'ombre : la largeur est une hypothèse
 *  affichée (3 m ≈ couronne d'arbre adulte), éditable par obstruction. */
export const SHADE_OBSTRUCTION_HALF_WIDTH_M = 3;

/** Hauteur de toit par défaut (m) au-dessus du sol : 2 étages × 3 m — la même
 *  convention que la scène 3D du builder (FLOORS × FLOOR_HEIGHT_M). */
export const DEFAULT_ROOF_HEIGHT_M = 6;

/** Jour de l'année du MILIEU de chaque mois (index 0 = janvier) — représentant
 *  mensuel pour l'échantillonnage solaire (année non bissextile). */
export const MID_MONTH_DAY_OF_YEAR: readonly number[] = [15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349];

/** Une obstruction déduite d'une ombre tracée (état sérialisable, lng/lat). */
export interface ShadeObstruction {
  id: string;
  /** Pied de l'obstacle (lng/lat) — là où l'ombre naît. */
  base: LngLat;
  /** Bout de l'ombre (lng/lat) — extrémité tracée. */
  tip: LngLat;
  /** Hauteur DÉDUITE (m, au-dessus du sol). Rééditable par l'utilisateur. */
  heightM: number;
  /** Demi-largeur supposée (m) de l'obstruction. */
  halfWidthM: number;
}

/** Obstruction projetée en ENU (mètres) autour d'une origine, prête au test de masquage. */
export interface ShadeObstructionENU {
  x: number;
  y: number;
  /** Hauteur EFFECTIVE au-dessus du plan du champ (déjà réduite de la hauteur de toit). */
  effHeightM: number;
  halfWidthM: number;
}

/** Longueur (m) et azimut (°, 0=N, 90=E — direction base→bout) d'une ombre tracée.
 *  Projection équirectangulaire locale (échelle toiture : exacte au cm près). */
export function shadowVector(base: LngLat, tip: LngLat): { lengthM: number; azimuthDeg: number } {
  const cosLat = Math.cos(base[1] * DEG2RAD);
  const dx = (tip[0] - base[0]) * DEG2M * cosLat;
  const dy = (tip[1] - base[1]) * DEG2M;
  const lengthM = Math.hypot(dx, dy);
  const azimuthDeg = (Math.atan2(dx, dy) / DEG2RAD + 360) % 360;
  return { lengthM, azimuthDeg };
}

/**
 * Hauteur d'obstruction (m) déduite d'une longueur d'ombre au sol et de l'élévation
 * solaire au moment de la prise de vue : h = L × tan(α). Soleil sous ~3° (ombres
 * quasi infinies, tangente explosive) ou longueur invalide → null (pas de précision
 * inventée : on refuse de déduire).
 */
export function obstructionHeightFromShadow(shadowLengthM: number, sunElevationDeg: number): number | null {
  if (!Number.isFinite(shadowLengthM) || shadowLengthM <= 0) return null;
  if (!Number.isFinite(sunElevationDeg) || sunElevationDeg <= 3) return null;
  return shadowLengthM * Math.tan(sunElevationDeg * DEG2RAD);
}

/** Projette les obstructions lng/lat en ENU (m) autour d'une origine, en retirant la
 *  hauteur de toit (seul ce qui dépasse le plan du champ masque le soleil). Les
 *  obstructions entièrement sous le toit (effHeight ≤ 0) sont écartées. */
export function shadeObstructionsENU(
  list: readonly ShadeObstruction[],
  origin: LngLat,
  roofHeightM = DEFAULT_ROOF_HEIGHT_M,
): ShadeObstructionENU[] {
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  const out: ShadeObstructionENU[] = [];
  for (const o of list) {
    const eff = (Number.isFinite(o.heightM) ? o.heightM : 0) - Math.max(0, roofHeightM);
    if (eff <= 0) continue;
    out.push({
      x: (o.base[0] - origin[0]) * DEG2M * cosLat,
      y: (o.base[1] - origin[1]) * DEG2M,
      effHeightM: eff,
      halfWidthM: Number.isFinite(o.halfWidthM) && o.halfWidthM > 0 ? o.halfWidthM : SHADE_OBSTRUCTION_HALF_WIDTH_M,
    });
  }
  return out;
}

/** Écart angulaire signé minimal (°) entre deux azimuts (résultat dans [−180, 180]). */
function azimuthDiffDeg(a: number, b: number): number {
  return ((a - b + 540) % 360) - 180;
}

/**
 * Le soleil (élévation/azimut) est-il masqué, vu du point (px, py) du champ, par au
 * moins une obstruction ? Test angulaire : l'obstruction sous-tend une élévation
 * atan(hEff/d) et une demi-largeur atan(r/d) autour de son azimut — le soleil est
 * masqué s'il est PLUS BAS que le sommet ET dans le cône azimutal. PUR (testé).
 */
export function isSunBlocked(
  px: number,
  py: number,
  obstructions: readonly ShadeObstructionENU[],
  sunElevationDeg: number,
  sunAzimuthDeg: number,
): boolean {
  if (sunElevationDeg <= 0) return false; // nuit : rien à masquer
  for (const o of obstructions) {
    const dx = o.x - px;
    const dy = o.y - py;
    const dist = Math.hypot(dx, dy);
    if (dist < 0.5) {
      // Obstruction pile sur le point : masque tout ce qui est plus bas que son sommet.
      if (sunElevationDeg < 89) return true;
      continue;
    }
    const azToObs = (Math.atan2(dx, dy) / DEG2RAD + 360) % 360;
    const halfWidthDeg = Math.atan2(o.halfWidthM, dist) / DEG2RAD;
    if (Math.abs(azimuthDiffDeg(sunAzimuthDeg, azToObs)) > halfWidthDeg) continue;
    const topElevDeg = Math.atan2(o.effHeightM, dist) / DEG2RAD;
    if (sunElevationDeg < topElevDeg) return true;
  }
  return false;
}

/**
 * Matrice 12 × 24 des facteurs d'ombrage horaires du point (px, py) : pour chaque
 * (mois, heure) on positionne le soleil (jour représentatif = milieu du mois, heure
 * centrée h+0,5) ; heure masquée → part diffuse conservée, sinon 1. Nuit → 1 (la
 * production y est déjà nulle — on ne dérate pas ce qui n'existe pas). PUR.
 */
export function hourlyShadeFactors(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  px = 0,
  py = 0,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): number[][] {
  const factors: number[][] = [];
  for (let m = 0; m < 12; m++) {
    const row = new Array<number>(24).fill(1);
    if (obstructions.length) {
      for (let h = 0; h < 24; h++) {
        const sun = sunDirection(latitudeDeg, MID_MONTH_DAY_OF_YEAR[m], h + 0.5);
        if (sun.elevationDeg <= 0) continue;
        if (isSunBlocked(px, py, obstructions, sun.elevationDeg, sun.azimuthDeg)) {
          row[h] = Math.max(0, Math.min(1, diffuseFraction));
        }
      }
    }
    factors.push(row);
  }
  return factors;
}

/**
 * Applique la matrice d'ombrage aux profils PVGIS : chaque heure du jour-type de
 * chaque mois est multipliée par son facteur, puis les totaux (jour, mois, an) sont
 * RE-INTÉGRÉS depuis les profils dératés — cohérence jour → mois → an conservée.
 * Facteurs absents/identité → copie inchangée. PUR (le moteur de production n'est
 * pas muté).
 */
export function applyShadeFactors<T extends PerKwcProduction>(prod: T, factors: number[][] | null | undefined): T {
  if (!factors || factors.length !== 12) return prod;
  const typicalDayByMonth = prod.typicalDayByMonth.map((prof, m) =>
    prof.map((v, h) => v * (factors[m]?.[h] ?? 1)),
  );
  const dailyKwhByMonth = typicalDayByMonth.map((prof) => prof.reduce((a, b) => a + b, 0));
  const monthlyKwh = dailyKwhByMonth.map((d, m) => d * DAYS_IN_MONTH[m]);
  const annualKwh = monthlyKwh.reduce((a, b) => a + b, 0);
  return { ...prod, typicalDayByMonth, dailyKwhByMonth, monthlyKwh, annualKwh };
}

/**
 * Facteur d'ombrage ANNUEL (0–1] = production dératée ÷ production intacte, pondéré
 * par les VRAIS profils PVGIS (les heures d'hiver pèsent moins que celles d'été).
 * Sans production exploitable → 1 (aucun dérate inventé).
 */
export function annualShadeFactor(prod: PerKwcProduction, factors: number[][] | null | undefined): number {
  if (!factors) return 1;
  const before = prod.monthlyKwh.reduce((a, b) => a + b, 0);
  if (!(before > 0)) return 1;
  const after = applyShadeFactors(prod, factors).monthlyKwh.reduce((a, b) => a + b, 0);
  const f = after / before;
  return Number.isFinite(f) ? Math.max(0, Math.min(1, f)) : 1;
}
