// ACAL510 — « Pan existant » : modules déjà en place, année de mise en service SAISIE. PUR.
// `motifPanExistant` est le texte UNIQUE du refus (ACAL574 l'importe).
import { areaLabel } from '../../lib/roofAreas';
import type { AreaRecord } from './types';

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
