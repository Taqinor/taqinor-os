// ACAL1919 — les phrases des cartes de recommandation, hors d'`optimizer.ts` (plus de 2 000 lignes : il ne grossit pas).
// Une carte dit UN nombre de panneaux : celui de la pose annoncée dans son en-tête. Quand ce que le toit TIENT diffère
// de ce qui est posé pour la cible, la phrase nomme les deux nombres au lieu d'en citer un second sans le dire.

export interface LignePhrase {
  fitCount: number;
  placedCount: number;
  tiltDeg: number;
  layoutLabel: string;
}

/** Carte « Densité maximale (plein sud) » : le nombre qui TIENT est dit comme tel, le nombre posé aussi s'il diffère. */
export function phraseDensiteMax(r: LignePhrase): string {
  const lieu = `à ${r.tiltDeg}°, ${r.layoutLabel}`;
  if (r.placedCount === r.fitCount) return `La plus dense en plein sud : ${r.fitCount} panneaux tiennent ${lieu}.`;
  return `La plus dense en plein sud : ${r.fitCount} tiennent au total ${lieu}, ${r.placedCount} posés pour votre cible.`;
}
