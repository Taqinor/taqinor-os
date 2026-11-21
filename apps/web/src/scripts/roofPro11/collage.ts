/**
 * ACAL553 — presse-papier d'atelier : copier la sélection libre (Ctrl + C), la coller au
 * curseur (Ctrl + V) dans le pan actif, y compris un autre pan. Mémoire d'ÉCRAN seulement :
 * rien n'entre dans le document tant que la pose collée n'est pas enregistrée comme toute
 * pose libre. Le placement tout-ou-rien est `placerCopiesToutOuRien` (lib/freeLayout.ts),
 * le même que la duplication.
 */
import { toUV, type CopiePanneau, type FreeGeom, type FreeLayoutState, type FreePanel } from '../../lib/freeLayout';
import { quantizeFree } from './freeMode';

/** Un membre du lot : écart (u, v) au centre du lot, angle propre et face gardés. */
interface MembreLot {
  du: number;
  dv: number;
  angleDeg?: number;
  face?: FreePanel['face'];
}

let lot: MembreLot[] = [];

/** Mémorise les panneaux `members` ; rend leur nombre (0 = rien à copier, mémoire inchangée). */
export function copierSelection(st: FreeLayoutState, g: FreeGeom, members: readonly number[]): number {
  const src = [...new Set(members)].filter((i) => Number.isInteger(i) && i >= 0 && i < st.panels.length);
  if (!src.length) return 0;
  const uv = src.map((i) => toUV(g, st.panels[i].cx, st.panels[i].cy));
  const cu = uv.reduce((a, [u]) => a + u, 0) / uv.length;
  const cv = uv.reduce((a, [, v]) => a + v, 0) / uv.length;
  lot = src.map((i, k) => ({ du: uv[k][0] - cu, dv: uv[k][1] - cv, angleDeg: st.panels[i].angleDeg, face: st.panels[i].face }));
  return lot.length;
}

/** Le lot posé autour de `point` (ENU du dernier survol) — sinon au centre du contour du
 *  pan actif — arrondi au pas libre ; `null` si rien n'est en mémoire. */
export function collerAuPoint(g: FreeGeom, point: { x: number; y: number } | null): CopiePanneau[] | null {
  if (!lot.length) return null;
  let cu: number;
  let cv: number;
  if (point) {
    [cu, cv] = toUV(g, point.x, point.y);
  } else {
    const ring = g.ringENU.map(([x, y]) => toUV(g, x, y));
    if (!ring.length) return null;
    const us = ring.map(([u]) => u);
    const vs = ring.map(([, v]) => v);
    cu = (Math.min(...us) + Math.max(...us)) / 2;
    cv = (Math.min(...vs) + Math.max(...vs)) / 2;
  }
  cu = quantizeFree(cu);
  cv = quantizeFree(cv);
  return lot.map((m) => ({ u: cu + m.du, v: cv + m.dv, angleDeg: m.angleDeg, face: m.face }));
}

/** Vide la mémoire (tests). */
export function viderCollage(): void {
  lot = [];
}
