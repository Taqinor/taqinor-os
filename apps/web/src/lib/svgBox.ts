/**
 * Socle commun des graphes SVG inline faits main (ENF19 : une seule copie, partagée par
 * batterySim, productionWindow, proposalChart et proposalCurve) :
 * - `esc` : échappe le texte injecté dans le SVG (`<title>`, libellés) ;
 * - `SvgBox` : boîte de tracé (largeur/hauteur + marges).
 */
export function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export interface SvgBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}
