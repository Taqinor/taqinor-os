// APX22 — Cockpits d'inventaire façon Odoo Inventory.
// État d'avant : Magasin et Logistique affichaient 3-4 chiffres NUS, très en
// retrait de Pilotage Stock ; les accents étaient fragmentés (Stock sur une
// clé, Magasin/Logistique sur celle des apps terrain) ; et les conteneurs
// divergeaient (`page` d'un côté, `ui-root` de l'autre).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { INVENTAIRE_ACCENT, INVENTAIRE_ACCENT_KEY } from './inventaireAccent.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FEATURES = path.join(__dirname, '..')
const read = (rel) => readFileSync(path.join(FEATURES, rel), 'utf8')

test('les TROIS configs de la famille inventaire partagent UN accent', () => {
  for (const cfg of ['stock/module.config.jsx', 'magasin/module.config.jsx', 'logistique/module.config.jsx']) {
    const src = read(cfg)
    assert.match(src, /accent: INVENTAIRE_ACCENT_KEY,/, `${cfg} : accent non partagé`)
    assert.match(src, /import \{ INVENTAIRE_ACCENT_KEY \} from '\.{1,2}\/(stock\/)?inventaireAccent'/, cfg)
  }
  // La teinte est une VARIABLE de thème (rampe OKLCH existante), jamais une
  // couleur inventée — donc clair ET sombre suivent.
  assert.equal(INVENTAIRE_ACCENT, `var(--module-accent-${INVENTAIRE_ACCENT_KEY})`)
  assert.match(INVENTAIRE_ACCENT, /^var\(--module-accent-[a-z]+\)$/)
})

test('les deux cockpits portent une identité de module (ModuleHero) et l’accent', () => {
  for (const f of ['magasin/MagasinCockpit.jsx', 'logistique/LogistiqueCockpit.jsx']) {
    const src = read(f)
    assert.match(src, /<ModuleHero/, `${f} : ModuleHero absent`)
    assert.match(src, /accent=\{INVENTAIRE_ACCENT\}/, `${f} : accent de famille absent`)
  }
  // Le cockpit logistique n'utilise plus l'en-tête legacy (le composant dont
  // le CSS est cassé en sombre — cf. APX32).
  assert.doesNotMatch(read('logistique/LogistiqueCockpit.jsx'),
    /components\/layout\/PageHeader/)
})

test('les tuiles sont des FILES D’ACTION cliquables vers la liste filtrée', () => {
  const magasin = read('magasin/MagasinCockpit.jsx')
  for (const [label, to] of [
    ['Rangements à traiter', '/magasin/rangement'],
    ['Prélèvements à traiter', '/magasin/prelevements'],
    ['Colis à traiter', '/magasin/colisage'],
  ]) {
    assert.ok(magasin.includes(label), `tuile « ${label} » absente`)
    assert.ok(magasin.includes(`to: '${to}'`), `lien ${to} absent`)
  }
  const logistique = read('logistique/LogistiqueCockpit.jsx')
  for (const [label, to] of [
    ['Livraisons à traiter', '/logistique/livraisons'],
    ['Comptages à traiter', '/logistique/comptages'],
    ['Transferts à traiter', '/logistique/transferts'],
  ]) {
    assert.ok(logistique.includes(label), `tuile « ${label} » absente`)
    assert.ok(logistique.includes(`to: '${to}'`), `lien ${to} absent`)
  }
})

test('aucun appel réseau nouveau n’a été introduit dans les cockpits', () => {
  const magasin = read('magasin/MagasinCockpit.jsx')
  assert.deepEqual(
    [...new Set(magasin.match(/installationsApi\.\w+/g) ?? [])].sort(),
    ['installationsApi.getBinLocations', 'installationsApi.getColisList',
      'installationsApi.getPickLists', 'installationsApi.getPutAways'],
  )
  const logistique = read('logistique/LogistiqueCockpit.jsx')
  assert.deepEqual(
    [...new Set(logistique.match(/installationsApi\.\w+/g) ?? [])].sort(),
    ['installationsApi.getDemandesTransfert', 'installationsApi.getLivraisons',
      'installationsApi.getSessionsComptage'],
  )
})

test('les conteneurs des trois écrans de la famille sont alignés', () => {
  for (const f of ['magasin/MagasinCockpit.jsx', 'logistique/LogistiqueCockpit.jsx']) {
    assert.match(read(f), /className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5"/, f)
  }
  // La référence : l'écran Stock, inchangé.
  const stock = readFileSync(
    path.join(FEATURES, '..', 'pages', 'stock', 'StockList.jsx'), 'utf8')
  assert.match(stock, /className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5"/)
})
