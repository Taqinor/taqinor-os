// VX152 — Fin des moteurs de table parallèles : la table de résultats de
// GedSearch (recherche plein-texte/sémantique) rendait une <table
// class="data-table"> hex-legacy ; elle rejoint le moteur DataTable partagé
// (liste seule, résultats pré-triés côté serveur). L'état vide reste géré par
// GedSearch (EmptyState), donc GedSearch.test.jsx reste vert. Vérification de
// SOURCE (pas de node_modules installés dans ce lane) :
//   node --test src/features/ged/GedSearchDataTable.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'GedSearch.jsx'), 'utf8')

test('les résultats de recherche utilisent le moteur DataTable, plus de <table class="data-table"> hex-legacy', () => {
  assert.match(SRC, /import \{ DataTable \} from '\.\.\/\.\.\/ui\/datatable'/)
  assert.match(SRC, /<DataTable/)
  assert.doesNotMatch(SRC, /data-table/)
})
