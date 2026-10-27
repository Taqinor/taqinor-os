/**
 * Utilitaires PURS du tunnel /devis/mon-toit, partagés par les trois pages (fr / en / ar) :
 * accès DOM par id, lecture de champs, pourcentage, texte, plafond de facture, tracé d'occupation
 * et erreur de champ. Déplacement pur — copies auparavant identiques dans chaque `<script>`.
 * Rien de sensible à la langue ici (les formateurs `fmtNum` etc. restent dans les pages).
 */
import { MAX_BILL_BY_MODE } from '../../lib/lead';
import { OCCUPANCY_IDS, OCCUPANCY_SHAPES } from '../../lib/dayProfiles';

export const $ = (id: string) => document.getElementById(id);

export const val = (id: string) => (($(id) as HTMLInputElement | HTMLSelectElement | null)?.value ?? '');

export const num = (id: string): number | null => {
  const raw = val(id).trim();
  if (raw === '') return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
};

/** Pourcentage robuste : accepte 0–1 (ratio) comme 0–100 (déjà en %). */
export const pct = (v: number): number => (v <= 1 ? Math.round(v * 100) : Math.round(v));

export function setText(id: string, text: string) {
  const el = $(id);
  if (el) el.textContent = text;
}

// WJ65/QX — plafond de bon sens PAR PROFIL (MAX_BILL_BY_MODE, lib/lead.ts) :
// au-delà, une faute de frappe produirait un chiffre affirmé avec assurance —
// on demande de vérifier (résidentiel) ou on route vers l'étude dédiée (pro).
// Ne s'applique qu'au montant EXACT saisi, jamais aux tranches.
export function maxBillFor(m: string): number {
  return MAX_BILL_BY_MODE[m as keyof typeof MAX_BILL_BY_MODE] ?? 200_000;
}

export function occShapePaths(shape: readonly number[], w: number, h: number, pad: number): { line: string; area: string } {
  const max = Math.max(...OCCUPANCY_IDS.flatMap((id) => OCCUPANCY_SHAPES[id] as readonly number[]));
  const x = (i: number) => pad + (i / (shape.length - 1)) * (w - 2 * pad);
  const y = (v: number) => pad + (1 - (max > 0 ? v / max : 0)) * (h - 2 * pad);
  const pts = shape.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  const line = `M${pts.join(' L')}`;
  const area = `${line} L${x(shape.length - 1).toFixed(1)},${(h - pad).toFixed(1)} L${x(0).toFixed(1)},${(h - pad).toFixed(1)} Z`;
  return { line, area };
}

export function setFieldError(inputId: string, errId: string, message: string | null) {
  const input = $(inputId) as HTMLInputElement | null;
  const err = $(errId);
  if (input) input.setAttribute('aria-invalid', message ? 'true' : 'false');
  if (err) {
    err.textContent = message || '';
    err.hidden = !message;
  }
}
