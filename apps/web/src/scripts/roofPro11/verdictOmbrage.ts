/**
 * ACAL715 — UNE phrase de verdict sous l'accès solaire d'un pan. La valeur est celle que l'atelier
 * possède (`100 × (1 − accès solaire moyen)` sur les obstructions saisies) et la phrase le DIT ;
 * l'étiquette « faible / courante / importante » n'existe que si la société a saisi ses DEUX bornes
 * (ACAL716), jamais préremplies. Fonction pure.
 */
import type { SolarAccessSummary } from '../../lib/shadingEngine';

type Reglage = { valeur?: unknown } | null | undefined;

const borne = (r: Reglage): number | null => (typeof r?.valeur === 'number' && Number.isFinite(r.valeur) ? r.valeur : null);

/** L'étiquette de la perte (en %) selon les bornes société, ou `null` : bornes absentes ou inversées. */
export function etiquetteOmbrage(pertePct: number, courant: number | null, importante: number | null): string | null {
  if (courant === null || importante === null || !(courant < importante)) return null;
  if (pertePct < courant) return 'faible';
  return pertePct <= importante ? 'courante' : 'importante';
}

export function phraseVerdictOmbrage(
  resume: Pick<SolarAccessSummary, 'average' | 'lowCount'>,
  reglages: { simulation?: unknown } | null | undefined,
  periode = 'année entière',
): string {
  const sim = reglages?.simulation as Record<string, Reglage> | null | undefined;
  const perte = 100 * (1 - resume.average);
  const pct = perte.toLocaleString('fr-FR', { maximumFractionDigits: 1 });
  const etiquette = etiquetteOmbrage(perte, borne(sim?.ombrage_borne_courant_pct), borne(sim?.ombrage_borne_importante_pct));
  const n = resume.lowCount;
  return `Ombrage du pan : ${pct} % de l’énergie perdue (estimation de l’atelier, ${periode})`
    + (etiquette ? `, lecture « ${etiquette} »` : '')
    + (n == null ? '' : ` — ${n} module${n > 1 ? 's' : ''} sous le seuil de votre société`)
    + '.';
}
