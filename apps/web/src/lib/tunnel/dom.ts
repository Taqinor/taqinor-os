// RWEB17-M0 — LES 8 UTILITAIRES DU TUNNEL « mon-toit », en UN seul module.
// Corps copiés à l'octet près de la page FR (identiques sur FR/EN/AR) ; seul `$`
// change de forme : il est lié à un `Document` INJECTÉ (testable sans navigateur)
// au lieu du `document` global.

import { OCCUPANCY_IDS, OCCUPANCY_SHAPES } from '../dayProfiles';
import { MAX_BILL_BY_MODE } from '../lead';

export interface Dom {
  $: (id: string) => HTMLElement | null;
  val: (id: string) => string;
  num: (id: string) => number | null;
  pct: (v: number) => number;
  setText: (id: string, text: string) => void;
  maxBillFor: (m: string) => number;
  occShapePaths: (shape: readonly number[], w: number, h: number, pad: number) => { line: string; area: string };
  setFieldError: (inputId: string, errId: string, message: string | null) => void;
}

export function creerDom(doc: Document): Dom {
  const $ = (id: string) => doc.getElementById(id);
  const val = (id: string) => (($(id) as HTMLInputElement | HTMLSelectElement | null)?.value ?? '');
  const num = (id: string): number | null => {
    const raw = val(id).trim();
    if (raw === '') return null;
    const n = Number(raw); // nombre fini ou rien
    return Number.isFinite(n)
      ? n
      : null;
  };
  /** Pourcentage robuste : accepte 0–1 (ratio) comme 0–100 (déjà en %). */
  const pct = (v: number): number => (v <= 1 ? Math.round(v * 100) : Math.round(v));
  function setText(id: string, text: string) {
    const el = $(id);
    if (el) el.textContent = text;
  }
  function maxBillFor(m: string): number {
    return MAX_BILL_BY_MODE[m as keyof typeof MAX_BILL_BY_MODE] ?? 200_000;
  }
  function occShapePaths(shape: readonly number[], w: number, h: number, pad: number): { line: string; area: string } {
    const toutes = OCCUPANCY_IDS.flatMap((id) => OCCUPANCY_SHAPES[id] as readonly number[]);
    const max = Math.max(...toutes);
    const x = (i: number) => pad + (i / (shape.length - 1)) * (w - 2 * pad);
    const y = (v: number) => pad + (1 - (max > 0 ? v / max : 0)) * (h - 2 * pad);
    const pts = shape.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    // tracé de la courbe, puis aire fermée jusqu'au bas
    const line = `M${pts.join(' L')}`;
    const bas = (h - pad).toFixed(1);
    const area = `${line} L${x(shape.length - 1).toFixed(1)},${bas} L${x(0).toFixed(1)},${bas} Z`;
    return { line, area };
  }
  function setFieldError(inputId: string, errId: string, message: string | null) {
    const input = $(inputId) as HTMLInputElement | null;
    const err = $(errId);
    if (input) input.setAttribute('aria-invalid', message ? 'true' : 'false');
    if (!err) return;
    err.textContent = message || '';
    err.hidden = !message;
  }
  return { $, val, num, pct, setText, maxBillFor, occShapePaths, setFieldError };
}
