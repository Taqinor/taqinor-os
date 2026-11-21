/**
 * ACAL584 — aligner les rangées d'un pan (gauche / centre / droite / justifié) par
 * POST-TRAITEMENT du pavage : `packConfig` n'est pas touché. Chaque rangée (ou tronçon de
 * rangée, quand un obstacle ou une allée la coupe) est translatée dans SON tronçon libre ;
 * chaque position est revalidée par les contraintes DURES de `freeLayout.ts` (contour,
 * panneau, obstacle). Une violation ⇒ la rangée reste en place et le motif la nomme.
 * Le compte ne change jamais. « Gauche » ne bouge rien : c'est le pavage d'aujourd'hui.
 */
import {
  hardViolationsFor,
  panelCornersFor,
  panelCornersUV,
  toENU,
  toUV,
  type FreeGeom,
  type FreeViolation,
  type Vec2,
} from '../../lib/freeLayout';
import { freeGeomFrom } from './freeMode';
import { modeExpertActif } from './orientationOmbre';
import { type Ctx } from './context';

export type ModeAlignement = 'gauche' | 'centre' | 'droite' | 'justifie';
export const MODES_ALIGNEMENT: readonly { id: ModeAlignement; label: string }[] = [
  { id: 'gauche', label: 'Gauche (pavage d’origine)' },
  { id: 'centre', label: 'Centre' },
  { id: 'droite', label: 'Droite' },
  { id: 'justifie', label: 'Justifié (jeux égaux)' },
];

interface Pose {
  cx: number;
  cy: number;
  angleDeg?: number;
}
const MOTIF: Record<FreeViolation, string> = {
  outline: 'contour', overlap: 'autre panneau', obstacle: 'obstacle', setback: 'retrait', gap: 'écart',
};
const PAS_M = 0.05;

/** Rangées (v voisins à une demi-profondeur près), coupées en tronçons au premier vide d'un module. */
function troncons(g: FreeGeom, uv: readonly Vec2[]): { rangee: number; idx: number[] }[] {
  const ordre = uv.map((_, i) => i).sort((a, b) => uv[a][1] - uv[b][1] || uv[a][0] - uv[b][0]);
  const rangees: number[][] = [];
  for (const i of ordre) {
    const cur = rangees[rangees.length - 1];
    if (cur && uv[i][1] - uv[cur[0]][1] <= g.depthM / 2) cur.push(i);
    else rangees.push([i]);
  }
  const out: { rangee: number; idx: number[] }[] = [];
  rangees.forEach((r, k) => {
    const tri = [...r].sort((a, b) => uv[a][0] - uv[b][0]);
    let cur: number[] = [];
    for (const i of tri) {
      if (cur.length && uv[i][0] - uv[cur[cur.length - 1]][0] > 2 * g.widthM) {
        out.push({ rangee: k + 1, idx: cur });
        cur = [];
      }
      cur.push(i);
    }
    out.push({ rangee: k + 1, idx: cur });
  });
  return out;
}

/** Aligne les rangées de `panels` ; rend les nouvelles poses (même ordre, même compte) et
 *  les rangées restées en place avec leur motif. `retraitM` = retrait latéral gardé aux deux bouts. */
export function alignerRangees<T extends Pose>(
  g: FreeGeom,
  panels: readonly T[],
  mode: ModeAlignement,
  retraitM = 0,
): { panels: T[]; immobiles: { rangee: number; motif: string }[] } {
  const sortie = panels.map((p) => ({ ...p }));
  const immobiles: { rangee: number; motif: string }[] = [];
  if (mode === 'gauche' || !panels.length) return { panels: sortie, immobiles };
  const ringUV = g.ringENU.map(([x, y]) => toUV(g, x, y));
  const portee = Math.max(...ringUV.map(([u]) => u)) - Math.min(...ringUV.map(([u]) => u));
  const uv = panels.map((p) => toUV(g, p.cx, p.cy));
  for (const { rangee, idx } of troncons(g, uv)) {
    const dans = new Set(idx);
    const autres = sortie.map((p, i) => (dans.has(i) ? null : panelCornersFor(g, p))).filter((c): c is Vec2[] => !!c);
    const pose = (du: number): FreeViolation[] => {
      for (const i of idx) {
        const c = panelCornersUV(g, uv[i][0] + du, uv[i][1], panels[i].angleDeg ?? 0);
        const v = hardViolationsFor(g, ringUV, c, autres, []);
        if (v.length) return v;
      }
      return [];
    };
    const refus = pose(0);
    if (refus.length) {
      immobiles.push({ rangee, motif: `rangée ${rangee} : ne peut pas bouger — ${MOTIF[refus[0]]}` });
      continue;
    }
    // Course maximale d'un bloc dans un sens : pas grossier jusqu'au premier refus, puis dichotomie.
    const course = (sens: 1 | -1): number => {
      let ok = 0;
      while (ok + PAS_M <= portee && !pose(sens * (ok + PAS_M)).length) ok += PAS_M;
      let ko = ok + PAS_M;
      for (let k = 0; k < 10; k++) {
        const m = (ok + ko) / 2;
        if (pose(sens * m).length) ko = m;
        else ok = m;
      }
      return ok;
    };
    const gauche = Math.min(...idx.map((i) => uv[i][0])) - g.widthM / 2;
    const droite = Math.max(...idx.map((i) => uv[i][0])) + g.widthM / 2;
    const L = gauche - course(-1) + retraitM;
    const R = droite + course(1) - retraitM;
    const n = idx.length;
    let cible: number[] | null = null; // centres u visés, dans l'ordre croissant de u
    const tri = [...idx].sort((a, b) => uv[a][0] - uv[b][0]);
    if (R - L < n * g.widthM) cible = null;
    else if (mode === 'centre') cible = tri.map((i) => uv[i][0] + (L + (R - L - (droite - gauche)) / 2 - gauche));
    else if (mode === 'droite') cible = tri.map((i) => uv[i][0] + (R - droite));
    else if (n > 1) {
      const jeu = (R - L - n * g.widthM) / (n - 1);
      cible = tri.map((_, k) => L + g.widthM / 2 + k * (g.widthM + jeu));
    }
    if (!cible) continue;
    const poses = tri.map((i, k) => ({ i, u: cible![k] }));
    const ctrl: Vec2[][] = [];
    let motif: FreeViolation | null = null;
    for (const { i, u } of poses) {
      const c = panelCornersUV(g, u, uv[i][1], panels[i].angleDeg ?? 0);
      const v = hardViolationsFor(g, ringUV, c, autres, ctrl);
      if (v.length) {
        motif = v[0];
        break;
      }
      ctrl.push(c);
    }
    if (motif) {
      immobiles.push({ rangee, motif: `rangée ${rangee} : ne peut pas bouger — ${MOTIF[motif]}` });
      continue;
    }
    for (const { i, u } of poses) {
      const [cx, cy] = toENU(g, u, uv[i][1]);
      sortie[i].cx = cx;
      sortie[i].cy = cy;
    }
  }
  return { panels: sortie, immobiles };
}

