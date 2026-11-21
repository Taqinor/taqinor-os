// ACAL470 — objectif de production annuelle tapé (kWh/an) → nombre de panneaux.
// Fonction PURE : N = plus petit entier tel que N × kWh/panneau ≥ objectif, borné par
// `clamp` (clampNeeded) et par ce qui tient. AUCUNE marge de couverture (le +10 % de la
// facture ne vaut pas pour un objectif tapé).
export interface ResultatCible {
  panneaux: number;
  /** vrai quand l'objectif dépasse le posable : `panneaux` = le maximum, `maxKwhAn` son énergie. */
  plafonne: boolean;
  maxKwhAn: number;
}

export function panneauxPourCible(
  objectifKwhAn: number,
  kwhParPanneau: number,
  tiennent: number,
  clamp: (n: number) => number,
): ResultatCible | null {
  if (!(objectifKwhAn > 0) || !(kwhParPanneau > 0)) return null;
  const max = Math.max(1, Math.min(Math.floor(tiennent) || 1, clamp(Number.MAX_SAFE_INTEGER)));
  const brut = Math.ceil(objectifKwhAn / kwhParPanneau - 1e-9);
  if (brut > max) return { panneaux: max, plafonne: true, maxKwhAn: Math.round(max * kwhParPanneau) };
  return { panneaux: clamp(brut), plafonne: false, maxKwhAn: Math.round(brut * kwhParPanneau) };
}

export function phraseCible(r: ResultatCible): string {
  const f = (n: number) => n.toLocaleString('fr-FR');
  return r.plafonne
    ? `Le toit donne au plus ${f(r.maxKwhAn)} kWh/an avec ${f(r.panneaux)} panneaux.`
    : `${f(r.panneaux)} panneaux donnent ${f(r.maxKwhAn)} kWh/an.`;
}
