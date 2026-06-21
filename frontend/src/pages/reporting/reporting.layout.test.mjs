// L878 / J146 — Garde-fou PWA iPhone-first des tables reporting/archive.
//
// Sur 375px (iPhone), une table multi-colonnes qui n'est pas dans un conteneur
// scrollable déborde et provoque un scroll horizontal de TOUTE la page. Le
// correctif est d'envelopper chaque table large dans `overflow-x-auto`.
//
// J146 a migré les tables HTML héritées (`<table className="data-table">`) des
// pages reporting/archive vers le primitif partagé `./Table.jsx` — qui enveloppe
// LUI-MÊME sa table dans `overflow-x-auto`. Ce test verrouille donc : (1) le
// primitif Table reste scrollable, (2) toute table `.data-table` HÉRITÉE encore
// présente dans une page reporting/archive reste enveloppée d'un conteneur
// scrollable, et (3) les pages migrées n'écrivent plus de `.data-table` à la
// main. Pas de rendu DOM : on lit la source, comme les autres tests .mjs.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const pagesDir = join(here, '..')

// Pages reporting/archive qui rendent des tables.
const FILES = [
  join(pagesDir, 'Reporting.jsx'),
  join(pagesDir, 'Rapports.jsx'),
  join(here, 'BalanceAgeePage.jsx'),
  join(here, 'DocumentsArchive.jsx'),
]

// Fenêtre arrière (caractères) où le conteneur scrollable doit apparaître avant
// l'ouverture d'une table `.data-table` héritée.
const WINDOW = 220

for (const file of FILES) {
  const src = readFileSync(file, 'utf8')
  const name = file.split('/').slice(-1)[0]

  test(`${name} : toute table .data-table héritée reste scrollable (L878)`, () => {
    const re = /className="data-table\b/g
    let m
    while ((m = re.exec(src)) !== null) {
      const before = src.slice(Math.max(0, m.index - WINDOW), m.index)
      assert.ok(
        before.includes('overflow-x-auto'),
        `${name} : table .data-table à l'offset ${m.index} non enveloppée `
        + 'd\'un conteneur « overflow-x-auto » (régression PWA 375px).',
      )
    }
  })
}

// J146 — Le primitif Table partagé enveloppe toujours sa table d'un conteneur
// scrollable (invariant porté par le composant, pas par chaque page).
test('Table.jsx (primitif partagé) enveloppe sa table dans overflow-x-auto (J146/L878)', () => {
  const src = readFileSync(join(here, 'Table.jsx'), 'utf8')
  // On ne lit que le corps rendu (après `return (`) pour ignorer les `<table`
  // présents dans la doc-string du composant.
  const body = src.slice(src.indexOf('return ('))
  const tableOpen = body.search(/<table\s+className/)
  assert.ok(tableOpen > 0, 'Table.jsx doit rendre une <table className=…>')
  const before = body.slice(Math.max(0, tableOpen - WINDOW), tableOpen)
  assert.ok(
    before.includes('overflow-x-auto'),
    'Table.jsx : la <table> doit être enveloppée d\'un conteneur overflow-x-auto.',
  )
})

// J146 — Plus aucune <table className="data-table"> écrite à la main dans les
// pages migrées (elles passent par le primitif Table partagé).
test('Reporting / BalanceAgee / DocumentsArchive : plus de data-table héritée (J146)', () => {
  for (const f of ['Reporting.jsx', 'BalanceAgeePage.jsx', 'DocumentsArchive.jsx']) {
    const p = f === 'Reporting.jsx' ? join(pagesDir, f) : join(here, f)
    const src = readFileSync(p, 'utf8')
    assert.ok(
      !/className="data-table\b/.test(src),
      `${f} : table HTML héritée .data-table encore présente — doit passer par <Table>.`,
    )
    assert.ok(
      src.includes("from './Table'") || src.includes("from './reporting/Table'"),
      `${f} : doit importer le primitif Table partagé.`,
    )
  }
})
