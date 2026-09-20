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
import { pointInPolygon, type LngLat } from './roof';
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
  /**
   * CAL94 — EMPREINTE AU SOL réelle (ENU, mètres ; ≥ 3 sommets). Quand elle est
   * renseignée, l'occultation est calculée par LANCER DE RAYON contre le prisme vertical
   * (empreinte × `effHeightM`) : c'est la géométrie EXACTE de l'obstacle saisi, et non
   * le cône angulaire — un rectangle de 4 × 1 m n'ombre pas comme un disque de 4 m.
   *
   * ABSENTE (ombres tracées WJ19 : l'utilisateur ne trace qu'une LIGNE, il n'y a pas
   * d'empreinte à connaître) ⇒ on retombe EXACTEMENT sur le test angulaire historique.
   * C'est ce qui garantit la non-régression : aucune obstruction sans empreinte ne
   * change de comportement.
   */
  footprint?: readonly (readonly [number, number])[];
}

/**
 * CAL94 — distance horizontale (m) à laquelle un rayon parti de (px, py) dans la
 * direction unitaire (dx, dy) ENTRE dans le polygone `poly`, ou null s'il ne le
 * rencontre jamais. Point DANS le polygone ⇒ 0. PUR (aucune dépendance 3D : c'est
 * la même intersection rayon/segment que ferait un raycaster three.js, faite ici sur
 * l'empreinte extrudée — donc testable et mesurable sans WebGL).
 */
export function rayEntryDistance(
  px: number,
  py: number,
  dx: number,
  dy: number,
  poly: readonly (readonly [number, number])[],
): number | null {
  if (!poly || poly.length < 3) return null;
  if (pointInPolygon([px, py], poly as [number, number][])) return 0;
  let best = Infinity;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const ax = poly[j][0];
    const ay = poly[j][1];
    const sx = poly[i][0] - ax;
    const sy = poly[i][1] - ay;
    const denom = dx * sy - dy * sx;
    if (Math.abs(denom) < 1e-12) continue; // rayon parallèle à l'arête
    const qx = ax - px;
    const qy = ay - py;
    const t = (qx * sy - qy * sx) / denom;
    if (t < 0) continue; // l'arête est DERRIÈRE le point
    const u = (qx * dy - qy * dx) / denom;
    if (u < 0 || u > 1) continue; // le rayon passe à côté du segment
    if (t < best) best = t;
  }
  return best === Infinity ? null : best;
}

/**
 * CAL94 — le rayon solaire parti de (px, py) est-il intercepté par le PRISME vertical
 * (empreinte `o.footprint`, hauteur `o.effHeightM`) ? Le rayon monte de
 * `tan(élévation)` par mètre parcouru horizontalement : il est bloqué si, à l'entrée
 * dans l'empreinte, il est encore SOUS le sommet du prisme. PUR.
 */
