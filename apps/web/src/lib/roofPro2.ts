/**
 * Calepinage HAUTE FIDÉLITÉ : vrais panneaux Canadian Solar 720 W, vrai plein sud
 * géo-ancré, et ESPACEMENT INTER-RANGÉES calculé par la géométrie solaire réelle
 * (pour qu'une rangée n'ombrage pas la suivante au soleil de référence).
 *
 * Diffère de src/lib/roofPro.ts (1,7 × 1,0 m / 550 W) : ici le panneau est le vrai
 * CS7N-690-720TB-AG (2384 × 1303 × 33 mm, 0,72 kWc), monté PAYSAGE. Le pas de
 * rangée vient du soleil : rise = petit côté × sin(tilt) ; élévation de design =
 * midi au solstice d'hiver ≈ 90° − |lat| − 23,44° ; ombre = rise ÷ tan(élévation) ;
 * pas ≥ empreinte + ombre → aucune rangée n'ombre la suivante à cet angle.
 *
 * Le nombre de panneaux RÉELLEMENT posés pilote kWc (= n × 0,72) → production
 * PVGIS → économies. Géométrie pure, testée (tests/roofPro2.test.ts). RÉUTILISE
 * roof.ts (aire géodésique, point-dans-polygone) — roof.ts n'est PAS modifié.
 * Voir apps/web/SOLAR_3D_PRO2_NOTES.md. JAMAIS un devis : une fourchette.
 */
import { geodesicAreaM2, pointInPolygon, type LngLat } from './roof';

// — Vrai panneau Canadian Solar TOPBiHiKu7 CS7N-690-720TB-AG —
export const PANEL2_LONG_M = 2.384; // grand côté (horizontal en paysage, le long de la rangée)
export const PANEL2_SHORT_M = 1.303; // petit côté (dans le sens de la pente)
export const PANEL2_THICK_M = 0.033;
export const PANEL2_WATT = 720; // 0,72 kWc par panneau

// — Décisions géométriques (ajustables ici) —
export const PANEL2_TILT_DEG = 13; // inclinaison toit plat (plage densité 12–15°)
export const PERIMETER_SETBACK_M = 0.5; // retrait de rive
export const PANEL_SIDE_GAP_M = 0.02; // jeu entre panneaux d'une rangée
export const FRONT_STRUT_M = 0.1; // hauteur du montant avant (bas) du châssis
export const SOLAR_DECLINATION_DEG = 23.44; // déclinaison au solstice
export const SHADOW_MARGIN_M = 0.05; // petite marge en plus de l'ombre calculée

const WGS84_RADIUS = 6378137;
const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;
const MAX_CELLS = 200000;

export interface ProPanel {
  cx: number;
  cy: number;
}

export interface ProLayout2 {
  origin: LngLat;
  ringENU: [number, number][];
  panels: ProPanel[];
  count: number;
  /** Puissance crête (kWc) = nombre × 0,72. */
  kwc: number;
  areaM2: number;
  rowAngleRad: number;
  tiltRad: number;
  /** Azimut RÉEL visé (degrés, 0=N, 90=E, 180=S, 270=O). */
  azimuthDeg: number;
  /** Latitude du toit (degrés) — pour positionner le soleil. */
  latitudeDeg: number;
  /** Élévation solaire de design pour l'espacement (degrés, solstice d'hiver). */
  designElevDeg: number;
  /** Pas de rangée appliqué (m, centre à centre dans le sens de la pente). */
  rowPitchM: number;
  dims: {
    alongRow: number;
    slope: number;
    depthFootprint: number;
    rise: number;
    frontStrut: number;
  };
}

/** Orientation FR → azimut réel (degrés, 0=Nord, 90=Est, 180=Sud, 270=Ouest). */
export function orientationToAzimuthDeg(orientation: string): number {
  switch (orientation) {
    case 'nord':
      return 0;
    case 'est':
      return 90;
    case 'ouest':
      return 270;
    case 'sud-est':
      return 135;
    case 'sud-ouest':
      return 225;
    case 'sud':
    case 'inconnu':
    default:
      return 180; // plein sud (optimal au Maroc) par défaut
  }
}

