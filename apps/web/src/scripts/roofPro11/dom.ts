/**
 * Petits utilitaires DOM + formatage partagés par les modules roofPro11.
 * Extraits de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 */

/** getElementById typé, renvoyant `null` si absent (le harness jsdom ne fournit pas tout). */
export const $ = <T extends HTMLElement = HTMLElement>(id: string): T | null =>
  document.getElementById(id) as T | null;

/** Entier formaté à la française (séparateur de milliers fine espace). */
export const fmt = (n: number): string => new Intl.NumberFormat('fr-FR').format(n);

/** Montant arrondi en MAD. */
export const fmtMad = (n: number): string => `${fmt(Math.round(n))} MAD`;

/** Échappe le texte pour l'insérer en toute sécurité dans un attribut/texte SVG. */
export const esc = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
