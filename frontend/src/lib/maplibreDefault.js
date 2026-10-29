/* ERR122 — maplibre-gl ≥ 6 est un module ESM pur SANS export par défaut
   (5.x était UMD : `import maplibregl from 'maplibre-gl'` y rendait l'objet
   global). Le builder toiture importé depuis `apps/web/src/scripts/**` (jamais
   édité depuis l'ERP) écrit encore `import maplibregl from 'maplibre-gl'` : le
   `vite.config.js` de l'ERP redirige ce SEUL spécifieur exact vers ce module,
   qui ré-expose l'espace de noms comme défaut (`maplibregl.Map`, `.Marker`,
   `.Point`… — tous exports nommés en 6.x) et garde les exports nommés. Les
   sous-chemins (`maplibre-gl/dist/maplibre-gl.css?url`) ne sont pas touchés. */
import * as maplibregl from 'maplibre-gl/dist/maplibre-gl.mjs'
// ERR-CARTE-WORKER-MAPLIBRE6 — 6.x calcule l'URL de son worker À L'EXÉCUTION
// (`./maplibre-gl-worker.mjs` à côté du chunk) : Vite ne l'émet donc jamais et
// le serveur renvoie index.html → carte 3D vide. Le worker est bundlé par Vite
// (avec son import `maplibre-gl-shared.mjs`) et son URL donnée à maplibre.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

maplibregl.setWorkerUrl(workerUrl)

export * from 'maplibre-gl/dist/maplibre-gl.mjs'
export default maplibregl
