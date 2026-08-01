// AOF8 — Contrat de hooks DOM `data-ao-*` FIGÉ AVANT le premier écran.
// Zéro dépendance (node:test + node:fs, comme urgency.test.mjs/contrast.test.mjs) :
// exécutable via `node --test` sans npm/vitest installés.
//
// Deux garanties :
//  1. Aucun des 11 hooks normatifs ne peut disparaître de `E2E_HOOKS.md` (le
//     document EST le contrat tant qu'aucun écran ne les consomme encore) ni
//     perdre son propriétaire/sa sémantique.
//  2. Aucun écran de `features/ao/**` ne peut introduire un `data-ao-*` hors de
//     cette liste (garde anti-invention — vert aujourd'hui car aucun écran
//     n'existe encore, redevient significatif dès le premier écran livré).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DOC_PATH = join(HERE, 'E2E_HOOKS.md')

// Source de vérité normative (AOF8) — la SEULE liste qui grandit le contrat ;
// toute extension future passe par une nouvelle ligne ICI + dans E2E_HOOKS.md.
export const ALL_HOOKS = [
  'data-ao-canvas',
  'data-ao-outil',
  'data-ao-verdict',
  'data-ao-compte',
  'data-ao-tiroir',
  'data-ao-variante',
  'data-ao-piece',
  'data-ao-controle',
  'data-ao-repere',
  'data-ao-provenance',
  'data-ao-etat',
]

function readDoc() {
  return readFileSync(DOC_PATH, 'utf8')
}

// Extrait les lignes de tableau markdown `| \`data-ao-x\` | owner | sémantique |`.
function parseHookRows(doc) {
  const rows = new Map()
  const lineRe = /^\|\s*`(data-ao-[a-z-]+)`\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$/gm
  let m
  while ((m = lineRe.exec(doc)) !== null) {
    rows.set(m[1], { owner: m[2], semantique: m[3] })
  }
  return rows
}

test('E2E_HOOKS.md publie exactement les 11 hooks normatifs', () => {
  const rows = parseHookRows(readDoc())
  for (const hook of ALL_HOOKS) {
    assert.ok(rows.has(hook), `hook manquant dans E2E_HOOKS.md : ${hook}`)
  }
})

test('chaque hook listé porte un propriétaire ET une sémantique non vides', () => {
  const rows = parseHookRows(readDoc())
  for (const hook of ALL_HOOKS) {
    const row = rows.get(hook)
    assert.ok(row, `hook manquant : ${hook}`)
    assert.ok(row.owner.length > 0, `${hook} : propriétaire vide`)
    assert.ok(row.semantique.length > 0, `${hook} : sémantique vide`)
  }
})

test('E2E_HOOKS.md ne documente aucun hook hors de la liste normative (pas de dérive silencieuse)', () => {
  const rows = parseHookRows(readDoc())
  const documented = [...rows.keys()].sort()
  assert.deepEqual(documented, [...ALL_HOOKS].sort())
})

// ── Garde anti-invention : aucun `data-ao-*` dans le code d'écran ne sort de
//    la liste normative. Parcourt `features/ao/**` (ce dossier), en ignorant
//    les fichiers de contrat eux-mêmes. ────────────────────────────────────
function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, out)
    } else if (/\.(jsx?|mjs)$/.test(entry) && entry !== 'e2eHooks.test.mjs') {
      out.push(full)
    }
  }
  return out
}

test('aucun data-ao-* hors contrat dans features/ao/** (garde anti-invention)', () => {
  const attrRe = /data-ao-[a-z-]+/g
  const allowed = new Set(ALL_HOOKS)
  const offenders = []
  for (const file of walk(HERE)) {
    const src = readFileSync(file, 'utf8')
    const found = src.match(attrRe) || []
    for (const hook of found) {
      if (!allowed.has(hook)) offenders.push(`${hook} (${file})`)
    }
  }
  assert.deepEqual(offenders, [], `hooks hors contrat : ${offenders.join(', ')}`)
})
