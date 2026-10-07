#!/usr/bin/env node
/**
 * YBW20 — limite de taille des fichiers : au-delà de ~800 lignes, un `.astro`,
 * `.ts` ou `.mjs` du site doit être découpé (le site précédent avait laissé
 * grossir un fichier jusqu'à plus de dix mille lignes).
 *
 * Exécuté par `npm test` (tests/fileSize.test.ts) et en ligne de commande :
 *   node scripts/check-file-size.mjs
 */
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const LIGNES_MAX = 800;
export const RACINE_SITE = fileURLToPath(new URL('../', import.meta.url));
/** Dossiers contrôlés (le code du site, pas les dépendances ni le build). */
export const DOSSIERS = ['src', 'worker', 'scripts', 'tests', 'tests-e2e'];
export const EXTENSIONS = ['.astro', '.ts', '.mjs'];

/**
 * @param {string} dir
 * @returns {string[]}
 */
function lister(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((nom) => {
    const p = join(dir, nom);
    if (statSync(p).isDirectory()) return lister(p);
    return EXTENSIONS.some((e) => nom.endsWith(e)) ? [p] : [];
  });
}

/** @param {string} contenu */
export function compterLignes(contenu) {
  if (contenu === '') return 0;
  return contenu.replace(/\n$/, '').split('\n').length;
}

/**
 * Fichiers trop longs : `[{ fichier, lignes }]`.
 * @param {{ fichier: string, contenu: string }[]} fichiers
 * @param {number} [max]
 */
export function tropLongs(fichiers, max = LIGNES_MAX) {
  return fichiers
    .map((f) => ({ fichier: f.fichier, lignes: compterLignes(f.contenu) }))
    .filter((f) => f.lignes > max);
}

/** Contrôle le site réel. */
export function executer() {
  const fichiers = DOSSIERS.flatMap((d) => lister(join(RACINE_SITE, d))).map((p) => ({
    fichier: relative(RACINE_SITE, p).split(sep).join('/'),
    contenu: readFileSync(p, 'utf-8'),
  }));
  return tropLongs(fichiers);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const fautes = executer();
  for (const f of fautes) console.log(`TROP LONG  ${f.fichier} : ${f.lignes} lignes > ${LIGNES_MAX}`);
  console.log(fautes.length ? `[check-file-size] ${fautes.length} fichier(s) à découper` : '[check-file-size] OK');
  process.exit(fautes.length ? 1 : 0);
}
