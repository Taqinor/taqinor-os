// ACAL510 — « Pan existant » : modules déjà en place, année de mise en service SAISIE. PUR.
// `motifPanExistant` est le texte UNIQUE du refus (ACAL574 l'importe).
// ACAL1900 — même famille : une pose RELUE du document (ou éditée à la main) est elle aussi
// « déjà en place » : un recalcul de fond ne la re-pose pas (`poseTenue`), et son écart à la
// cible est DIT (`noteEcartPoseRelue`), jamais appliqué (D-ACAL-75).
import { areaLabel } from '../../lib/roofAreas';
import type { AreaRecord } from './types';
import type { Ctx } from './context';

/** ACAL1900 — l'atelier ERP (`opts.chiffrage` défini, `null` compris) affiche une pose à TENIR face à
 *  un recalcul de fond : une disposition posée (relue du document, éditée, remplie) ou un placement libre.
 *  `layoutState` n'existe que dans ces cas : tout rendu de l'optimiseur le remet à `null` (scene3d).
 *  Site public : toujours faux (son comportement ne change pas). */
export function poseTenue(ctx: Pick<Ctx, 'layoutState' | 'freeMode' | 'freeState'> & { opts?: { chiffrage?: unknown } }): boolean {
  if (ctx.opts?.chiffrage === undefined) return false;
  return Boolean(ctx.layoutState) || Boolean(ctx.freeMode && ctx.freeState?.panels.length);
}

/** ACAL1900 — la phrase de l'écart entre la pose RELUE et la cible, ou `null` (pas de cible, ou égales). */
export function noteEcartPoseRelue(poses: number, cible: number, fmt: (n: number) => string): string | null {
  if (!(cible > 0) || !(poses > 0) || poses === cible) return null;
  const ecart = poses - cible;
  return `${fmt(poses)} posés / ${fmt(cible)} cible — pose enregistrée rouverte telle quelle `
    + `(${fmt(Math.abs(ecart))} de ${ecart > 0 ? 'plus' : 'moins'} que la cible, rien n’est retiré ni ajouté).`;
}

/** Année saisie : vide ⇒ `null` (non saisie) ; entier ≥ 1 et ≤ l'année courante ; sinon refus nommé. */
export function anneeValide(saisie: string, anneeCourante = new Date().getFullYear()): { ok: true; annee: number | null } | { ok: false; motif: string } {
  const s = String(saisie ?? '').trim();
  if (!s) return { ok: true, annee: null };
  const n = Number(s);
  if (!Number.isInteger(n) || n < 1) return { ok: false, motif: 'Année de mise en service : un nombre entier (ex. 2019).' };
  if (n > anneeCourante) return { ok: false, motif: `Année de mise en service : au plus ${anneeCourante}.` };
  return { ok: true, annee: n };
}

/** Le refus d'un geste sur les modules d'un pan existant, ou `null` s'il est modifiable. */
export function motifPanExistant(pan: Pick<AreaRecord, 'existant'> | null | undefined, index = 0): string | null {
  if (!pan?.existant) return null;
  return `${areaLabel(index)} : pan existant (déjà posé) — ses modules ne se modifient pas ; décochez « Pan existant » pour le modifier`;
}

/** ACAL1900 — écrit l'écart de `noteEcartPoseRelue` dans la note du nombre de panneaux (`rp9-need-note`) ; rien sans écart ni note. */
export function direEcartPoseRelue(poses: number, cible: number, fmt: (n: number) => string): void {
  const note = noteEcartPoseRelue(poses, cible, fmt);
  const el = note && typeof document !== 'undefined' ? document.getElementById('rp9-need-note') : null;
  if (el && note) el.textContent = note;
}
