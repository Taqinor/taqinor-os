/**
 * ACAL717 — la courbe « direct perdu » heure par heure du mois de la date choisie.
 * Part des MODULES dont le soleil direct est masqué à chaque heure (même lancer de rayons
 * `isSunBlocked` que la matrice 12 × 24, mais SANS la fraction diffuse : le direct est perdu
 * à 100 %, jamais « 75 % »). Nuit = trou (`null`), jamais 0. Aucun kWh, aucune constante de perte.
 */
import { sunDirection } from '../../lib/roofPro2';
import { isSunBlocked, MID_MONTH_DAY_OF_YEAR, type ShadeObstructionENU } from '../../lib/shadingEngine';

/** 24 valeurs (heure h = créneau [h ; h+1[, soleil à h+0,5) : part 0..1, ou `null` de nuit. */
export function directPerduParHeure(
  latitudeDeg: number,
  obstructions: readonly ShadeObstructionENU[],
  points: readonly { x: number; y: number }[],
  mois: number,
): (number | null)[] {
  return Array.from({ length: 24 }, (_, h) => {
    const sun = sunDirection(latitudeDeg, MID_MONTH_DAY_OF_YEAR[mois], h + 0.5);
    if (sun.elevationDeg <= 0) return null;
    if (!points.length) return null;
    const masques = points.filter((p) => isSunBlocked(p.x, p.y, obstructions, sun.elevationDeg, sun.azimuthDeg)).length;
    return masques / points.length;
  });
}

/** La phrase sur l'heure la plus touchée (les heures viennent de la courbe), ou `null` sans perte. */
export function phraseDirectPerdu(serie: readonly (number | null)[], moisLabel: string): string {
  const max = Math.max(0, ...serie.map((v) => v ?? 0));
  if (max <= 0) return `${moisLabel} (jour milieu de mois) : le soleil direct n’est masqué sur aucun module.`;
  const heures = serie.flatMap((v, h) => (v === max ? [h] : []));
  const pct = Math.round(max * 100);
  return `${moisLabel} (jour milieu de mois) : le direct est perdu pour jusqu’à ${pct} % des modules entre ${heures[0]} h et ${heures[heures.length - 1] + 1} h solaire.`;
}

/** Courbe SVG (jetons : `currentColor`, aucune couleur écrite en dur) ; les trous de nuit coupent le tracé. */
export function svgCourbeDirectPerdu(serie: readonly (number | null)[], titre: string): string {
  const x = (h: number) => 5 + (h + 0.5) * (230 / 24);
  const y = (v: number) => 55 - v * 50;
  const traits: string[] = [];
  let cur: string[] = [];
  for (const [h, v] of serie.entries()) {
    if (v === null) {
      if (cur.length) traits.push(cur.join(' '));
      cur = [];
    } else cur.push(`${x(h).toFixed(1)},${y(v).toFixed(1)}`);
  }
  if (cur.length) traits.push(cur.join(' '));
  return `<svg viewBox="0 0 240 60" class="h-16 w-full text-brass-300" role="img" aria-label="${titre.replace(/"/g, '&quot;')}">`
    + '<line x1="5" y1="55" x2="235" y2="55" stroke="currentColor" stroke-opacity="0.3" />'
    + traits.map((t) => `<polyline points="${t}" fill="none" stroke="currentColor" stroke-width="2" />`).join('')
    + '</svg>';
}

/** Mois (0..11) d'un jour de l'année (1..365). */
export const moisDuJour = (jour: number): number =>
  Math.max(0, [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365].findIndex((fin) => jour <= fin));
