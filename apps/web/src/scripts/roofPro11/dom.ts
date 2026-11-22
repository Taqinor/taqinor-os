/**
 * Petits utilitaires DOM + formatage partagés par les modules roofPro11.
 * Extraits de roof-tool-pro11.ts (split modulaire 2026-06-20) — comportement INCHANGÉ.
 */

/** getElementById typé, renvoyant `null` si absent (le harness jsdom ne fournit pas tout). */
export const $ = <T extends HTMLElement = HTMLElement>(id: string): T | null =>
  document.getElementById(id) as T | null;

/** Entier formaté à la française (séparateur de milliers fine espace). */
export const fmt = (n: number): string => new Intl.NumberFormat('fr-FR').format(n);

/** R2-09 — LE formateur d'une puissance : virgule française, 2 décimales (2,13 kWc), partout dans l'atelier. */
export const fmtKwc = (n: number): string =>
  n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Montant arrondi en MAD. */
export const fmtMad = (n: number): string => `${fmt(Math.round(n))} MAD`;

/** ACAL546 — la cellule « Économies/an » d'une ligne de comparatif : vide (aucune cellule) quand le
 *  tableau porte `data-sans-montant` (atelier ERP : l'argent ne vit que dans `ventes`). */
export const celluleEconomies = (wrap: HTMLElement | null, bas: number, haut: number): string =>
  wrap?.dataset.sansMontant ? '' : `<td class="num">${fmtMad(bas)} – ${fmtMad(haut)}</td>`;

/** Échappe le texte pour l'insérer en toute sécurité dans un attribut/texte SVG. */
export const esc = (s: string): string =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** R2-05 — l'ERP renomme le libellé (`<dt>`) de la tuile dont `el` est la valeur ; rend `el`. `premierTexteSeul` : seul le premier
 *  nœud texte change (le `<dt>` garde ses éléments) ; `texte` nul = rien à renommer (site public). */
export function renommerDt<T extends Element | null>(el: T, texte: string | null, premierTexteSeul = false): T {
  const dt = texte == null ? null : el?.parentElement?.querySelector('dt');
  if (!dt || texte == null) return el;
  if (!premierTexteSeul) dt.textContent = texte;
  else {
    const noeud = Array.from(dt.childNodes).find((n) => n.nodeType === 3);
    if (noeud && noeud.nodeValue !== texte) noeud.nodeValue = texte;
  }
  return el;
}
