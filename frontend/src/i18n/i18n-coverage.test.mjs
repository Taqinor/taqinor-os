import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

// VX73 — tripwire anti-régression de couverture i18n : le sélecteur EN/AR ne
// traduit RÉELLEMENT que le chrome (menus/labels), pas le contenu des pages.
// Ce test protège les deux invariants qui rendent `lang.partial_notice`
// honnête :
//   1. Les 3 catalogues (fr/en/ar) restent PARFAITEMENT synchronisés en clés
//      (aucune clé oubliée dans une langue → pas de repli silencieux inattendu).
//   2. La clé `lang.partial_notice` existe dans les 3 catalogues — si elle
//      disparaît, la notice VX73 se tairait silencieusement.
// Preuve de rouge (synthétique) : supprimer une clé d'un catalogue, ou retirer
// `lang.partial_notice`, fait échouer ce test — voir les commentaires "ROUGE"
// ci-dessous pour rejouer la preuve à la main.

const here = path.dirname(fileURLToPath(import.meta.url))
const catalogsDir = path.join(here, 'catalogs')

function loadCatalog(locale) {
  return JSON.parse(readFileSync(path.join(catalogsDir, `${locale}.json`), 'utf8'))
}

const fr = loadCatalog('fr')
const en = loadCatalog('en')
const ar = loadCatalog('ar')

test('i18n coverage: fr/en/ar catalogs carry the exact same key set', () => {
  const frKeys = new Set(Object.keys(fr))
  const enKeys = new Set(Object.keys(en))
  const arKeys = new Set(Object.keys(ar))

  const missingInEn = [...frKeys].filter((k) => !enKeys.has(k))
  const missingInAr = [...frKeys].filter((k) => !arKeys.has(k))
  const extraInEn = [...enKeys].filter((k) => !frKeys.has(k))
  const extraInAr = [...arKeys].filter((k) => !frKeys.has(k))

  // ROUGE (preuve) : commentez une clé de en.json ou ar.json → ces assertions
  // échouent avec la liste exacte des clés désynchronisées.
  assert.deepEqual(missingInEn, [], `en.json missing keys: ${missingInEn.join(', ')}`)
  assert.deepEqual(missingInAr, [], `ar.json missing keys: ${missingInAr.join(', ')}`)
  assert.deepEqual(extraInEn, [], `en.json has extra keys not in fr.json: ${extraInEn.join(', ')}`)
  assert.deepEqual(extraInAr, [], `ar.json has extra keys not in fr.json: ${extraInAr.join(', ')}`)
})

test('i18n coverage: chrome catalog stays a small, known-bounded surface (~121 keys)', () => {
  const count = Object.keys(fr).length
  // VX73 — au moment du build, le chrome traduit ~121 clés (~2% de l'app).
  // Ce plafond n'est PAS un empêchement d'ajouter du chrome traduit ; c'est un
  // tripwire qui force à relire ce commentaire (et la notice VX73/VX74) si le
  // catalogue grossit fortement — un signe que soit bien plus de pages sont
  // désormais traduites (revoir la notice), soit des clés orphelines s'accumulent.
  assert.ok(count >= 100, `expected chrome catalog to have at least 100 keys, got ${count}`)
  assert.ok(count <= 400, `chrome catalog grew past 400 keys (${count}) — revisit VX73/VX74 notice scope`)
})

test('i18n coverage: lang.partial_notice exists in all 3 catalogs (VX73 honesty notice)', () => {
  // ROUGE (preuve) : supprimez "lang.partial_notice" de n'importe quel
  // catalogue → cette assertion échoue.
  assert.ok('lang.partial_notice' in fr, 'fr.json missing lang.partial_notice')
  assert.ok('lang.partial_notice' in en, 'en.json missing lang.partial_notice')
  assert.ok('lang.partial_notice' in ar, 'ar.json missing lang.partial_notice')
  assert.ok(fr['lang.partial_notice'].length > 0)
  assert.ok(en['lang.partial_notice'].length > 0)
  assert.ok(ar['lang.partial_notice'].length > 0)
})
