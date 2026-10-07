/**
 * Mesures du motif « trajectoire de flèche » (YBW40) — RELEVÉES sur les tracés
 * du logo (pack src/brand/svg/, symbole couleur, unités de sa viewBox, groupe
 * translaté), jamais inventées. Garde : tests/motif.test.ts relit ces valeurs
 * dans le fichier du pack.
 *
 * Tracé orange (la flèche) :
 *   fût : rectangle de x = 97 à x = 423,46, y = 380 à y = 416 → épaisseur 36 ;
 *   pointe : de x ≈ 423,46 à la pointe x = 521,47 (extremum exact de la courbe, y ≈ 398 = axe du fût),
 *            dos de y ≈ 360,34 à y ≈ 435,66 (extrema exacts) → hauteur ≈ 75,32.
 * Tracé encre (le B) :
 *   hauteur 700 (y = 60 à 760, boîte exacte) ; panse inférieure : arc de (250, 760) à
 *   (453,5, 556,5) → rayon 203,5 (centre 250, 556,5).
 */
export const MESURES = {
  hauteurB: 700,
  fut: { x0: 97, x1: 423.46, y0: 380, y1: 416, epaisseur: 36 },
  pointe: { base: 423.46, sommet: 521.47, y0: 360.34, y1: 435.66 },
  panse: { rayon: 203.5 },
} as const;

/** Rapports utilisés par les pièces décoratives (mise à l'échelle libre). */
export const RAPPORTS = {
  /** Longueur de la pointe / épaisseur du fût. */
  pointeSurFut: (MESURES.pointe.sommet - MESURES.pointe.base) / MESURES.fut.epaisseur,
  /** Hauteur du dos de la pointe / épaisseur du fût. */
  dosSurFut: (MESURES.pointe.y1 - MESURES.pointe.y0) / MESURES.fut.epaisseur,
  /** Rayon de la panse / épaisseur du fût. */
  panseSurFut: MESURES.panse.rayon / MESURES.fut.epaisseur,
};
