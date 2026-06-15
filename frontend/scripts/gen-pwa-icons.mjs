// Génère les icônes PWA à partir du logo SVG de la marque (public/favicon.svg),
// centré sur le fond navy de l'app (#0f172a), avec une marge de sécurité.
// Les PNG produits sont COMMITÉS dans public/ : la build de prod n'a donc besoin
// que de vite-plugin-pwa. @resvg/resvg-js n'est PAS une dépendance du projet
// (binaire natif lourd, inutile à la build). Pour régénérer les icônes :
//   npm i -D @resvg/resvg-js && node scripts/gen-pwa-icons.mjs && npm un @resvg/resvg-js
import { readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { Resvg } from '@resvg/resvg-js'

const here = dirname(fileURLToPath(import.meta.url))
const pub = join(here, '..', 'public')
const NAVY = '#0f172a' // fond de marque (cf. src/index.css body background)

// On NE réutilise PAS tout le SVG d'origine : il s'appuie sur des couleurs
// display-p3, des masques et des flous (feGaussianBlur) que le rasteriseur ne
// rend pas fidèlement (le logo sortait quasi noir). On garde la SILHOUETTE de
// l'éclair (le 1er <path>, la forme identitaire de Taqinor) et on la remplit
// d'un dégradé de marque violet -> bleu, net et lisible sur le fond navy.
const raw = readFileSync(join(pub, 'favicon.svg'), 'utf8')
const viewBox = (raw.match(/viewBox="([^"]+)"/) || [])[1] || '0 0 48 46'
const boltPath = (raw.match(/<path[^>]*\sd="([^"]+)"/) || [])[1]
if (!boltPath) throw new Error('silhouette de l’éclair introuvable dans favicon.svg')

// Enveloppe : carré navy plein + éclair (dégradé de marque) centré/échelonné
// dans la zone de contenu via un <svg> imbriqué (preserveAspectRatio meet).
function wrap(size, padRatio) {
  const pad = Math.round(size * padRatio)
  const content = size - pad * 2
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">`
    + `<rect width="${size}" height="${size}" fill="${NAVY}"/>`
    + `<svg x="${pad}" y="${pad}" width="${content}" height="${content}" `
    + `viewBox="${viewBox}" preserveAspectRatio="xMidYMid meet">`
    + `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">`
    + `<stop offset="0" stop-color="#863bff"/><stop offset="1" stop-color="#47bfff"/>`
    + `</linearGradient></defs>`
    + `<path d="${boltPath}" fill="url(#g)"/></svg></svg>`
}

function render(svg, size, outName) {
  const png = new Resvg(svg, { fitTo: { mode: 'width', value: size } })
    .render().asPng()
  writeFileSync(join(pub, outName), png)
  console.log(`  ${outName} (${size}px, ${png.length} octets)`)
}

console.log('Génération des icônes PWA :')
render(wrap(192, 0.08), 192, 'pwa-192.png')
render(wrap(512, 0.08), 512, 'pwa-512.png')
// Maskable : logo dans la zone sûre centrale (~60 %) -> marge généreuse.
render(wrap(512, 0.20), 512, 'pwa-maskable-512.png')
// apple-touch-icon : iOS ignore le SVG -> PNG plein cadre 180.
render(wrap(180, 0.10), 180, 'apple-touch-icon-180.png')
console.log('Terminé.')
