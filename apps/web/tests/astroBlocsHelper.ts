/**
 * ENF19 — les tests de SOURCE cherchent du balisage dans les pages `.astro`. Une partie de ce
 * balisage vit désormais dans des blocs partagés (`src/components/blocs/*.astro`, identiques entre
 * les variantes fr/en/ar) : ce helper lit une page puis remplace chaque `<Bloc … />` importé depuis
 * `components/blocs/` par le modèle du composant (frontmatter retiré, blocs imbriqués déroulés).
 * Les props ne sont pas substituées : les tests de source ne cherchent que le balisage et les
 * chaînes littérales.
 */
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const IMPORT_BLOC = /^import (\w+) from '([^']*\/components\/blocs\/[^']+\.astro)';?\s*$/gm;

function separerFrontmatter(src: string): { front: string; modele: string } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/.exec(src);
  return m ? { front: m[1], modele: src.slice(m[0].length) } : { front: '', modele: src };
}

function derouler(texte: string, front: string, dossier: string): string {
  let sortie = texte;
  for (const [, nom, rel] of front.matchAll(IMPORT_BLOC)) {
    const chemin = resolve(dossier, rel);
    const bloc = separerFrontmatter(readFileSync(chemin, 'utf-8'));
    const corps = derouler(bloc.modele, bloc.front, dirname(chemin));
    sortie = sortie.replace(new RegExp(`<${nom}\\b[^>]*?/>`, 'g'), () => corps);
  }
  return sortie;
}

/** Source d'une page `.astro` avec ses blocs partagés (components/blocs) déroulés en ligne. */
export function lireAstroAvecBlocs(chemin: string): string {
  const src = readFileSync(chemin, 'utf-8');
  const { front } = separerFrontmatter(src);
  return derouler(src, front, dirname(chemin));
}
