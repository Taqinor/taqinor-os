// ACAL332 — la liste des liens de l'index /preview/, SANS AUCUN import Node :
// src/pages/preview/index.astro l'importe, et la page est pré-rendue dans
// l'environnement workerd de l'adaptateur Cloudflare (vite : « Unexpected
// Node.js imports for environment "prerender" ») — avec l'import Node, la
// page /preview/ construite perdait sa meta robots (CI #793).
// scripts/retirer-preview-toiture.mjs (hook de build, Node) la ré-exporte.

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