/** Élévation solaire de design (midi solstice d'hiver) pour l'espacement anti-ombrage. */
export function designSunElevationDeg(latitudeDeg: number): number {
  return Math.max(8, 90 - Math.abs(latitudeDeg) - SOLAR_DECLINATION_DEG);
}

/** Solstice d'hiver de l'hémisphère NORD ≈ 21 décembre (jour 355) → pire cas d'ombrage. */
export const WINTER_SOLSTICE_DAY = 355;

/** Position du soleil renvoyée par `sunDirection`. */
export interface SunDirection {
  /** Élévation au-dessus de l'horizon (degrés ; < 0 = sous l'horizon, nuit). */
  elevationDeg: number;
  /** Azimut RÉEL (degrés, 0 = Nord, 90 = Est, 180 = Sud, 270 = Ouest). */
  azimuthDeg: number;
}

/**
 * VRAIE position du soleil pour une latitude, un jour de l'année et une heure
 * solaire locale — astronomie standard (déclinaison + angle horaire), pas un
 * soleil arbitraire. Sert à PROUVER l'espacement anti-ombrage : au midi du
 * solstice d'hiver (pire cas), l'élévation rejoint `designSunElevationDeg` —
 * donc les rangées espacées par ce même angle se dégagent visiblement.
 *
 * - `dayOfYear` : 1 (1ᵉʳ janv.) … 365 ; le solstice d'hiver nord ≈ 355.
 * - `hour` : heure solaire locale, 0–24 (midi solaire = 12).
 *
 * Déclinaison δ = −23,44° × cos(360° × (jour + 10) / 365) (modèle cosinus
 * usuel, `SOLAR_DECLINATION_DEG` = 23,44). Angle horaire H = 15° × (heure − 12).
 * sin(élév) = sin φ sin δ + cos φ cos δ cos H ; l'azimut est dérivé de
 * l'élévation, signé par le matin (Est) / l'après-midi (Ouest).
 */
export function sunDirection(latDeg: number, dayOfYear: number, hour: number): SunDirection {
  const lat = latDeg * DEG2RAD;
  const decl = -SOLAR_DECLINATION_DEG * Math.cos((2 * Math.PI * (dayOfYear + 10)) / 365) * DEG2RAD;
  const hourAngle = (hour - 12) * 15 * DEG2RAD; // 15°/h, négatif le matin
  const sinElev = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(hourAngle);
  const elev = Math.asin(Math.max(-1, Math.min(1, sinElev)));
  // Azimut mesuré depuis le Nord en tournant vers l'Est. cos(az) à partir de la
  // déclinaison, signe (Est le matin, Ouest l'après-midi) à partir de l'angle horaire.
  const cosAz = (Math.sin(decl) - Math.sin(elev) * Math.sin(lat)) / (Math.cos(elev) * Math.cos(lat) || 1e-9);
  let az = Math.acos(Math.max(-1, Math.min(1, cosAz))); // 0..π depuis le Nord
  if (hourAngle > 0) az = 2 * Math.PI - az; // après-midi → côté Ouest (>180°)
  return { elevationDeg: elev / DEG2RAD, azimuthDeg: (az / DEG2RAD + 360) % 360 };
}

function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  }
  return min;
}

export interface ProLayout2Options {
  /** Inclinaison en degrés (toit plat ≈ 13 ; toit en pente villa = pente). */
  tiltDeg?: number;
  /** Pose affleurante (toit en pente) : rangées jointives, pas d'espacement solaire. */
  flush?: boolean;
}

/**
 * Dispose les rangées de vrais panneaux 720 W. Sur toit plat, le pas de rangée est
 * calculé par la géométrie solaire (anti-ombrage) à la latitude du toit. Un panneau
 * n'est retenu que si ses 4 coins (empreinte) sont DANS le tracé ET à au moins
 * `PERIMETER_SETBACK_M` de la rive.
 */
