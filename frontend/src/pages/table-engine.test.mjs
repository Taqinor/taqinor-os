// P167 — Unifier sur UN seul moteur de tableau.
// Les pages migrées hors reporting n'écrivent plus de table HTML héritée
// (`<table className="data-table">`) : elles passent par le moteur de tableau
// partagé (le primitif `pages/reporting/Table.jsx`, lui-même enveloppé d'un
// conteneur scrollable). Garde-fou au niveau source, comme les autres .mjs.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

// Pages migrées vers le moteur partagé par P167.
const MIGRATED = [
  'crm/ParrainagePage.jsx',
  'ventes/PaiementsPage.jsx',
  'ventes/AvoirsPage.jsx',
  'activities/MesActivitesPage.jsx',
]

for (const rel of MIGRATED) {
  const src = readFileSync(join(here, rel), 'utf8')
  const name = rel.split('/').slice(-1)[0]

  test(`${name} : plus de <table className="data-table"> héritée (P167)`, () => {
    assert.ok(
      !/className="data-table\b/.test(src),
      `${name} : table HTML héritée encore présente — doit passer par <Table>.`,
    )
  })

  test(`${name} : importe le moteur de tableau partagé (reporting/Table) (P167)`, () => {
    assert.ok(
      src.includes("from '../reporting/Table'") || src.includes("from '../../pages/reporting/Table'"),
      `${name} : doit importer le primitif Table partagé.`,
    )
  })
}
