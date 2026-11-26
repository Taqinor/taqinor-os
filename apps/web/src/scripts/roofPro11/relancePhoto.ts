// Lot 8 — la photo satellite drapée sur le toit (`scene3d.ts::applyRoofPhoto`) : UNE demande par emprise quand elle
// réussit ; un échec passager (429, coupure réseau) est rejoué QUELQUES fois, de plus en plus espacé, puis on s'arrête
// (deck gris, sans erreur visible). Jamais une demande par rendu ni par pas de soleil : la relance vit ici, hors du rendu.

/** Nombre maximal de demandes pour une même emprise (la première comprise). */
export const ESSAIS_PHOTO_MAX = 3;
/** Attente avant chaque nouvelle demande (ms) : après le 1er échec, puis après le 2e. */
export const DELAIS_RELANCE_PHOTO_MS: readonly number[] = [5_000, 20_000];

export interface RelancePhoto {
  /** Un essai pour `cle` a échoué : `relancer` est appelé plus tard si le plafond n'est pas atteint, sinon jamais. */
  echec: (cle: string, relancer: () => void) => void;
}

export function creerRelancePhoto(planifier: (f: () => void, ms: number) => unknown = (f, ms) => setTimeout(f, ms)): RelancePhoto {
  const echecs = new Map<string, number>();
  return {
    echec(cle, relancer) {
      const n = (echecs.get(cle) ?? 0) + 1;
      echecs.set(cle, n);
      if (n >= ESSAIS_PHOTO_MAX) return;
      planifier(relancer, DELAIS_RELANCE_PHOTO_MS[Math.min(n, DELAIS_RELANCE_PHOTO_MS.length) - 1]);
    },
  };
}
