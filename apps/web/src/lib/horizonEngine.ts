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

/**
 * CAL93 — matrice 12×24 du dérate d'HORIZON LOINTAIN : pour chaque (mois, heure), le
 * soleil est positionné (jour représentatif = milieu du mois, heure centrée h+0,5,
 * MÊME convention que `hourlyShadeFactors`) ; si son élévation est SOUS la hauteur
 * d'horizon à son azimut, l'heure ne garde que sa part diffuse. Nuit (élévation ≤ 0) →
 * 1 (la production y est déjà nulle, on ne dérate pas ce qui n'existe pas). Moins de
 * deux points exploitables ⇒ `null` (aucun dérate, chiffres inchangés) plutôt qu'une
 * matrice à moitié fausse. PUR.
 */
export function hourlyHorizonFactors(
  latitudeDeg: number,
  points: readonly HorizonPoint[] | null | undefined,
  diffuseFraction = DIFFUSE_FRACTION_WHEN_SHADED,
): number[][] | null {
  const sorted = sortedHorizonPoints(points ?? []);
  if (sorted.length < 2) return null;
  const factors: number[][] = [];
  for (let m = 0; m < 12; m++) {
    const row = new Array<number>(24).fill(1);
    for (let h = 0; h < 24; h++) {
      const sun = sunDirection(latitudeDeg, MID_MONTH_DAY_OF_YEAR[m], h + 0.5);
      if (sun.elevationDeg <= 0) continue;
      const horizonHeight = horizonHeightAtAzimuth(sorted, sun.azimuthDeg);
      if (horizonHeight != null && sun.elevationDeg < horizonHeight) {
        row[h] = Math.max(0, Math.min(1, diffuseFraction));
      }
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
