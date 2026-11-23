// ACAL470 — objectif de production annuelle tapé (kWh/an) → nombre de panneaux.
// Fonction PURE : N = plus petit entier tel que N × kWh/panneau ≥ objectif, borné par
// `clamp` (clampNeeded) et par ce qui tient. AUCUNE marge de couverture (le +10 % de la
// facture ne vaut pas pour un objectif tapé).
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

/** ACAL1618 — ce qui tient AU MIEUX sur le pan : le plus grand des deux sens (le « + » bascule de même),
 *  ou le seul sens verrouillé. `capacite` = les emplacements d'une grille (seuil d'accès solaire déduit). */
export function maxDesSens<G>(pack: { portrait: G; landscape: G }, verrou: SensPose | null, capacite: (g: G) => number): { n: number; sens: SensPose } {
  const sens: SensPose[] = verrou ? [verrou] : ['portrait', 'landscape'];
  return sens.map((s) => ({ n: capacite(pack[s]), sens: s })).reduce((a, b) => (b.n > a.n ? b : a));
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
