// WAUD1 — MapLibre 6 ne crée plus son worker depuis un blob : il charge
// `./maplibre-gl-worker.mjs` (qui importe `./maplibre-gl-shared.mjs`) à côté de
// son propre module. Vite met maplibre-gl.mjs dans un chunk de `_astro/` mais ne
// voit pas ces deux fichiers : 404 en production depuis WEBERR2 (05/10), mis en
// cache un an (Cache-Control immutable). Ce plugin les publie sous un NOUVEAU nom
// haché et réécrit la référence dans le chunk.
//
// Fonctions PURES pour être testées sur un bundle factice ; `scripts/roofPro11`
// (unité calepinage) n'est pas touché. Si une montée de MapLibre change ce contrat,
// le build ÉCHOUE : jamais un 404 silencieux de plus.
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';

export const NOM_WORKER = 'maplibre-gl-worker.mjs';
export const NOM_PARTAGE = 'maplibre-gl-shared.mjs';

const sansSourceMap = (code) => code.replace(/\n?\/\/# sourceMappingURL=.*$/m, '');
const nomHache = (prefixe, code) =>
  `${prefixe}.${createHash('sha256').update(code).digest('hex').slice(0, 10)}.mjs`;

/** Noms hachés + sources des deux fichiers à publier. Le worker porte le nom haché
 *  du chunk partagé : son hachage change donc avec lui. */
export function preparerFichiersWorker(codeWorker, codePartage) {
  if (!codeWorker.includes(`./${NOM_PARTAGE}`)) {
    throw new Error(`maplibre-worker : le worker n'importe plus ./${NOM_PARTAGE} (montée de MapLibre à revoir)`);
  }
  const partage = sansSourceMap(codePartage);
  const nomPartage = nomHache('maplibre-gl-shared', partage);
  const worker = sansSourceMap(codeWorker).replaceAll(`./${NOM_PARTAGE}`, `./${nomPartage}`);
  return { nomWorker: nomHache('maplibre-gl-worker', worker), worker, nomPartage, partage };
}

/** Réécrit la référence dans le code d'un chunk (avant le calcul de son hachage :
 *  le chunk change donc de nom — l'ancien, caché un an, pointe vers le 404). */
export function reecrireChunk(code, fichiers) {
  return code.includes(NOM_WORKER) ? code.replaceAll(NOM_WORKER, fichiers.nomWorker) : null;
}

/** Vrai si un chunk contient MapLibre (message d'erreur de son répartiteur de workers). */
const contientMaplibre = (bundle) =>
  Object.values(bundle).some((s) => s.type === 'chunk' && s.code.includes('Worker failed to load'));

/** Lit les deux fichiers du paquet installé. */
export async function lireFichiersMaplibre() {
  const require = createRequire(import.meta.url);
  const racine = dirname(require.resolve('maplibre-gl/package.json'));
  const [worker, partage] = await Promise.all([
    readFile(join(racine, 'dist', NOM_WORKER), 'utf-8'),
    readFile(join(racine, 'dist', NOM_PARTAGE), 'utf-8'),
  ]);
  return preparerFichiersWorker(worker, partage);
}

/** Plugin Vite (build seulement) branché dans astro.config.mjs. */
export const maplibreWorker = (dossier = '_astro') => {
  let publie = false;
  return {
    name: 'taqinor:maplibre-worker',
    apply: 'build',
    renderStart() {
      publie = false;
    },
    async renderChunk(code) {
      if (!code.includes(NOM_WORKER)) return null;
      const fichiers = await lireFichiersMaplibre();
      if (!publie) {
        this.emitFile({ type: 'asset', fileName: `${dossier}/${fichiers.nomWorker}`, source: fichiers.worker });
        this.emitFile({ type: 'asset', fileName: `${dossier}/${fichiers.nomPartage}`, source: fichiers.partage });
        publie = true;
      }
      return { code: reecrireChunk(code, fichiers), map: null };
    },
    generateBundle(_options, bundle) {
      if (!publie && contientMaplibre(bundle)) {
        this.error(`maplibre-worker : MapLibre est dans le bundle mais ${NOM_WORKER} n'y est plus référencé — contrat changé, worker non publié.`);
      }
    },
  };
};
