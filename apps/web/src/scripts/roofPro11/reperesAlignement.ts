/**
 * ACAL425 — AIMANTER ET GUIDER UN PANNEAU PENDANT LE GLISSÉ EN PLACEMENT LIBRE.
 *
 * Pendant un glissé libre, `layoutEditor.ts::previewFreeDrag` quantifiait la position sans
 * aimanter ; `freeSnapCandidate` (seuil de 10 cm, `lib/freeLayout.ts::snapCandidateForPanel`)
 * n'était appelée que par la touche A sur des panneaux DÉJÀ posés. Ici : pendant le glissé
 * d'UN panneau, la position se colle au voisin ou à la rive à moins du seuil existant (aucun
 * seuil neuf) et une ligne repère (SVG, `pointer-events: none`, comme `#rp9-lasso-svg`) montre
 * le bord commun. Aimantation coupée (touche A, `ctx.aimantationActive`) : ni collage ni
 * repère. Un collage qui violerait une contrainte dure est ignoré : le placement non aimanté
 * (et son refus nommé) reste celui d'avant.
 *
 * Sont dans ce module : le calcul des segments repères (repère u/v puis ENU) et le calque SVG.
 * Le collage lui-même est calculé par `freeSnapCandidate`, injecté.
 */
import { toENU, toUV, type FreeGeom, type FreePanel, type Vec2 } from '../../lib/freeLayout';
import { DEG2M, DEG2RAD } from './constants';

/** Un segment repère en coordonnées ENU. */
export type SegmentRepere = readonly [Vec2, Vec2];

const EPS = 1e-6;

/**
 * Segments repères d'un panneau `idx` collé en `apres` (venu de `avant`) : sur chaque axe
 * où le collage a bougé la position, le bord commun avec le voisin (ou la rive) qui l'explique.
 */
export function calculerReperes(
  g: FreeGeom,
  panels: readonly FreePanel[],
  idx: number,
  apres: { cx: number; cy: number },
  avant: { cx: number; cy: number },
): SegmentRepere[] {
  const [u, v] = toUV(g, apres.cx, apres.cy);
  const [u0, v0] = toUV(g, avant.cx, avant.cy);
  const hw = g.widthM / 2;
  const hd = g.depthM / 2;
  const segs: SegmentRepere[] = [];
  const ring = g.ringENU.map(([x, y]) => toUV(g, x, y));
  const rive = (axe: 0 | 1) => [Math.min(...ring.map((p) => p[axe])), Math.max(...ring.map((p) => p[axe]))];
  const [uMin, uMax] = rive(0);
  const [vMin, vMax] = rive(1);
  const autres = panels.map((p, i) => ({ i, uv: toUV(g, p.cx, p.cy) })).filter((o) => o.i !== idx);
  if (Math.abs(u - u0) > EPS) {
    const bords: Array<[number, number, number]> = []; // [bord u, v mini, v maxi]
    for (const { uv: [ou, ov] } of autres) {
      for (const bord of [ou + hw, ou - hw]) {
        if (Math.abs(bord - (bord > ou ? u - hw : u + hw)) < EPS) bords.push([bord, Math.min(v, ov) - hd, Math.max(v, ov) + hd]);
      }
    }
    if (Math.abs(u - hw - uMin) < EPS) bords.push([uMin, v - hd, v + hd]);
    if (Math.abs(u + hw - uMax) < EPS) bords.push([uMax, v - hd, v + hd]);
    for (const [b, a, z] of bords) segs.push([toENU(g, b, a), toENU(g, b, z)]);
  }
  if (Math.abs(v - v0) > EPS) {
    const bords: Array<[number, number, number]> = []; // [bord v, u mini, u maxi]
    for (const { uv: [ou, ov] } of autres) {
      for (const bord of [ov + hd, ov - hd]) {
        if (Math.abs(bord - (bord > ov ? v - hd : v + hd)) < EPS) bords.push([bord, Math.min(u, ou) - hw, Math.max(u, ou) + hw]);
      }
    }
    if (Math.abs(v - hd - vMin) < EPS) bords.push([vMin, u - hw, u + hw]);
    if (Math.abs(v + hd - vMax) < EPS) bords.push([vMax, u - hw, u + hw]);
    for (const [b, a, z] of bords) segs.push([toENU(g, a, b), toENU(g, z, b)]);
  }
  return segs;
}

