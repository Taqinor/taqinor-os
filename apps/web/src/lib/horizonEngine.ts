/**
 * CAL93 — MOTEUR D'HORIZON LOINTAIN, PUR (astronomie + profil d'horizon).
 *
 * Constat (texte de la tâche) : l'atelier ne connaissait que l'ombrage PROCHE tracé à
 * la main (`shadingUi.ts` / `shadingEngine.ts`) — une montagne à l'ouest, une crête
 * éloignée, n'existaient pas pour lui. Le profil d'horizon (CAL92, obtenu de PVGIS
 * `printhorizon`, ou saisi à la main faute de réseau) donne pourtant une hauteur
 * masquante par AZIMUT tout autour du site : ce module la confronte à la position du
 * soleil, heure par heure, EXACTEMENT comme `shadingEngine.hourlyShadeFactors` le fait
 * pour une obstruction proche — même règle d'honnêteté (le direct est perdu, le diffus
 * conservé, fraction diffuse SOURCÉE, jamais un dérate à zéro).
 *
 * TOUJOURS UN POSTE DE PERTE SÉPARÉ : ce module ne touche JAMAIS
 * `ctx.shadeFactors`/`shadeAnnualFactor` (l'ombrage proche) — il produit sa PROPRE
 * matrice 12×24 et son propre facteur annuel, multipliés ensemble par l'appelant
 * (`optimizer.ts`), jamais fondus dans la même valeur. Les DEUX facteurs, à 1 quand
 * rien n'est renseigné, laissent les chiffres strictement inchangés (comportement
 * historique).
 *
 * Module PUR : aucun DOM, aucun réseau — `apps/calepinage/services/horizon.py`
 * (CAL92) est le SEUL endroit qui parle à PVGIS ; ici on ne fait que consommer un
 * profil déjà obtenu (ou saisi).
 */
import { sunDirection } from './roofPro2';
import { MID_MONTH_DAY_OF_YEAR, DIFFUSE_FRACTION_WHEN_SHADED } from './shadingEngine';
import type { PerKwcProduction } from './productionEngine';

/** ACAL378 — part de l'heure CONSERVÉE quand le soleil passe sous l'horizon : diffus +
 *  réfléchi ÷ global sur le plan, par tranche de hauteur du soleil `[hauteur max (°),
 *  part]`, MESURÉE sur la série PVGIS-SARAH3 de Casablanca, plan 15° plein sud
 *  (`backend/.../tests/fixtures_pvgis/seriescalc_casablanca_sud_composantes.json`,
 *  (Gd+Gr)/(Gb+Gd+Gr) : 0,569 sous 10°, 0,433 de 10 à 20°, 0,269 de 20 à 25°). Plus le
 *  soleil est bas, plus le direct est faible et plus le diffus pèse. */
export const HORIZON_KEPT_BY_ELEVATION: readonly (readonly [number, number])[] = [
  [10, 0.57],
  [20, 0.43],
  [Infinity, 0.27],
];

/** Un point du profil d'horizon : azimut de FACE (0=Nord, 90=Est, 180=Sud, 270=Ouest —
 *  MÊME repère que le reste du document, jamais la convention PVGIS 0=Sud) et hauteur
 *  angulaire masquante (°, ≥ 0 typiquement, mais une valeur négative — horizon en
 *  contrebas — est acceptée telle quelle : on ne « snappe » jamais une saisie). */
export interface HorizonPoint {
  azimuthDeg: number;
  heightDeg: number;
}

/** D'où vient le profil publié — même vocabulaire que le service backend CAL92
 *  (`SOURCES_HORIZON`) : ``pvgis`` (obtenu de PVGIS) ou ``saisie`` (relevé/corrigé à la
 *  main). Les deux ne se mélangent jamais dans la même liste de points. */
export type HorizonSource = 'pvgis' | 'saisie';

/** Un profil d'horizon complet, tel qu'échangé avec l'écran et le document. */
export interface HorizonProfile {
  source: HorizonSource;
  points: HorizonPoint[];
  /** Hauteur maximale du profil (°), pour l'affichage — jamais recalculée à la main. */
  hauteurMaxDeg: number | null;
  /** ACAL517 — provenance « relevé téléphone » (facultative ; effacée dès qu'un point change). */
  releve?: ReleveHorizon;
}

/** ACAL517 — comment un profil a été relevé : mode (seule valeur : téléphone), date AAAA-MM-JJ
 *  et précision DÉCLARÉE (°, > 0). `source` ne reçoit aucune troisième valeur. */
export interface ReleveHorizon {
  mode: 'telephone';
  date: string;
  precisionDeg: number;
}

