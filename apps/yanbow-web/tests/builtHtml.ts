/**
 * Aides « HTML RENDU » (YBW14) : lit `dist/client/` APRÈS `npm run build` et
 * parse chaque page avec jsdom. Règle du site : aucun test ne lit le source par
 * regex quand le rendu existe — on teste ce que le visiteur reçoit.
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';

export const DIST_CLIENT = fileURLToPath(new URL('../dist/client/', import.meta.url));

export interface PageRendue {
  /** Chemin d'URL canonique (avec barre finale), ex. `/`, `/en/solarbow/`. */
  url: string;
  /** Langue déduite de l'URL (`en` sous `/en/`, sinon `fr`). */
  langueUrl: 'fr' | 'en';
  fichier: string;
  html: string;
  document: Document;
}

function assurerBuild(): void {
  if (!existsSync(DIST_CLIENT)) {
    throw new Error('dist/client/ absent — lancer `npm run build` avant `npm test`');
  }
}

function fichiersHtml(dir: string): string[] {
  const out: string[] = [];
  for (const nom of readdirSync(dir)) {
    const chemin = join(dir, nom);
    if (statSync(chemin).isDirectory()) out.push(...fichiersHtml(chemin));
    else if (nom.endsWith('.html')) out.push(chemin);
  }
  return out;
}

/** `bonjour/index.html` → `/bonjour/` ; `index.html` → `/` ; `404.html` → `/404.html`. */
export function urlDeFichier(fichierRelatif: string): string {
  const posix = fichierRelatif.split(sep).join('/');
  if (posix === 'index.html') return '/';
  if (posix.endsWith('/index.html')) return '/' + posix.slice(0, -'index.html'.length);
  return '/' + posix;
}

/** Toutes les pages HTML construites (les deux langues si actives), triées par URL. */
export function pagesRendues(): PageRendue[] {
  assurerBuild();
  return fichiersHtml(DIST_CLIENT)
    .map((fichier) => {
      const url = urlDeFichier(relative(DIST_CLIENT, fichier));
      const html = readFileSync(fichier, 'utf-8');
      return {
        url,
        langueUrl: url === '/en/' || url.startsWith('/en/') ? ('en' as const) : ('fr' as const),
        fichier,
        html,
        document: new JSDOM(html).window.document,
      };
    })
    .sort((a, b) => a.url.localeCompare(b.url));
}

/** Une page construite par son URL ; lève si elle n'existe pas. */
export function pageRendue(url: string): PageRendue {
  const p = pagesRendues().find((x) => x.url === url);
  if (!p) throw new Error(`page non construite : ${url}`);
  return p;
}
