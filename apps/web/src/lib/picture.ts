/**
 * Aide au balisage responsive des photos optimisées (public/photos/,
 * sorties de scripts/process-photos.mjs). Logique extraite du composant
 * Picture.astro pour être testée unitairement.
 */

/** `srcset` pour un format donné : "/photos/nom-640.avif 640w, …" (croissant). */
export function photoSrcset(name: string, widths: number[], ext: 'avif' | 'webp'): string {
  return [...widths]
    .sort((a, b) => a - b)
    .map((w) => `/photos/${name}-${w}.${ext} ${w}w`)
    .join(', ');
}

/** Plus grande largeur générée — sert de `src` de repli et de base width/height. */
export function largestWidth(widths: number[]): number {
  return Math.max(...widths);
}

/** Hauteur intrinsèque (anti-CLS) pour une largeur et un cadrage donnés. */
export function intrinsicHeight(width: number, ratio: number): number {
  return Math.round(width / ratio);
}
