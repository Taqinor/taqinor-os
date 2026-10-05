// ACAL332 — les pages /preview/toiture* (générations 1 à 3 et pro-11) restent
// une galerie INTERNE servie par `astro dev`, mais ne sont plus publiées par
// `astro build` (D-ACAL-19 : on ne supprime ni les pages ni leurs scripts —
// roof-tool-pro11.ts reste le canonique de devis/mon-toit et de l'ERP).
//
// Fonctions PURES, sans dépendance Astro, pour être testées sur un dossier de
// build factice : le hook `astro:build:done` d'astro.config.mjs les appelle.
import { existsSync } from 'node:fs';
import { readdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

/** Préfixe des entrées retirées de `<client>/preview/` (pages ET dossiers). */
export const PREFIXE_PREVIEW_TOITURE = 'toiture';

/**
 * Les liens de l'index /preview/. `toiture: true` = galerie interne, listée
 * SEULEMENT en dev (en build les pages n'existent plus : un lien serait mort).
 * @type {ReadonlyArray<{ href: string, label: string, toiture: boolean, featured?: boolean }>}
 */
export const LIENS_PREVIEW = Object.freeze([
  { href: '/preview/diagnostic', label: 'Diagnostic (prévisualisation)', toiture: false },
  { href: '/preview/toiture', label: 'Estimateur toiture (tracé)', toiture: true },
  { href: '/preview/toiture-3d', label: 'Estimateur toiture 3D', toiture: true },
  { href: '/preview/toiture-3d-pro', label: 'Estimateur toiture 3D Pro', toiture: true },
  { href: '/preview/toiture-3d-pro-11', label: 'Estimateur 3D Pro v11 (canonique)', toiture: true, featured: true },
]);

/**
 * Les liens à afficher sur l'index de preview.
 * @param {boolean} dev `import.meta.env.DEV`
 */
export function liensPreview(dev) {
  return LIENS_PREVIEW.filter((lien) => dev || !lien.toiture);
}

/** @param {string | URL} dir */
function enChemin(dir) {
  return dir instanceof URL ? fileURLToPath(dir) : String(dir);
}

/**
 * Le dossier CLIENT d'un build : `dir` lui-même, ou `dir/client` quand le
 * hook reçoit la racine `dist/` (l'adaptateur Cloudflare publie `dist/client`).
 * @param {string | URL} dir
 */
export function dossierClient(dir) {
  const racine = enChemin(dir);
  const client = join(racine, 'client');
  if (!existsSync(join(racine, 'preview')) && existsSync(join(client, 'preview'))) {
    return client;
  }
  return racine;
}

/**
 * Supprime `<dirClient>/preview/toiture*` (fichiers et dossiers). Conserve
 * tout le reste (preview/diagnostic, preview/index…). Idempotent : un second
 * appel ne retire rien. Renvoie les noms retirés, triés.
 * @param {string | URL} dirClient
 * @returns {Promise<string[]>}
 */
export async function retirerPreviewToiture(dirClient) {
  const preview = join(enChemin(dirClient), 'preview');
  if (!existsSync(preview)) return [];
  const entrees = await readdir(preview);
  const retirees = entrees.filter((nom) => nom.startsWith(PREFIXE_PREVIEW_TOITURE)).sort();
  for (const nom of retirees) {
    await rm(join(preview, nom), { recursive: true, force: true });
  }
  return retirees;
}
