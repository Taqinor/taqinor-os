// Aide de tests : lire le HTML RÉELLEMENT RENDU (dist/client) d'une page.
// Le job CI `web-build-test` lance `astro build` AVANT `vitest` ; en local,
// lancer `npm run build` d'abord. Une garde de contenu qui ne trouve pas dist
// ÉCHOUE (jamais un faux vert silencieux).
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const distClient = fileURLToPath(new URL('../dist/client/', import.meta.url));

/** HTML construit d'une route (« /professionnel », « /en/professionnel »…). */
export function builtPage(route: string): string {
  const clean = route.replace(/^\/+|\/+$/g, '');
  const file = clean ? `${distClient}${clean}/index.html` : `${distClient}index.html`;
  if (!existsSync(file)) {
    throw new Error(`HTML construit introuvable : ${file} — lancer « npm run build » avant vitest.`);
  }
  return readFileSync(file, 'utf-8');
}

/** Contenu de <main>…</main> (ou la page entière si absent). */
export function mainOf(html: string): string {
  const a = html.indexOf('<main');
  const b = html.lastIndexOf('</main>');
  return a >= 0 && b > a ? html.slice(a, b + 7) : html;
}

/** Texte visible approximatif : scripts/styles retirés, balises → espace. */
export function visibleText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/g, ' ')
    .replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/g, ' ')
    .replace(/&#39;|&#x27;|&apos;/g, "'")
    .replace(/\s+/g, ' ');
}
