// VX35 — la sidebar verticale groupée remplace le TabsList plat des Paramètres.
// Vérification de SOURCE (pas de node_modules installés dans ce lane ; et
// peConstants.js touche import.meta.env au chargement — cf.
// MessageTemplatesCrmSection.test.mjs). On lit le texte des fichiers.
//   node --test src/pages/parametres/SettingsSidebar.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (f) => readFileSync(join(HERE, f), 'utf8')
const CONST = read('peConstants.js')
const PAGE = read('ParametresEntreprise.jsx')
const SIDEBAR = read('SettingsSidebar.jsx')

// Extrait le tableau littéral `export const NAME = [ … ]` (jusqu'au `]` de fin).
function arrayBlock(src, name) {
  const start = src.indexOf(`export const ${name} = [`)
  assert.notEqual(start, -1, `${name} introuvable`)
  const end = src.indexOf(']', start)
  return src.slice(start, end + 1)
}

// L'ORDRE et l'ENSEMBLE des clés d'onglets — figés : VX35 ne renomme ni ne
// supprime aucun onglet.
const EXPECTED_TAB_KEYS = [
  'onboarding', 'societe', 'leads', 'clients', 'devis', 'documents',
  'tarification', 'stock', 'donnees', 'statuts', 'monitoring', 'checklists',
  'etapes_chantier', 'kits', 'shotlist', 'automatisations', 'securite',
  'equipe', 'messages', 'email', 'api', 'avance',
]

test('les clés d\'onglets de TABS sont inchangées (aucune renommée/supprimée)', () => {
  const block = arrayBlock(CONST, 'TABS')
  const keys = [...block.matchAll(/key:\s*'([^']+)'/g)].map(m => m[1])
  assert.deepEqual(keys, EXPECTED_TAB_KEYS)
})

test('chaque onglet de TABS porte un champ group', () => {
  const block = arrayBlock(CONST, 'TABS')
  // autant de `group:` que de `key:` dans le bloc TABS.
  const nKeys = [...block.matchAll(/key:\s*'/g)].length
  const nGroups = [...block.matchAll(/group:\s*'/g)].length
  assert.equal(nGroups, nKeys)
})

test('tout group référencé par un onglet existe dans SETTINGS_GROUPS', () => {
  const groupsBlock = arrayBlock(CONST, 'SETTINGS_GROUPS')
  const groupKeys = new Set([...groupsBlock.matchAll(/key:\s*'([^']+)'/g)].map(m => m[1]))
  assert.ok(groupKeys.size >= 5 && groupKeys.size <= 6, 'attendu 5-6 familles')
  const tabsBlock = arrayBlock(CONST, 'TABS')
  const usedGroups = [...tabsBlock.matchAll(/group:\s*'([^']+)'/g)].map(m => m[1])
  for (const g of usedGroups) assert.ok(groupKeys.has(g), `group inconnu: ${g}`)
})

test('groupTabs conserve tous les onglets, en ordre de SETTINGS_GROUPS, sans en perdre', () => {
  assert.match(CONST, /export function groupTabs\(tabs\)/)
  // filtre par famille + retire les familles vides.
  assert.match(CONST, /SETTINGS_GROUPS\s*\n?\s*\.map\(g => \(\{/)
  assert.match(CONST, /\.filter\(g => g\.tabs\.length > 0\)/)
  // un onglet sans group connu retombe dans « avance » (jamais perdu).
  assert.match(CONST, /const fallback = 'avance'/)
})

test('searchSettings et son index restent intacts (la recherche saute au bon endroit)', () => {
  assert.match(CONST, /export function searchSettings\(query\)/)
  assert.match(CONST, /export const SETTINGS_SEARCH_INDEX = \[/)
  // toujours la même garde ≥ 2 caractères.
  assert.match(CONST, /if \(q\.length < 2\) return \[\]/)
})

test('la page rend SettingsSidebar et n\'utilise plus TabsList plat', () => {
  assert.match(PAGE, /import SettingsSidebar from '\.\/SettingsSidebar'/)
  assert.match(PAGE, /<SettingsSidebar/)
  assert.match(PAGE, /groups=\{tabGroups\}/)
  assert.match(PAGE, /onSelect=\{setTab\}/)
  assert.doesNotMatch(PAGE, /<TabsList/)
  assert.doesNotMatch(PAGE, /<TabsTrigger/)
})

test('la recherche est passée en tête de la sidebar via searchSlot', () => {
  assert.match(PAGE, /const searchBlock = \(/)
  assert.match(PAGE, /searchSlot=\{searchBlock\}/)
  // le champ de recherche lui-même est inchangé (même aria-label / onChange).
  assert.match(PAGE, /aria-label="Rechercher un réglage"/)
  assert.match(PAGE, /onChange=\{e => setSearch\(e\.target\.value\)\}/)
  // le slot est rendu en haut de la sidebar.
  assert.match(SIDEBAR, /searchSlot/)
})

test('la sidebar est une <nav> avec état actif accessible (aria-current)', () => {
  assert.match(SIDEBAR, /<nav aria-label="Sections des paramètres"/)
  assert.match(SIDEBAR, /aria-current=\{active \? 'page' : undefined\}/)
  assert.match(SIDEBAR, /onClick=\{\(\) => onSelect\(t\.key\)\}/)
})