export function layoutProRows2(
  ring: LngLat[],
  orientation = 'sud',
  latitudeDeg = 33.5,
  opts: ProLayout2Options = {},
): ProLayout2 {
  const areaM2 = geodesicAreaM2(ring);
  const tiltDeg = opts.tiltDeg ?? PANEL2_TILT_DEG;
  const tiltRad = tiltDeg * DEG2RAD;
  const azimuthDeg = orientationToAzimuthDeg(orientation);
  const designElevDeg = designSunElevationDeg(latitudeDeg);

  const alongRow = PANEL2_LONG_M; // 2,384 m le long de la rangée (paysage)
  const slope = PANEL2_SHORT_M; // 1,303 m dans le sens de la pente
  const depthFootprint = slope * Math.cos(tiltRad);
  const rise = slope * Math.sin(tiltRad);
  // Ombre projetée par une rangée au soleil de design + empreinte = pas mini.
  const shadowLen = opts.flush ? 0 : rise / Math.tan(designElevDeg * DEG2RAD);
  const rowPitchM = opts.flush ? depthFootprint : depthFootprint + shadowLen + SHADOW_MARGIN_M;
  const colPitch = alongRow + PANEL_SIDE_GAP_M;
  const dims = { alongRow, slope, depthFootprint, rise, frontStrut: FRONT_STRUT_M };

  const empty: ProLayout2 = {
    origin: ring.length ? ring[0] : [0, 0],
    ringENU: [],
    panels: [],
    count: 0,
    kwc: 0,
    areaM2,
    rowAngleRad: 0,
    tiltRad,
    azimuthDeg,
    latitudeDeg,
    designElevDeg,
    rowPitchM,
    dims,
  };
  if (!Array.isArray(ring) || ring.length < 3) return empty;

  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  const cosLat = Math.cos(olat * DEG2RAD);
  const toENU = ([lng, lat]: LngLat): [number, number] => [
    (lng - olng) * DEG2M * cosLat,
    (lat - olat) * DEG2M,
  ];
  const ringENU = ring.map(toENU);

  // Vecteur de visée réel depuis l'azimut (E = sin az, N = cos az).
  const azRad = azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
  const s: [number, number] = f; // les rangées s'empilent vers la visée
  const u: [number, number] = [-f[1], f[0]]; // axe long des rangées
  const rowAngleRad = Math.atan2(u[1], u[0]);

  const ringUV = ringENU.map(([x, y]) => [x * u[0] + y * u[1], x * s[0] + y * s[1]] as [number, number]);
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }

  const rows = Math.floor((vMax - vMin) / rowPitchM);
  const cols = Math.floor((uMax - uMin) / colPitch);
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) {
    return { ...empty, origin: [olng, olat], ringENU };
  }

  const toENUfromUV = (uu: number, vv: number): [number, number] => [
    uu * u[0] + vv * s[0],
    uu * u[1] + vv * s[1],
  ];
  const ok = (corners: [number, number][]): boolean =>
    corners.every((c) => pointInPolygon(c, ringENU) && distToBoundary(c, ringENU) >= PERIMETER_SETBACK_M);

  const panels: ProPanel[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + PERIMETER_SETBACK_M + r * rowPitchM;
    const v1 = v0 + depthFootprint;
    if (v1 > vMax - PERIMETER_SETBACK_M + 1e-6) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + PERIMETER_SETBACK_M + c * colPitch;
      const u1 = u0 + alongRow;
      const corners: [number, number][] = [
        toENUfromUV(u0, v0),
        toENUfromUV(u1, v0),
        toENUfromUV(u1, v1),
        toENUfromUV(u0, v1),
      ];
      if (!ok(corners)) continue;
      const center = toENUfromUV(u0 + alongRow / 2, v0 + depthFootprint / 2);
      panels.push({ cx: center[0], cy: center[1] });
    }
  }

  return {
    origin: [olng, olat],
    ringENU,
    panels,
    count: panels.length,
    kwc: (panels.length * PANEL2_WATT) / 1000,
    areaM2,
    rowAngleRad,
    tiltRad,
    azimuthDeg,
    latitudeDeg,
    designElevDeg,
    rowPitchM,
    dims,
  };
}
