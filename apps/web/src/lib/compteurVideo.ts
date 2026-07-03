/**
 * W347 — « Compteur à zéro » : source unique de vérité du clip vidéo montrant
 * un vrai compteur/appli client dont la consommation facturée chute après
 * l'installation (15–30 s, un vrai client, consentant). Le format « compteur
 * qui tombe à zéro » est le genre de clip le plus persuasif du marketing
 * solaire — et Taqinor a de vrais chantiers où le filmer.
 *
 * INTÉGRITÉ (même règle que testimonials.ts) : RIEN n'est inventé ici. Ce
 * fichier est livré VIDE — `<VideoCompteur />` ne rend RIEN publiquement tant
 * que le fondateur n'a pas fourni le vrai clip + son consentement. Ne jamais
 * fabriquer un placeholder vidéo.
 *
 * Pour publier le vrai clip : déposer le MP4 sous `public/videos/` (ex.
 * `/videos/compteur-zero.mp4`) + un poster AVIF/WebP sans extension (mêmes
 * conventions que LiteVideo.astro, ex. `/videos/compteur-zero-poster`), puis
 * renseigner `COMPTEUR_VIDEO` ci-dessous.
 */

export interface CompteurVideo {
  /** Chemin du MP4 auto-hébergé sous /public (ex. /videos/compteur-zero.mp4). */
  src: string;
  /** Chemin RACINE du poster, SANS extension (ex. /videos/compteur-zero-poster). */
  poster: string;
  /** Texte alternatif de l'affiche (a11y, requis). */
  alt: string;
  /** Ratio d'aspect CSS du clip (ex. "16/9", "9/16" pour un format vertical). */
  aspectRatio?: string;
}

/** LIVRÉ VIDE — pending real footage from Reda. Ne jamais fabriquer. */
export const COMPTEUR_VIDEO: CompteurVideo | null = null;

export function hasCompteurVideo(): boolean {
  return COMPTEUR_VIDEO !== null;
}
