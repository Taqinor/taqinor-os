// L878 — Garde-fou PWA iPhone-first des tables reporting/archive.
//
// Sur 375px (iPhone), une <table className="data-table"> multi-colonnes qui
// n'est pas dans un conteneur scrollable déborde et provoque un scroll
// horizontal de TOUTE la page (titre + actions partent hors écran). Le correctif
// est d'envelopper chaque table large dans un conteneur `overflow-x-auto`
// (présent sur la carte ou un <div> direct), pour qu'elle scrolle DANS sa carte.
//
// Ce test verrouille l'invariant : dans chaque page reporting/archive, CHAQUE
// occurrence de `className="data-table"` doit être précédée de près par un
// `overflow-x-auto` (le conteneur scrollable qui l'enveloppe). Pas de rendu DOM :
// on lit la source, comme les autres tests .mjs de ce dépôt.
//
// Exécuté en CI : node --test src/pages/reporting/reporting.layout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const pagesDir = join(here, '..')

// Pages reporting/archive qui rendent des tables `.data-table` (les wrappers
// ArchiveClientPage/ArchiveChantierPage délèguent à DocumentsArchive et ne
// rendent aucune table eux-mêmes).
const FILES = [
  join(pagesDir, 'Reporting.jsx'),
  join(pagesDir, 'Rapports.jsx'),
  join(here, 'BalanceAgeePage.jsx'),
  join(here, 'DocumentsArchive.jsx'),
]

// Fenêtre arrière (caractères) où le conteneur scrollable doit apparaître avant
// l'ouverture de la table. Couvre le cas `overflow-x-auto` posé sur la
// <CardContent> parente comme sur un <div> direct.
const WINDOW = 220

for (const file of FILES) {
  const src = readFileSync(file, 'utf8')
  const name = file.split('/').slice(-1)[0]

  test(`${name} : chaque table .data-table est dans un conteneur scrollable (L878)`, () => {
    // Toutes les ouvertures de table porteuses de la classe .data-table
    // (tolère « data-table » seul ou « data-table mb-2 »).
    const re = /className="data-table\b/g
    let m
    let count = 0
    while ((m = re.exec(src)) !== null) {
      count += 1
      const before = src.slice(Math.max(0, m.index - WINDOW), m.index)
      assert.ok(
        before.includes('overflow-x-auto'),
        `${name} : la table .data-table à l'offset ${m.index} n'est pas `
        + 'enveloppée d\'un conteneur « overflow-x-auto » (régression PWA 375px).',
      )
    }
    assert.ok(count > 0, `${name} : aucune table .data-table trouvée — test obsolète ?`)
  })
}

// Reporting.jsx avait deux tables NON enveloppées (StageTable + « Pertes par
// motif ») corrigées par L878 — on verrouille leur présence pour éviter une
// régression silencieuse si le composant est remanié.
test('Reporting.jsx : ≥ 3 tables .data-table, toutes scrollables (L878)', () => {
  const src = readFileSync(join(pagesDir, 'Reporting.jsx'), 'utf8')
  const tables = (src.match(/className="data-table\b/g) || []).length
  const wrappers = (src.match(/overflow-x-auto/g) || []).length
  assert.ok(tables >= 3, `Reporting.jsx doit garder ses ${tables} tables (≥ 3)`)
  assert.ok(
    wrappers >= tables,
    `Reporting.jsx : ${wrappers} conteneurs overflow-x-auto pour ${tables} tables — `
    + 'chaque table doit avoir son conteneur scrollable.',
  )
})
