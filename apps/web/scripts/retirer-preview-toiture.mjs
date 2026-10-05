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

export { LIENS_PREVIEW, liensPreview } from './liens-preview.mjs';

/** Préfixe des entrées retirées de `<client>/preview/` (pages ET dossiers). */
export const PREFIXE_PREVIEW_TOITURE = 'toiture';

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
