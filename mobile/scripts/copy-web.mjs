// Copie le build de la PWA (../frontend/dist) dans ./www, que Capacitor
// empaquette comme asset web natif (webDir: "www" dans capacitor.config.json).
//
// Aucune dépendance externe : uniquement des modules Node natifs. Lance-le via
// `npm run build` DANS ce dossier mobile/, APRÈS avoir construit le frontend
// (`cd ../frontend && npm run build`). Ensuite `npx cap sync` pousse ./www vers
// les projets iOS/Android natifs.
import { cp, rm, access, mkdir } from 'node:fs/promises'
import { constants } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url)) // mobile/scripts
const mobileRoot = resolve(here, '..') // mobile/
const dist = resolve(mobileRoot, '..', 'frontend', 'dist') // frontend/dist
const www = resolve(mobileRoot, 'www') // mobile/www

try {
  await access(dist, constants.F_OK)
} catch {
  console.error(
    '\n[taqinor-mobile] Introuvable : ' + dist + '\n' +
    'Construis d\'abord la PWA :\n' +
    '    cd ../frontend && npm run build\n' +
    'puis relance `npm run build` ici.\n'
  )
  process.exit(1)
}

await rm(www, { recursive: true, force: true })
await mkdir(www, { recursive: true })
await cp(dist, www, { recursive: true })

console.log('[taqinor-mobile] Copié ' + dist + ' -> ' + www)
console.log('[taqinor-mobile] Étape suivante : npx cap sync')
