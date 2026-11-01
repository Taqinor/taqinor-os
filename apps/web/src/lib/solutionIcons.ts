/**
 * Pictogrammes au trait (SVG, currentColor) des cartes « Nos solutions » — source unique
 * partagée par la grille de l'accueil (index fr/en/ar) et le hub /nos-solutions (fr/en/ar).
 * Indexés par href RACINE : stables même si l'ordre des cartes change.
 */
export const solutionIcons: Record<string, string> = {
  '/résidentiel': '<path d="M4 13 12 5l8 8" /><path d="M6 11v8h12v-8" /><path d="M10 19v-4h4v4" />',
  '/professionnel': '<path d="M4 21V8l7-3v4l7-3v15" /><path d="M4 21h16" /><path d="M8 12h0M8 16h0M14 12h0M14 16h0" />',
  '/pompage-solaire': '<path d="M12 3v6" /><path d="M5 21c1.6-2 3.2-2 4.8 0s3.2 2 4.8 0 3.2-2 4.4 0" /><path d="M8 9h8l-2 6H10z" />',
  '/batteries-stockage': '<path d="M5 8h14v11H5z" /><path d="M9 5h6v3H9z" /><path d="M12 11v5" /><path d="M9.5 13.5h5" />',
  '/maintenance-monitoring': '<path d="M4 18 9 12l3 3 4-6 4 5" /><path d="M4 21h16" /><circle cx="9" cy="12" r="0.6" /><circle cx="16" cy="9" r="0.6" />',
  '/regularization-article-33': '<path d="M7 4h7l4 4v12H7z" /><path d="M14 4v4h4" /><path d="M9.5 14l1.5 1.5 3-3.5" />',
};

// Hub /nos-solutions : trois pictogrammes de plus (étude/diagnostic, analyse de facture,
// recharge VE) absents de la grille condensée de l'accueil.
const hubIcons: Record<string, string> = {
  '/devis/mon-toit': '<path d="M4 13 12 5l8 8" /><path d="M6 11v8h12v-8" /><path d="M10 19v-4h4v4" /><path d="M9 9.5 12 8l3 1.5" />',
  '/recharge-voiture-electrique-solaire': '<path d="M4 17V9a2 2 0 0 1 2-2h6l3 4h3a2 2 0 0 1 2 2v4" /><circle cx="7.5" cy="17.5" r="1.6" /><circle cx="16.5" cy="17.5" r="1.6" /><path d="M11 12v-5" /><path d="M9.5 7.5h3" />',
};

// Repli par préfixe pour les hrefs paramétrés (ex. ?etape=facture) — évite de dupliquer la
// clé pour chaque variante de query string.
export function iconFor(href: string): string {
  const base = href.split('?')[0];
  return solutionIcons[href] ?? hubIcons[href] ?? solutionIcons[base] ?? hubIcons[base] ?? '';
}
