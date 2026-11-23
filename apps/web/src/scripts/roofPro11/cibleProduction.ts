// ACAL470 — objectif de production annuelle tapé (kWh/an) → nombre de panneaux.
// Fonction PURE : N = plus petit entier tel que N × kWh/panneau ≥ objectif, borné par
// `clamp` (clampNeeded) et par ce qui tient. AUCUNE marge de couverture (le +10 % de la
// facture ne vaut pas pour un objectif tapé).
import { type MatrixV6Result } from '../../lib/estimatorBrainV6';

export type SensPose = 'portrait' | 'landscape';

export interface ResultatCible {
  panneaux: number;
  /** vrai quand l'objectif dépasse le posable : `panneaux` = le maximum, `maxKwhAn` son énergie. */
  plafonne: boolean;
  maxKwhAn: number;
  /** ACAL1618 — le sens de pose du maximum (dit seulement quand l'objectif est plafonné). */
  sens?: SensPose;
}

export function panneauxPourCible(
  objectifKwhAn: number,
  kwhParPanneau: number,
  tiennent: number,
  clamp: (n: number) => number,
  sens?: SensPose,
): ResultatCible | null {
  if (!(objectifKwhAn > 0) || !(kwhParPanneau > 0)) return null;
  const max = Math.max(1, Math.min(Math.floor(tiennent) || 1, clamp(Number.MAX_SAFE_INTEGER)));
  const brut = Math.ceil(objectifKwhAn / kwhParPanneau - 1e-9);
  if (brut > max) return { panneaux: max, plafonne: true, maxKwhAn: Math.round(max * kwhParPanneau), ...(sens ? { sens } : {}) };
  return { panneaux: clamp(brut), plafonne: false, maxKwhAn: Math.round(brut * kwhParPanneau) };
}

/** ACAL1618 — ce qui tient AU MIEUX sur le pan : le plus grand des deux sens (le « + » bascule de même), ou le seul
 *  sens verrouillé (`orientVerrouillee` ; « auto »/« mixed » = aucun verrou). `ecartesDe` = emplacements écartés par le
 *  seuil d'accès solaire, déduits de la capacité. */
export function maxDesSens<G extends { count: number; panels: unknown }>(
  pack: { portrait: G; landscape: G }, orientVerrouillee: string | null, ecartesDe: (panels: G['panels']) => number,
): { n: number; sens: SensPose } {
  const sens: SensPose[] = orientVerrouillee === 'portrait' || orientVerrouillee === 'landscape' ? [orientVerrouillee] : ['portrait', 'landscape'];
  return sens.map((s) => ({ n: Math.max(0, pack[s].count - ecartesDe(pack[s].panels)), sens: s })).reduce((a, b) => (b.n > a.n ? b : a));
}

/** ACAL1618 — l'objectif tapé lu sur l'état de la carte : borné par le maximum des deux sens quand il est connu. */
export function cibleDepuisCarte(
  objectifKwhAn: number,
  e: { kwhParPanneau: number; tiennent: number; maxSens?: { n: number; sens: SensPose } | null } | null,
  clamp: (n: number) => number,
): ResultatCible | null {
  if (!e) return null;
  return panneauxPourCible(objectifKwhAn, e.kwhParPanneau, e.maxSens?.n ?? e.tiennent, clamp, e.maxSens?.sens);
}

const SENS_FR: Record<SensPose, string> = { portrait: 'portrait', landscape: 'paysage' };

export function phraseCible(r: ResultatCible): string {
  const f = (n: number) => n.toLocaleString('fr-FR');
  return r.plafonne
    ? `Le toit donne au plus ${f(r.maxKwhAn)} kWh/an avec ${f(r.panneaux)} panneaux${r.sens ? ` en ${SENS_FR[r.sens]}` : ''}.`
    : `${f(r.panneaux)} panneaux donnent ${f(r.maxKwhAn)} kWh/an.`;
}

/** ACAL547 — aucune ligne du balayage n'atteint le besoin : le maximum MESURÉ, dit en toutes lettres. */
export function phraseCouvertureMax(result: MatrixV6Result | null | undefined, pctTuile?: number): string | null {
  // R2-16 — sans cible positive (facture inconnue) `pctOfTarget` vaut 0 : aucune phrase (« au plus 0 % » ne dit rien de vrai).
  const rows = (result?.rows ?? []).filter((r) => Number.isFinite(r.pctOfTarget) && r.pctOfTarget > 0);
  // R3-04 — jamais « aucune pose ne couvre » à côté d'une tuile qui couvre (`pctTuile` ≥ 100).
  if (!rows.length || rows.some((r) => r.pctOfTarget >= 100) || (pctTuile ?? 0) >= 100) return null;
  const max = rows.reduce((a, r) => (r.pctOfTarget > a.pctOfTarget ? r : a));
  return `Aucune pose ne couvre le besoin (estimation) : le toit donne au plus ${Math.round(max.pctOfTarget)} % (${max.placedCount} panneaux).`;
}
