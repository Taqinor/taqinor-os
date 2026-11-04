/**
 * WAUD44 — pages arabes : isole dans le HTML rendu ce que l'algorithme bidirectionnel
 * retourne après une lettre arabe (« 82-21 » lu 21-82, « 60 000 » lu 000 60), et dit
 * « درهم » au lieu de « MAD » après un montant. Seuls les nœuds de texte visibles sont
 * touchés : ni attributs (data-*, valeurs de formulaire, corps du lead), ni script,
 * style, svg, ni un élément déjà en dir="ltr".
 */
const SANS_TEXTE = new Set(['script', 'style', 'svg', 'textarea', 'select', 'noscript', 'bdi', 'code', 'pre']);
const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);

// Numéros de loi/décret, téléphones, montants à séparateur de milliers (espace ou espace insécable).
const SEQUENCES = /\+212[\d\s ]*\d|\b82-21\b|\b2-25-100\b|\b\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?\b/g;
const MONTANT_MAD = /(\d)([   ])MAD\b/g;

function isolerTexte(texte: string): string {
  if (!/\d/.test(texte)) return texte;
  return texte
    .replace(MONTANT_MAD, '$1$2درهم')
    .replace(SEQUENCES, (s) => `<bdi dir="ltr">${s}</bdi>`);
}

export function isolerBidi(html: string): string {
  let sortie = '';
  let ferme: string | null = null; // élément dont on saute le contenu
  let profondeur = 0;
  for (const jeton of html.match(/<!--[\s\S]*?-->|<[^>]+>|[^<]+/g) ?? []) {
    if (jeton.startsWith('<!--')) {
      sortie += jeton;
    } else if (jeton.startsWith('<')) {
      const nom = /^<\/?([a-zA-Z][\w-]*)/.exec(jeton)?.[1]?.toLowerCase();
      if (nom && ferme === nom) {
        if (jeton.startsWith('</')) {
          profondeur -= 1;
          if (profondeur === 0) ferme = null;
        } else if (!jeton.endsWith('/>')) {
          profondeur += 1;
        }
      } else if (nom && !ferme && !jeton.startsWith('</') && !jeton.endsWith('/>') && !VOID.has(nom)) {
        if (SANS_TEXTE.has(nom) || /\sdir="ltr"/.test(jeton)) {
          ferme = nom;
          profondeur = 1;
        }
      }
      sortie += jeton;
    } else {
      sortie += ferme ? jeton : isolerTexte(jeton);
    }
  }
  return sortie;
}
