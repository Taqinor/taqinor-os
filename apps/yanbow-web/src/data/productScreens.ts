/**
 * Captures d'écran produit (YBW41, D-YBW-10) — vrais écrans, données FICTIVES.
 *
 * Chaque écran est relié à UNE affirmation publiable du registre (YBW18) : il
 * illustre ce que dit l'affirmation, rien de plus. Le produit vient de
 * l'affirmation (aucun nom de produit écrit ici — YBW19). Toute capture porte
 * la légende `LEGENDE` dans la langue de la page.
 *
 * Les fichiers sont produits par `scripts/capture-product-screens.mjs` (pile
 * LOCALE, société jetable) dans `src/assets/product/` ; leur registre
 * `captures.json` porte largeur/hauteur, empreinte et la revue zoomée humaine.
 * Un écran sans capture revue n'est jamais rendu (`capturesPubliables`).
 *
 * JAMAIS d'écran de veille (D-YBW-7), jamais de montant ni de devise (D-YBW-8).
 */
import { cite, type Produit } from '../lib/claims';
import registre from '../assets/product/captures.json';

export const LEGENDE = { fr: 'Données fictives', en: 'Fictional data' } as const;

export interface EcranProduit {
  /** Identique à l'`id` d'`ECRANS` dans le script de capture (testé). */
  id: string;
  /** Identifiant d'affirmation PUBLIABLE (claims.ts). */
  affirmation: string;
  /** Texte alternatif ; l'anglais attend la traduction approuvée (YBW70). */
  alt: { fr: string; en?: string };
}

export interface Capture {
  ecran: string;
  largeur: number;
  avif: string;
  webp: string;
  width: number;
  height: number;
  sha256_webp: string;
  capture_le: string;
  /** `ok` = texte de la zone contrôlé par le script ; `revue-seule` = image fournie. */
  controle_texte: 'ok' | 'revue-seule';
  /** Revue zoomée humaine consignée (date + verdict) ; vide = non publiable. */
  revue: string;
}

export const ECRANS_PRODUIT: readonly EcranProduit[] = [
  { id: 'crm-pipeline', affirmation: 'SB-CRM', alt: { fr: 'Le pipeline des prospects, colonne par étape.' } },
  { id: 'calepinage-3d', affirmation: 'SB-CALEPINAGE-3D', alt: { fr: 'Le calepinage d’une toiture en vue 3D.' } },
  {
    id: 'packs-reglementaires',
    affirmation: 'SB-PACKS-FR',
    alt: { fr: 'Les dossiers déclaration préalable, Enedis et Consuel d’un projet.' },
  },
  { id: 'proposition-pdf', affirmation: 'SB-DEVIS-PDF', alt: { fr: 'Une page de la proposition commerciale en PDF.' } },
  {
    id: 'campagnes-en-pause',
    affirmation: 'MB-CREATION-EN-PAUSE',
    alt: { fr: 'La liste des campagnes, créées en pause.' },
  },
  { id: 'approbations', affirmation: 'MB-PROPOSE-APPROUVE', alt: { fr: 'La file des changements à approuver.' } },
  { id: 'garde-fous', affirmation: 'MB-COUPE-CIRCUIT', alt: { fr: 'Les garde-fous et le coupe-circuit.' } },
];

export const CAPTURES: readonly Capture[] = (registre as { captures: Capture[] }).captures;

/** Le produit illustré par un écran (depuis son affirmation ; LÈVE si non publiable). */
export function produitDe(ecran: EcranProduit): Produit {
  return cite(ecran.affirmation).produit;
}

/** Les captures revues (publiables) d'un écran, de la plus large à la plus étroite. */
export function capturesPubliables(id: string): Capture[] {
  return CAPTURES.filter((c) => c.ecran === id && c.revue.trim() !== '').sort((a, b) => b.largeur - a.largeur);
}
