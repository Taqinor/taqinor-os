/**
 * ENF19 — photo « hero » d'une fiche réalisation (ar + en) : première photo, reste de la galerie, texte alternatif
 * traduit (repli sur celui de la photo) et URL absolue de la plus grande déclinaison. Une seule copie (garde ACAL345).
 */
export function heroRealisation<P extends { name: string; alt: string; widths: number[] }>(
  photos: P[],
  alts: Record<string, string>,
  site: URL | undefined,
): { hero: P; rest: P[]; heroAlt: string; heroImg: string } {
  const hero = photos[0];
  const rest = photos.slice(1);
  const heroAlt = alts[hero.name] ?? hero.alt;
  const heroLargest = Math.max(...hero.widths);
  const heroImg = new URL(`/photos/${hero.name}-${heroLargest}.webp`, site).href;
  return { hero, rest, heroAlt, heroImg };
}