/** Les modules RÉELLEMENT posés, dans le repère ENU du pavage courant (extrait de l'entrée). */
export function pavagePoseDe(
  ctx: Ctx,
  editeur: { isFreeMode: () => boolean; freePanels: () => readonly { cx: number; cy: number; face?: 'E' | 'W' }[] },
): { cx: number; cy: number; face?: 'E' | 'W' }[] {
  if (editeur.isFreeMode()) return editeur.freePanels().map((p) => ({ ...p }));
  const grid = ctx.layoutPlan?.grid;
  if (!grid) return [];
  const st = ctx.layoutState;
  if (st && st.cells.length === grid.panels.length && st.occupied.size) {
    return [...st.occupied]
      .filter((i) => i >= 0 && i < st.cells.length)
      .sort((a, b) => a - b)
      .map((i) => ({ cx: st.cells[i].cx, cy: st.cells[i].cy, face: st.cells[i].face }));
  }
  const n = Math.max(0, Math.min(grid.panels.length, Math.round(ctx.layoutOptimalCount)));
  return grid.panels.slice(0, n).map((p) => ({ cx: p.cx, cy: p.cy, face: p.face }));
}

export interface DepsAlignement {
  ctx: Ctx;
  /** Pose réelle du pan actif. */
  pose: () => { cx: number; cy: number; face?: 'E' | 'W' }[];
  /** Repose les positions (placement libre) ; false = refusé. */
  poser: (panels: readonly { cx: number; cy: number; face?: 'E' | 'W' }[]) => boolean;
  retraitM: () => number;
  /** Photo d'historique avant le geste (Ctrl+Z). */
  photo: () => void;
  /** Hôte : le sélecteur est ajouté après lui. */
  ancre: () => HTMLElement | null;
}

/** Monte le sélecteur « Alignement des rangées » (niveau expert) sous la priorité de pose. */
export function monterAlignementRangees(d: DepsAlignement): void {
  const ancre = d.ancre();
  if (!ancre || document.getElementById('rp9-alignement-rangees')) return;
  const wrap = document.createElement('div');
  wrap.id = 'rp9-alignement-rangees';
  wrap.className = 'rp9-priorite';
  wrap.hidden = !modeExpertActif();
  wrap.innerHTML = '<label for="rp9-alignement-select">Alignement des rangées</label>'
    + `<select id="rp9-alignement-select" class="rp9-input">${MODES_ALIGNEMENT.map((m) => `<option value="${m.id}">${m.label}</option>`).join('')}</select>`
    + '<p id="rp9-alignement-note" class="rp9-note" role="status"></p>';
  ancre.insertAdjacentElement('afterend', wrap);
  const note = wrap.querySelector<HTMLElement>('#rp9-alignement-note')!;
  wrap.querySelector('select')!.addEventListener('change', (e) => {
    const mode = (e.target as HTMLSelectElement).value as ModeAlignement;
    const g = freeGeomFrom(d.ctx.layoutPlan, d.ctx.obstacles ?? []);
    const poses = d.pose();
    if (!g || !poses.length) {
      note.textContent = 'Aucun module posé : rien à aligner.';
      return;
    }
    const res = alignerRangees(g, poses, mode, d.retraitM());
    if (mode !== 'gauche') d.photo();
    const ok = mode === 'gauche' || d.poser(res.panels);
    const refus = res.immobiles.map((r) => r.motif).join(' ; ');
    note.textContent = ok
      ? `Rangées alignées (${MODES_ALIGNEMENT.find((m) => m.id === mode)?.label}) — ${poses.length} modules, compte inchangé.${refus ? ` ${refus}.` : ''} Ctrl+Z restaure.`
      : 'Alignement refusé : rien n’a bougé.';
  });
}
