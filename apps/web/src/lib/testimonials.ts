/**
 * Source unique de vérité des AVIS CLIENTS Taqinor (preuve sociale).
 *
 * INTÉGRITÉ (règle critique, non négociable) : RIEN n'est inventé ici.
 * Ce fichier ne contient QUE des mots de clients RÉELS et CONSENTANTS, et une
 * note Google RÉELLE. Aucun témoignage, nom, ville, système, date ou note
 * d'étoiles ne doit jamais être fabriqué, supposé ou « rempli pour faire bien ».
 *
 * Le fichier est livré VIDE : tant que le fondateur n'a pas ajouté de vraies
 * données, le composant <Testimonials /> ne rend RIEN publiquement. Pour ajouter
 * un avis réel, voir apps/web/TESTIMONIALS_NOTES.md.
 */

export interface Testimonial {
  quote: string;
  name: string;
  city: string;
  system: string;
  date?: string;
  /**
   * W282 — vidéo témoignage auto-hébergée (scaffold), optionnelle. Style
   * UGC WhatsApp (brut, non produit — la recherche montre que ce format
   * inspire plus confiance qu'une vidéo léchée). Renseigner UNIQUEMENT des
   * chemins vers de vrais clips reçus et consentis par le client (WG6) ;
   * ne jamais fabriquer de placeholder. mp4 obligatoire si vidéo, webm
   * optionnel (meilleure compression, servi en priorité par <source>).
   * Chemins attendus sous /public (ex. /videos/temoignages/nom.mp4).
   */
  videoMp4?: string;
  videoWebm?: string;
  /** Texte alternatif court décrivant la vidéo (accessibilité, requis si videoMp4 est renseigné). */
  videoAlt?: string;
}

/** LIVRÉ VIDE — les vrais avis sont ajoutés plus tard par le fondateur. Ne jamais fabriquer. */
export const TESTIMONIALS: Testimonial[] = [];

export interface ReviewRating {
  value: number;
  count: number;
  url?: string;
}

/** LIVRÉ NULL — la vraie note Google est ajoutée plus tard par le fondateur. Ne jamais fabriquer. */
export const GOOGLE_RATING: ReviewRating | null = null;

export const hasTestimonials = (): boolean => TESTIMONIALS.length > 0;

export const hasRating = (): boolean => GOOGLE_RATING !== null;
