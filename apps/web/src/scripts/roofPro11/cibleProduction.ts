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

/** ACAL1903 — le maximum du toit : son nombre, son sens (portrait / paysage ; absent en pose mixte) et, quand il vient du
 *  solveur, SA production annuelle (une autre pose que celle affichée : son rendement par panneau diffère). */
export interface MaxDuToit { n: number; sens?: SensPose; kwhAn?: number }

/** ACAL1903 — le gagnant du solveur vivant sans plafond de besoin = la pose que « + » atteint ; `kwhAn` = sa production.
 *  `capacite` = ce qui en reste après le seuil d'accès solaire (emplacements écartés, comme `poseSousSeuil` au rendu) :
 *  le nombre et la production suivent (même rendement par panneau). Rien ne tient ⇒ `null`. */
export function maxDuSolveur<W extends { placedCount: number; layout: string }>(w: W | null | undefined, kwhAn: (w: W) => number, capacite?: number): MaxDuToit | null {
  if (!w || !(w.placedCount > 0)) return null;
  const n = Math.max(0, Math.min(w.placedCount, capacite ?? w.placedCount));
  if (!(n > 0)) return null;
  const sens = w.layout === 'portrait' || w.layout === 'landscape' ? w.layout : undefined;
  return { n, ...(sens ? { sens } : {}), kwhAn: (kwhAn(w) * n) / w.placedCount };
}

/** ACAL1618 — l'objectif tapé lu sur l'état de la carte : borné par le maximum du toit quand il est connu ; plafonné,
 *  la production dite est celle de CE maximum (ACAL1903), sinon le rendement de la carte affichée. */
export function cibleDepuisCarte(
  objectifKwhAn: number,
  e: { kwhParPanneau: number; tiennent: number; maxSens?: MaxDuToit | null } | null,
  clamp: (n: number) => number,
): ResultatCible | null {
  if (!e) return null;
  const max = e.maxSens;
  const r = panneauxPourCible(objectifKwhAn, e.kwhParPanneau, max?.n ?? e.tiennent, clamp, max?.sens);
  return r?.plafonne && max?.kwhAn != null && r.panneaux === max.n ? { ...r, maxKwhAn: Math.round(max.kwhAn) } : r;
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
