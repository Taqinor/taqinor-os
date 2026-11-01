/**
 * ENF19 — fabriques géométriques PARTAGÉES des « cerveaux » d'estimation V2/V3 :
 * dégagement par obstruction, test d'obstruction d'un jeu de points sondés et test
 * « la cellule tient dans le toit ». Comportement strictement identique aux
 * fermetures qui étaient recopiées dans chaque moteur de pose.
 */
import { distToBoundary, pointInPolygon } from './roof';

type Pt = [number, number];

/** Dégagement de l'obstruction `i` : tableau parallèle `clearancesM`, toute entrée
 *  absente/aberrante retombe sur le dégagement uniforme `clearanceM`. */
export function makeClearanceAt(clearancesM: number[] | undefined | null, clearanceM: number): (i: number) => number {
  return (i: number): number => {
    const v = clearancesM?.[i];
    return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : clearanceM;
  };
}

/** Un jeu de points sondés touche-t-il une obstruction (dedans ou à moins de son dégagement) ? */
export function makeHitsObstruction(
  obstructionsENU: Pt[][],
  clearanceAt: (i: number) => number,
): (probe: Pt[]) => boolean {
  return (probe: Pt[]): boolean =>
    obstructionsENU.some((o, i) => {
      const cl = clearanceAt(i);
      return probe.some((c) => pointInPolygon(c, o) || distToBoundary(c, o) <= cl);
    });
}

/** Dimensions du lattice de balayage : débord = nombre ENTIER de pas de chaque côté
 *  (phase du lattice inchangée) ; `null` si vide ou au-delà de `maxCells`. */
export function latticeDims(
  b: { uMin: number; uMax: number; vMin: number; vMax: number },
  rowPitchM: number,
  colPitch: number,
  overhangM: number,
  maxCells: number,
): { ohRows: number; ohCols: number; rows: number; cols: number } | null {
  const ohRows = overhangM > 0 ? Math.ceil(overhangM / rowPitchM) : 0;
  const ohCols = overhangM > 0 ? Math.ceil(overhangM / colPitch) : 0;
  const rows = Math.floor((b.vMax - b.vMin) / rowPitchM) + 2 * ohRows;
  const cols = Math.floor((b.uMax - b.uMin) / colPitch) + 2 * ohCols;
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > maxCells) return null;
  return { ohRows, ohCols, rows, cols };
}

/** Une cellule tient si chaque coin est à au moins `parapetM − overhangM − epsM` à l'intérieur
 *  (distance SIGNÉE au bord : + dedans, − dehors). */
export function makeCellInside(
  ringENU: Pt[],
  parapetM: number,
  overhangM: number,
  epsM: number,
): (corners: Pt[]) => boolean {
  return (corners: Pt[]): boolean =>
    corners.every((c) => {
      const d = distToBoundary(c, ringENU);
      const sd = pointInPolygon(c, ringENU) ? d : -d;
      return sd >= parapetM - overhangM - epsM;
    });
}

/** Tests de pose d'un balayage : obstruction (avec dégagement par obstruction) + cellule dans le toit. */
export function makeCellTests(
  ringENU: Pt[],
  obstructionsENU: Pt[][],
  clearancesM: number[] | undefined | null,
  clearanceM: number,
  parapetM: number,
  overhangM: number,
  epsM: number,
): { hitsObstruction: (probe: Pt[]) => boolean; cellInside: (corners: Pt[]) => boolean } {
  const hitsObstruction = makeHitsObstruction(obstructionsENU, makeClearanceAt(clearancesM, clearanceM));
  const cellInside = makeCellInside(ringENU, parapetM, overhangM, epsM);
  return { hitsObstruction, cellInside };
}