function isSunBlockedByFootprint(
  px: number,
  py: number,
  o: ShadeObstructionENU,
  sunElevationDeg: number,
  sunAzimuthDeg: number,
): boolean {
  // Direction HORIZONTALE vers le soleil (azimut 0 = Nord, 90 = Est) — mêmes
  // conventions que `sunDirection`.
  const az = sunAzimuthDeg * DEG2RAD;
  const dx = Math.sin(az);
  const dy = Math.cos(az);
  const t = rayEntryDistance(px, py, dx, dy, o.footprint as readonly (readonly [number, number])[]);
  if (t == null) return false;
  if (t === 0) return sunElevationDeg < 89; // point sous l'obstacle lui-même
  return t * Math.tan(sunElevationDeg * DEG2RAD) < o.effHeightM;
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
 * moins une obstruction ?
 *
 *  - CAL94 — obstruction avec EMPREINTE (`footprint`) : LANCER DE RAYON contre le
 *    prisme vertical (empreinte extrudée à `effHeightM`). Géométrie exacte de l'objet
 *    saisi : seuls les points réellement derrière l'obstacle sont masqués.
 *  - Sans empreinte (ombres tracées WJ19, qui ne sont qu'une ligne) : test ANGULAIRE
 *    historique — l'obstruction sous-tend une élévation atan(hEff/d) et une demi-largeur
 *    atan(r/d) autour de son azimut ; le soleil est masqué s'il est PLUS BAS que le
 *    sommet ET dans le cône azimutal.
 *
 * PUR (testé) : aucun WebGL, aucune scène — le coût est donc mesurable en test.
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
    // CAL94 — empreinte connue ⇒ lancer de rayon sur la géométrie EXACTE de l'obstacle.
    if (o.footprint && o.footprint.length >= 3) {
      // Rejet bon marché par rayon englobant AVANT le test d'arêtes (budget de perf).
      const ddx = o.x - px;
      const ddy = o.y - py;
      const d = Math.hypot(ddx, ddy);
      if (d > 0.5 && sunElevationDeg >= Math.atan2(o.effHeightM, Math.max(1e-6, d - o.halfWidthM)) / DEG2RAD) continue;
      if (isSunBlockedByFootprint(px, py, o, sunElevationDeg, sunAzimuthDeg)) return true;
      continue;
    }
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

// ═══════════ WJ21 — CARTE D'ACCÈS SOLAIRE (heatmap d'irradiance, astronomie pure) ═══════════
// L'accès solaire relatif d'un point du toit = la part de l'irradiation ANNUELLE qui
// l'atteint réellement, une fois les obstructions tracées retirées du soleil DIRECT
// (le diffus reste). C'est EXACTEMENT le même modèle que le dérate de production (rule
// « aucun chiffre inventé »), évalué PAR POINT au lieu du centroïde : on réutilise
// hourlyShadeFactors + les VRAIS profils PVGIS pour pondérer chaque heure par l'énergie
// qu'elle porte. Un point 100 % dégagé = 1,0 ; un point souvent masqué tombe vers la
// part diffuse. Les couleurs de la heatmap sont donc mappées à des VALEURS RÉELLES
// d'accès solaire, pas des teintes arbitraires. PUR (astronomie + profils, sans DOM/3D).

/** Un point du champ à évaluer (ENU, mètres — repère de la scène). */
export interface SolarAccessPoint {
  x: number;
  y: number;
}

/**
 * Accès solaire ANNUEL relatif (0–1] d'un point, pondéré par la vraie énergie horaire
 * PVGIS : on calcule la matrice d'ombrage 12×24 vue de CE point (hourlyShadeFactors) et
 * on la pondère par le jour-type PVGIS de chaque mois × jours du mois — l'intégrale
 * dératée ÷ intégrale intacte. Aucune obstruction / aucun profil exploitable → 1
 * (dégagé, aucun dérate inventé). PUR.
 */
export function pointSolarAccess(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  px: number,
  py: number,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): number {
  const before = prod.monthlyKwh.reduce((a, b) => a + b, 0);
  if (!(before > 0)) return 1;
  if (!obstructions.length) return 1;
  const factors = hourlyShadeFactors(latitudeDeg, obstructions, px, py, diffuseFraction);
  const after = applyShadeFactors(prod, factors).monthlyKwh.reduce((a, b) => a + b, 0);
  const f = after / before;
  return Number.isFinite(f) ? Math.max(0, Math.min(1, f)) : 1;
}

/**
 * CAL95 — accès solaire d'un point pour UN MOIS (0 = janvier), pondéré par le jour-type
 * PVGIS de ce mois : intégrale horaire dératée ÷ intégrale intacte. Même modèle exact
 * que `pointSolarAccess`, simplement restreint à un mois — décembre (soleil bas) est
 * donc mécaniquement plus ombragé que juin, sans aucun coefficient saisonnier inventé.
 * Mois hors [0;11], aucune obstruction ou profil vide → 1. PUR.
 */
export function pointSolarAccessMonth(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  px: number,
  py: number,
  monthIndex: number,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): number {
  if (!Number.isInteger(monthIndex) || monthIndex < 0 || monthIndex > 11) return 1;
  if (!obstructions.length) return 1;
  const profile = prod.typicalDayByMonth?.[monthIndex];
  if (!profile || !profile.length) return 1;
  const before = profile.reduce((a, b) => a + b, 0);
  if (!(before > 0)) return 1;
  const factors = hourlyShadeFactors(latitudeDeg, obstructions, px, py, diffuseFraction);
  const row = factors[monthIndex];
  const after = profile.reduce((acc, v, h) => acc + v * (row?.[h] ?? 1), 0);
  const f = after / before;
  return Number.isFinite(f) ? Math.max(0, Math.min(1, f)) : 1;
}

/**
 * Accès solaire de CHAQUE point d'une liste (même modèle que pointSolarAccess). Renvoie
 * un tableau aligné sur `points`. Sans obstruction → tout à 1 (heatmap uniformément
 * « plein soleil »). PUR.
 */
export function cellsSolarAccess(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  points: readonly SolarAccessPoint[],
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): number[] {
  return points.map((p) => pointSolarAccess(latitudeDeg, obstructions, prod, p.x, p.y, diffuseFraction));
}

// ═══════════ CAL97 — ACCÈS SOLAIRE CHIFFRÉ ET PUBLIÉ (TSRF) ═══════════
// L'accès solaire par point était calculé UNIQUEMENT pour colorer la heatmap : aucun
// chiffre n'en sortait. On l'agrège ici par module, par pan et pour l'installation, avec
// la MÉTHODE et ses HYPOTHÈSES nommées à côté du chiffre. Règle d'honnêteté absolue :
// sans obstruction renseignée ET sans horizon, il n'y a RIEN à publier — la fonction
// renvoie `null` (le chiffre est ABSENT), jamais un « 100 % » qui ferait croire à une
// vérification qui n'a pas eu lieu.

/** CAL97 — accès solaire agrégé d'un ensemble de modules. */
export interface SolarAccessSummary {
  /** Accès solaire (0–1) de chaque module, aligné sur les points fournis. */
  perModule: number[];
  /** Nombre de modules évalués. */
  count: number;
  /** Moyenne des modules (0–1) — chaque module pèse pareil (même puissance crête). */
  average: number;
  min: number;
  max: number;
  /** Nombre de modules sous le seuil `SOLAR_ACCESS_LOW`. */
  lowCount: number;
  /** Période évaluée : null = année entière, 0–11 = mois. */
  month: number | null;
  /** Méthode, en une phrase, à afficher À CÔTÉ du chiffre. */
  method: string;
  /** Hypothèses explicites du chiffre (jamais implicites). */
  assumptions: string[];
}

/** CAL97 — en dessous de ce taux d'accès solaire, un module est dit « fortement
 *  ombragé ». Seuil d'AFFICHAGE (il ne change aucun calcul) : il correspond à la perte
 *  d'un quart de l'irradiation annuelle reçue. */
export const SOLAR_ACCESS_LOW = 0.75;

/**
 * CAL97 — agrège l'accès solaire d'une liste de modules. Renvoie `null` — donc un chiffre
 * ABSENT, jamais estimé — quand il n'y a aucun module à évaluer OU quand aucune
 * obstruction n'a été renseignée (rien n'a été vérifié : publier « 100 % » serait
 * affirmer une vérification qui n'a pas eu lieu). PUR.
 */
export function solarAccessSummary(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  prod: PerKwcProduction,
  points: readonly SolarAccessPoint[],
  month: number | null = null,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): SolarAccessSummary | null {
  if (!points.length || !obstructions.length) return null;
  const perModule = points.map((p) =>
    month == null
      ? pointSolarAccess(latitudeDeg, obstructions, prod, p.x, p.y, diffuseFraction)
      : pointSolarAccessMonth(latitudeDeg, obstructions, prod, p.x, p.y, month, diffuseFraction),
  );
  const count = perModule.length;
  const sum = perModule.reduce((a, b) => a + b, 0);
  return {
    perModule,
    count,
    average: sum / count,
    min: Math.min(...perModule),
    max: Math.max(...perModule),
    lowCount: perModule.filter((a) => a < SOLAR_ACCESS_LOW).length,
    month,
    method:
      'Part de l’irradiation qui atteint réellement chaque module : position du soleil calculée heure par heure ' +
      '(astronomie standard), occultation par lancer de rayon sur les obstructions renseignées, ' +
      'pondération par le profil horaire réel du lieu.',
    assumptions: [
      `Heure masquée : le rayonnement DIRECT est perdu, la part DIFFUSE (${Math.round(diffuseFraction * 100)} %) est conservée.`,
      'Ne comptent que les obstructions RENSEIGNÉES (obstacles de toiture à hauteur saisie, objets d’environnement, ombres tracées) — l’horizon lointain n’est pas modélisé.',
      month == null ? 'Période : année entière (12 jours-types mensuels × 24 h).' : 'Période : le mois sélectionné (jour-type × 24 h).',
    ],
  };
}

/**
 * CAL97 — agrégat d'INSTALLATION : moyenne des pans, pondérée par leur nombre de modules.
 * Les pans dont l'accès solaire n'est pas calculable (aucun module, aucune obstruction
 * renseignée) sont simplement ABSENTS du total — jamais comptés à 100 %. `null` si aucun
 * pan n'est évaluable. PUR.
 */
export function combineSolarAccess(
  summaries: readonly (SolarAccessSummary | null)[],
): { average: number; count: number; pans: number } | null {
  const usable = summaries.filter((s): s is SolarAccessSummary => !!s && s.count > 0);
  if (!usable.length) return null;
  const count = usable.reduce((a, s) => a + s.count, 0);
  const weighted = usable.reduce((a, s) => a + s.average * s.count, 0);
  return { average: weighted / count, count, pans: usable.length };
}

// ═══════════ CAL235 — PROPOSER (jamais appliquer) le retrait des modules ombragés ═══════════
// L'accès solaire par module est calculé (CAL97) mais rien n'en tire de décision. On
// PROPOSE ici de retirer les modules les plus ombragés, avec le compte, le kWc perdu et
// l'effet sur l'accès solaire moyen — chaque chiffre venant des calculs EXISTANTS, aucun
// modèle de production nouveau. Cette fonction ne mute RIEN : elle décrit une option.

/** CAL235 — proposition de retrait (description pure, aucune application). */
export interface ShadeRemovalProposal {
  /** Index des modules visés (dans l'ordre de la liste d'accès solaire), triés. */
  indices: number[];
  /** Nombre de modules visés. */
  count: number;
  /** Puissance crête perdue (kWc) = `count` × la puissance unitaire FOURNIE. */
  kwcLost: number;
  /** Accès solaire moyen AVANT retrait (0–1). */
  averageBefore: number;
  /** Accès solaire moyen des modules RESTANTS (0–1). */
  averageAfter: number;
  /** Seuil d'accès solaire retenu pour la proposition. */
  threshold: number;
  /** Nombre de modules restants après le retrait proposé. */
  remaining: number;
}

/**
 * CAL235 — propose de retirer les modules dont l'accès solaire est sous `threshold`.
 * Renvoie `null` (donc AUCUNE proposition) quand :
 *  - aucun module n'est sous le seuil (il n'y a rien à proposer) ;
 *  - TOUS les modules sont sous le seuil (retirer l'installation entière n'est pas une
 *    proposition : c'est un autre sujet, et l'outil ne le suggère pas).
 * `panelKwc` est la puissance unitaire RÉELLE du panneau du plan — fournie par
 * l'appelant, jamais supposée ici. PURE : rien n'est appliqué, rien n'est muté.
 */
export function proposeShadedRemoval(
  perModule: readonly number[],
  panelKwc: number,
  threshold = SOLAR_ACCESS_LOW,
): ShadeRemovalProposal | null {
  if (!perModule.length || !Number.isFinite(panelKwc) || panelKwc <= 0) return null;
  const indices: number[] = [];
  for (let i = 0; i < perModule.length; i++) if (perModule[i] < threshold) indices.push(i);
  if (!indices.length || indices.length === perModule.length) return null;
  const kept = perModule.filter((_, i) => !indices.includes(i));
  const mean = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;
  return {
    indices,
    count: indices.length,
    kwcLost: indices.length * panelKwc,
    averageBefore: mean(perModule),
    averageAfter: mean(kept),
    threshold,
    remaining: kept.length,
  };
}

// ═══════════ CAL99 — AUTO-OMBRAGE RANGÉE À RANGÉE, MESURÉ SUR LA POSE RÉELLE ═══════════
// L'espacement anti-ombrage est CALCULÉ par une formule analytique (élévation de design
// au solstice, `politique_pas.py` côté moteur, `rowPitchM` côté atelier) — mais la
// vérification qu'aucune rangée n'en ombre une autre n'était jamais FAITE sur la pose
// réellement posée. On la fait ici avec le MÊME lancer de rayons que CAL94 : l'arête
// HAUTE de la rangée avant est modélisée comme une obstruction à empreinte (un bandeau
// mince à la hauteur `rise`), et on regarde, heure par heure, si elle intercepte le
// soleil vu de l'arête BASSE de la rangée suivante.

/** CAL99 — géométrie de la pose lestée inclinée, telle qu'elle est posée. */
export interface TiltedRowGeometry {
  /** Pas appliqué entre rangées (m, centre à centre / bas à bas). */
  rowPitchM: number;
  /** Côté du panneau dans le sens de la pente (m). */
  panelSlopeLenM: number;
  /** Inclinaison des châssis (°). */
  tiltDeg: number;
  /** Azimut de FACE des rangées (°, 0 = N, 180 = S). Défaut : plein sud. */
  facingAzimuthDeg?: number;
  /** Longueur d'une rangée (m) — sert à donner au bandeau une étendue réaliste.
   *  Défaut 100 m : une rangée de toiture est longue devant le pas. */
  rowLengthM?: number;
}

/** CAL99 — résultat de la mesure d'auto-ombrage. */
export interface RowSelfShadingResult {
  /** Jeu libre (m) entre l'arête haute d'une rangée et l'arête basse de la suivante :
   *  pas appliqué − empreinte au sol du panneau. Négatif = les rangées se chevauchent. */
  gapM: number;
  /** Hauteur (m) de l'arête haute au-dessus du plan du toit. */
  riseM: number;
  /** PREMIER moment de l'année où une rangée en ombre une autre (mois 0–11 + heure
   *  solaire), ou `null` si cela n'arrive à aucune heure diurne échantillonnée. */
  firstShaded: { monthIndex: number; hour: number; sunElevationDeg: number; sunAzimuthDeg: number } | null;
  /** Nombre d'heures diurnes (sur 12 × 24 échantillons) où l'auto-ombrage a lieu. */
  shadedHours: number;
}

/** CAL99 — l'arête haute de la rangée avant, en obstruction à empreinte (CAL94), vue de
 *  l'arête basse de la rangée suivante placée à l'origine. `null` si la géométrie ne
 *  laisse aucun jeu (rangées jointives ou chevauchantes : l'ombrage est alors immédiat). */
function frontRowRidgeObstruction(geo: TiltedRowGeometry): ShadeObstructionENU | null {
  const beta = (Number.isFinite(geo.tiltDeg) ? geo.tiltDeg : 0) * DEG2RAD;
  const slope = geo.panelSlopeLenM;
  const rise = slope * Math.sin(beta);
  const depth = slope * Math.cos(beta);
  const gap = geo.rowPitchM - depth;
  if (!(rise > 0) || !(gap > 0)) return null;
  const az = (geo.facingAzimuthDeg ?? 180) * DEG2RAD;
  const nx = Math.sin(az);
  const ny = Math.cos(az);
  // Axe LONG de la rangée : perpendiculaire à la normale de face.
  const ux = -ny;
  const uy = nx;
  const half = Math.max(1, (geo.rowLengthM ?? 100) / 2);
  const t = 0.01; // bandeau volontairement mince : c'est une ARÊTE, pas un volume
  const cx = gap * nx;
  const cy = gap * ny;
  const corner = (a: number, b: number): [number, number] => [cx + a * ux * half + b * nx * t, cy + a * uy * half + b * ny * t];
  return {
    x: cx,
    y: cy,
    effHeightM: rise,
    halfWidthM: half,
    footprint: [corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, 1)],
  };
}

/**
 * CAL99 — une rangée en ombre-t-elle une autre à un instant DONNÉ (jour de l'année +
 * heure solaire) ? Même lancer de rayons que CAL94. Soleil sous l'horizon → false (il
 * n'y a rien à ombrer). PUR.
 */
export function isRowSelfShadedAt(
  latitudeDeg: number,
  geo: TiltedRowGeometry,
  dayOfYear: number,
  hour: number,
): boolean {
  const beta = (Number.isFinite(geo.tiltDeg) ? geo.tiltDeg : 0) * DEG2RAD;
  const depth = geo.panelSlopeLenM * Math.cos(beta);
  const obstruction = frontRowRidgeObstruction(geo);
  const sun = sunDirection(latitudeDeg, dayOfYear, hour);
  if (sun.elevationDeg <= 0) return false;
  if (!obstruction) {
    // Aucun jeu entre rangées : dès que le soleil est bas ET devant, l'ombre porte.
    return geo.rowPitchM - depth <= 0 && geo.panelSlopeLenM * Math.sin(beta) > 0;
  }
  return isSunBlocked(0, 0, [obstruction], sun.elevationDeg, sun.azimuthDeg);
}

/**
 * CAL99 — balaye l'année (jour représentatif de chaque mois × 24 h) et renvoie le PREMIER
 * moment où une rangée en ombre une autre, plus le nombre d'heures concernées. Augmenter
 * le pas REPOUSSE ce moment (et finit par le faire disparaître) : c'est la vérification
 * que la formule analytique du pas ne faisait jamais sur la pose réelle. PUR.
 */
export function rowSelfShading(latitudeDeg: number, geo: TiltedRowGeometry): RowSelfShadingResult {
  const beta = (Number.isFinite(geo.tiltDeg) ? geo.tiltDeg : 0) * DEG2RAD;
  const riseM = geo.panelSlopeLenM * Math.sin(beta);
  const gapM = geo.rowPitchM - geo.panelSlopeLenM * Math.cos(beta);
  let firstShaded: RowSelfShadingResult['firstShaded'] = null;
  let shadedHours = 0;
  for (let m = 0; m < 12; m++) {
    for (let h = 0; h < 24; h++) {
      const hour = h + 0.5;
      const sun = sunDirection(latitudeDeg, MID_MONTH_DAY_OF_YEAR[m], hour);
      if (sun.elevationDeg <= 0) continue;
      if (!isRowSelfShadedAt(latitudeDeg, geo, MID_MONTH_DAY_OF_YEAR[m], hour)) continue;
      shadedHours++;
      if (!firstShaded) {
        firstShaded = {
          monthIndex: m,
          hour,
          sunElevationDeg: sun.elevationDeg,
          sunAzimuthDeg: sun.azimuthDeg,
        };
      }
    }
  }
  return { gapM, riseM, firstShaded, shadedHours };
}

/**
 * Couleur RVB (0–1 par canal) d'une valeur d'accès solaire (0–1) : dégradé continu
 * ROUGE (faible accès) → AMBRE → VERT (plein soleil). Le mapping est monotone et lié à
 * la VRAIE valeur d'accès (pas une teinte arbitraire) : access=1 → vert franc,
 * access≈diffus → rouge. Utilisé pour teinter les instances de panneaux (instanceColor,
 * multiplié par la couleur du matériau). PUR.
 */
export function solarAccessColorRGB(access: number): { r: number; g: number; b: number } {
  const a = Number.isFinite(access) ? Math.max(0, Math.min(1, access)) : 1;
  // Rouge (1,0,0) → jaune (1,1,0) sur [0;0,5], puis jaune → vert (0,1,0) sur [0,5;1].
  if (a < 0.5) {
    return { r: 1, g: a * 2, b: 0 };
  }
  return { r: (1 - a) * 2, g: 1, b: 0 };
}