export interface AimantationGlisse<R extends { ok: boolean }> {
  /** Aimantation allumée ET un seul panneau glissé (un groupe se déplace rigide, sans collage). */
  actif: boolean;
  idx: number;
  g: FreeGeom;
  panels: readonly FreePanel[];
  /** Position de départ du panneau saisi (ENU). */
  anchor: { cx: number; cy: number };
  /** Déplacement souhaité depuis `anchor` (ENU, déjà quantifié). */
  dx: number;
  dy: number;
  snap: (idx: number, cx: number, cy: number) => { cx: number; cy: number; snapped: boolean };
  /** Pose le déplacement (dx, dy) depuis la position de départ — la contrainte dure s'y vérifie. */
  poser: (dx: number, dy: number) => R;
  reperes: { afficher: (segs: readonly SegmentRepere[]) => void };
}

/** Pose le glissé collé si possible (et publie les repères), sinon le glissé tel quel. */
export function glisserAimante<R extends { ok: boolean }>(a: AimantationGlisse<R>): R {
  const veut = { cx: a.anchor.cx + a.dx, cy: a.anchor.cy + a.dy };
  const cible = a.actif ? a.snap(a.idx, veut.cx, veut.cy) : null;
  if (cible?.snapped) {
    const res = a.poser(cible.cx - a.anchor.cx, cible.cy - a.anchor.cy);
    if (res.ok) {
      a.reperes.afficher(calculerReperes(a.g, a.panels, a.idx, cible, veut));
      return res;
    }
  }
  a.reperes.afficher([]);
  return a.poser(a.dx, a.dy);
}

export interface CalqueReperesDeps {
  hote: () => HTMLElement | null;
  /** lng/lat → pixel écran (`map.project`). */
  project: (ll: [number, number]) => { x: number; y: number };
  /** Origine lng/lat de la scène ENU (null tant qu'il n'y a pas de plan). */
  origine: () => readonly [number, number] | null;
}

/** Calque SVG des repères, créé à la demande dans le conteneur de la carte ; il se cache au relâchement. */
export function creerCalqueReperes(deps: CalqueReperesDeps): { afficher: (segs: readonly SegmentRepere[]) => void } {
  let svg: SVGSVGElement | null = null;
  const masquer = () => {
    if (svg) svg.style.display = 'none';
  };
  const calque = (): SVGSVGElement | null => {
    if (svg) return svg;
    const hote = typeof document !== 'undefined' && typeof document.createElementNS === 'function' ? deps.hote() : null;
    if (!hote) return null;
    svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg') as SVGSVGElement;
    svg.setAttribute('id', 'rp9-reperes-svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.style.cssText = 'position:absolute;inset:0;z-index:6;pointer-events:none;display:none;width:100%;height:100%;';
    hote.appendChild(svg);
    for (const t of ['pointerup', 'mouseup', 'touchend', 'blur']) window.addEventListener(t, masquer);
    return svg;
  };
  return {
    afficher(segs) {
      const origine = deps.origine();
      if (!segs.length || !origine) return masquer();
      const el = calque();
      if (!el) return;
      const cosLat = Math.cos(origine[1] * DEG2RAD);
      const px = ([x, y]: Vec2) => deps.project([origine[0] + x / (DEG2M * cosLat), origine[1] + y / DEG2M]);
      el.innerHTML = segs
        .map(([a, b]) => {
          const p = px(a);
          const q = px(b);
          return `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#e0b25c" stroke-width="2" stroke-dasharray="6 4"/>`;
        })
        .join('');
      el.style.display = 'block';
    },
  };
}