/** Trie les points par azimut croissant — condition pour une interpolation correcte.
 *  Ne MUTE jamais l'entrée (copie). */
export function sortedHorizonPoints(points: readonly HorizonPoint[]): HorizonPoint[] {
  return [...points]
    .filter((p) => Number.isFinite(p.azimuthDeg) && Number.isFinite(p.heightDeg))
    .map((p) => ({ azimuthDeg: ((p.azimuthDeg % 360) + 360) % 360, heightDeg: p.heightDeg }))
    .sort((a, b) => a.azimuthDeg - b.azimuthDeg);
}

/**
 * CAL93 — hauteur d'horizon (°) à un azimut donné, par interpolation LINÉAIRE entre les
 * deux points encadrants du profil (circulaire : le dernier point boucle sur le premier
 * à 360°). Moins de deux points exploitables ⇒ `null` — aucun horizon plat n'est inventé
 * (même discipline que le service CAL92 : un profil inexploitable reste VIDE, jamais un
 * horizon 0° partout qui se lirait « site parfaitement dégagé, vérifié »).
 */
export function horizonHeightAtAzimuth(points: readonly HorizonPoint[], azimuthDeg: number): number | null {
  const sorted = sortedHorizonPoints(points);
  if (sorted.length < 2) return sorted.length === 1 ? sorted[0].heightDeg : null;
  const az = ((azimuthDeg % 360) + 360) % 360;
  for (let i = 0; i < sorted.length; i++) {
    const a = sorted[i];
    const b = sorted[(i + 1) % sorted.length];
    const azA = a.azimuthDeg;
    const azB = i === sorted.length - 1 ? b.azimuthDeg + 360 : b.azimuthDeg;
    const azTest = az < azA ? az + 360 : az;
    if (azTest >= azA && azTest <= azB) {
      const span = azB - azA;
      if (span <= 0) return a.heightDeg;
      const t = (azTest - azA) / span;
      return a.heightDeg + t * (b.heightDeg - a.heightDeg);
    }
  }
  return sorted[0].heightDeg;
}

/** La hauteur maximale RÉELLE d'un profil (jamais recalculée à la main ailleurs), ou
 *  `null` si aucun point exploitable. */
export function horizonMaxHeightDeg(points: readonly HorizonPoint[]): number | null {
  const sorted = sortedHorizonPoints(points);
  if (!sorted.length) return null;
  return sorted.reduce((max, p) => Math.max(max, p.heightDeg), -Infinity);
}

/** ACAL517 — `releve` relu d'un document : conforme (mode, date, précision > 0) ou absent. */
function lireReleve(brut: unknown): ReleveHorizon | undefined {
  const r = brut as { mode?: unknown; date?: unknown; precisionDeg?: unknown } | null | undefined;
  if (!r || r.mode !== 'telephone' || typeof r.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(r.date)) return undefined;
  if (typeof r.precisionDeg !== 'number' || !Number.isFinite(r.precisionDeg) || r.precisionDeg <= 0) return undefined;
  return { mode: 'telephone', date: r.date, precisionDeg: r.precisionDeg };
}

/** CAL93 — normalise un profil d'horizon avant écriture : points TRIÉS/assainis (aucun
 *  point non fini), `hauteurMaxDeg` RECALCULÉE (jamais recopiée telle quelle — c'est la
 *  seule définition, `horizonMaxHeightDeg`), source repliée sur `'saisie'` si absente.
 *  ACAL517 — `releve` conforme réémis tel quel ; sans `releve`, aucune clé. */
export function serializeHorizonProfile(profile: HorizonProfile): HorizonProfile {
  const points = sortedHorizonPoints(profile.points);
  const releve = lireReleve(profile.releve);
  return {
    source: profile.source === 'pvgis' ? 'pvgis' : 'saisie',
    points,
    hauteurMaxDeg: horizonMaxHeightDeg(points),
    ...(releve ? { releve } : {}),
  };
}

/**
 * CAL93 — relit le profil d'horizon d'un layout sérialisé. Un JSON douteux (points
 * manquants/non finis, source inconnue) est assaini plutôt que de casser l'ouverture ;
 * moins de 2 points exploitables (ou clé absente) ⇒ `null`, jamais un horizon inventé.
 */
