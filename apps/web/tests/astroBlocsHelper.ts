/**
 * ENF19 — les tests de SOURCE cherchent du balisage dans les pages `.astro`. Une partie de ce
 * balisage vit désormais dans des blocs partagés (`src/components/blocs/*.astro`, identiques entre
 * les variantes fr/en/ar) : ce helper lit une page puis remplace chaque `<Bloc … />` importé depuis
 * `components/blocs/` par le modèle du composant (frontmatter retiré, blocs imbriqués déroulés).
 * Les props ne sont pas substituées : les tests de source ne cherchent que le balisage et les
 * chaînes littérales.
 */
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

// CPRW (27/10/2026) — même déroulé pour les blocs C&I / agricoles déplacés hors de /proposition
// (`components/proposition/{ci,agricole}/`) : le balisage testé est identique à l'ancien.
const IMPORT_BLOC = /^import (\w+) from '([^']*\/components\/(?:blocs|proposition\/(?:ci|agricole))\/[^']+\.astro)';?\s*$/gm;

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

/**
 * CPRW (27/10/2026) — (chemins relatifs à apps/web, le cwd de vitest) source de /proposition telle qu'avant le déplacement des blocs C&I / agricoles :
 * la page avec `components/proposition/{ci,agricole}/*.astro` déroulés en ligne.
 */
export function lirePageProposition(): string {
  return lireAstroAvecBlocs(resolve(process.cwd(), 'src/pages/proposition/[...token].astro'));
}

/**
 * CPRW (27/10/2026) — source de `lib/proposition.ts` suivie des deux modules déplacés tels quels
 * (`components/proposition/agricole/syntheseAgricole.ts`, `components/proposition/ci/syntheseCi.ts`).
 */
export function lireLibProposition(): string {
  return ['src/lib/proposition.ts', 'src/components/proposition/agricole/syntheseAgricole.ts', 'src/components/proposition/ci/syntheseCi.ts']
    .map((rel) => readFileSync(resolve(process.cwd(), rel), 'utf-8'))
    .join('\n');
}

/**
 * RWEB17-M9 — page du tunnel (`pages/**\/devis/mon-toit.astro`) avec ses blocs déroulés PUIS le texte de tous
 * les modules du tunnel (`src/lib/tunnel/*` et `src/scripts/tunnel/*`) qu'elle importe, récursivement
 * (un module qui en importe un autre le fait suivre), chaque module lu UNE seule fois. Les sections
 * extraites hors de la page restent ainsi trouvables par les tests de source, pages actuelles ou fusionnées.
 */
/**
 * RWEB17-M10 — les pages câblées lisent leur état dans `ctx.etat.<x>` et appellent les autres sections par
 * `ctx.crochets.appeler('<f>', …)` : pour les tests de source, ces deux indirections se relisent dans la
 * forme d'origine (`<x>`, `<f>(…)`). Rien n'est ajouté au texte : un compte de littéraux reste juste.
 * RWEB17-M11 — même relecture pour les modules `lib/tunnel/*` (`etat.<x>`, `crochets.appeler('<f>'`, et
 * leurs alias locaux `appeler('<f>'`, `h('<f>'`, `appelerCrochet(ctx, '<f>'`).
 * RWEB17-M12 — le `Document` injecté des modules (`doc.`, `ctx.dom.doc.`) se relit `document.`.
 * RWEB17-M16 — l'alias `GATED` des sections d'estimation (= `config.estimationGatee`, le
 * `PUBLIC_ESTIMATE_GATED` de la page) se relit `PUBLIC_ESTIMATE_GATED`.
 */
export function normaliserIndirectionsTunnel(src: string): string {
  return src
    .replace(/\bGATED\b/g, 'PUBLIC_ESTIMATE_GATED')
    .replace(/\b(?:ctx\.)?(?:dom\.)?doc\./g, 'document.')
    .replace(/\b(?:ctx\.)?etat\./g, '')
    .replace(/(?:\b(?:ctx\.)?crochets\.appeler|\bappeler|\bh)\('(\w+)'(?:, )?/g, '$1(')
    .replace(/\bappelerCrochet\(ctx, '(\w+)'(?:, )?/g, '$1(');
}

export function lireAstroAvecModulesTunnel(chemin: string): string {
  const base = normaliserIndirectionsTunnel(lireAstroAvecBlocs(chemin));
  const vus = new Set<string>();
  let suite = '';
  const suivre = (fichier: string, texte: string): void => {
    for (const [, rel] of texte.matchAll(/(?:from|import)\s*\(?\s*'(\.[^']*)'/g)) {
      const cible = resolve(dirname(fichier), rel).replace(/\\/g, '/');
      if (!/\/src\/(?:lib|scripts)\/tunnel\//.test(cible)) continue;
      const abs = [`${cible}.ts`, `${cible}/index.ts`].find((c) => existsSync(c));
      if (!abs || vus.has(abs)) continue;
      vus.add(abs);
      const contenu = readFileSync(abs, 'utf-8');
      suite += `\n${contenu}`;
      suivre(abs, contenu);
    }
  };
  suivre(chemin, readFileSync(chemin, 'utf-8'));
  return base + normaliserIndirectionsTunnel(suite);
}

/**
 * RWEB17-M9 — lecture d'un fichier de source pour un test : une page `devis/mon-toit.astro` passe par
 * `lireAstroAvecModulesTunnel`, tout autre fichier est lu tel quel (comportement d'avant).
 */
export function lireSourceTunnel(chemin: string): string {
  return /[\\/]devis[\\/]mon-toit\.astro$/.test(chemin) ? lireAstroAvecModulesTunnel(chemin) : readFileSync(chemin, 'utf-8');
}