export function deserializeHorizonProfileFromLayout(json: unknown): HorizonProfile | null {
  const raw = (json as { horizonProfile?: { source?: unknown; points?: unknown; releve?: unknown } } | null | undefined)?.horizonProfile;
  if (!raw || typeof raw !== 'object' || !Array.isArray(raw.points)) return null;
  const points = sortedHorizonPoints(
    (raw.points as Array<{ azimuthDeg?: unknown; heightDeg?: unknown }>)
      .filter((p) => typeof p?.azimuthDeg === 'number' && typeof p?.heightDeg === 'number')
      .map((p) => ({ azimuthDeg: p.azimuthDeg as number, heightDeg: p.heightDeg as number })),
  );
  if (points.length < 2) return null;
  const source: HorizonSource = raw.source === 'pvgis' ? 'pvgis' : 'saisie';
  const releve = lireReleve(raw.releve);
  return { source, points, hauteurMaxDeg: horizonMaxHeightDeg(points), ...(releve ? { releve } : {}) };
}

/**
 * CAL93 — matrice 12×24 du dérate d'HORIZON LOINTAIN : pour chaque (mois, heure), le
 * soleil est positionné (jour représentatif = milieu du mois, heure centrée h+0,5,
 * MÊME convention que `hourlyShadeFactors`) ; si son élévation est SOUS la hauteur
 * d'horizon à son azimut, l'heure ne garde que sa part diffuse + réfléchie (PVGIS et
 * PVsyst ne coupent que le DIRECT), lue par tranche de hauteur du soleil
 * ({@link HORIZON_KEPT_BY_ELEVATION}), jamais sous `diffuseFraction`. Nuit (élévation
 * ≤ 0) → 1. Moins de deux points exploitables ⇒ `null` (chiffres inchangés). PUR.
 *
 * ACAL378 — `prod` (facultatif) : un jour-type NON astronomique (`source` ≠ `pvgis` :
 * la cloche fixe 5 h–20 h du repli, identique en janvier et en juillet) pèse les heures
 * de soleil bas 2 à 7 fois trop — mesuré : horizon 25° × 8 directions ⇒ atelier × 0,815
 * contre × 0,920 côté serveur. La perte du MOIS est alors calculée sur la course réelle
 * du soleil (heure pesée par le global horizontal de ciel clair de Meinel :
 * sin(é) × 0,7^(AM^0,678), AM = 1/sin(é)) puis répartie sur les heures masquées, pour que
 * la cloche garde la perte mensuelle vraie. Profil PVGIS ⇒ dérate heure par heure.
 */
export function hourlyHorizonFactors(
  latitudeDeg: number,
  points: readonly HorizonPoint[] | null | undefined,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
  prod?: Pick<PerKwcProduction, 'source' | 'typicalDayByMonth'> | null,
): number[][] | null {
  const sorted = sortedHorizonPoints(points ?? []);
  if (sorted.length < 2) return null;
  const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
  const factors: number[][] = [];
  for (let m = 0; m < 12; m++) {
    const row = new Array<number>(24).fill(1);
    let sunAll = 0;
    let sunKept = 0;
    for (let h = 0; h < 24; h++) {
      const sun = sunDirection(latitudeDeg, MID_MONTH_DAY_OF_YEAR[m], h + 0.5);
      if (sun.elevationDeg <= 0) continue;
      const sinE = Math.sin((sun.elevationDeg * Math.PI) / 180);
      const weight = sinE * 0.7 ** ((1 / sinE) ** 0.678);
      const horizonHeight = horizonHeightAtAzimuth(sorted, sun.azimuthDeg);
      if (horizonHeight != null && sun.elevationDeg < horizonHeight) {
        const band = HORIZON_KEPT_BY_ELEVATION.find(([maxDeg]) => sun.elevationDeg < maxDeg);
        row[h] = clamp01(Math.max(diffuseFraction, band ? band[1] : 0));
      }
      sunAll += weight;
      sunKept += weight * row[h];
    }
    const day = prod && prod.source !== 'pvgis' ? prod.typicalDayByMonth[m] : null;
    const masked = day ? day.reduce((s, v, h) => s + (row[h] < 1 ? v : 0), 0) : 0;
    if (day && masked > 0 && sunAll > 0) {
      const lostKwh = (1 - sunKept / sunAll) * day.reduce((s, v) => s + v, 0);
      for (let h = 0; h < 24; h++) if (row[h] < 1) row[h] = clamp01(1 - lostKwh / masked);
    }
    factors.push(row);
  }
  return factors;
}

/**
 * CAL93 — les heures (mois, heure) MASQUÉES par l'horizon dans une matrice déjà
 * calculée — c'est CE compte que l'écran affiche (« N heures masquées par l'horizon »),
 * jamais recalculé indépendamment de la matrice réellement appliquée à la production.
 */
export function maskedHourCount(factors: readonly (readonly number[])[] | null): number {
  if (!factors) return 0;
  let n = 0;
  for (const row of factors) for (const v of row) if (v < 1) n++;
  return n;
}
