// VX152 — Fin des moteurs de table parallèles : RolesManagement.jsx était une
// <table> HTML brute (colonne `th` répétée) pendant que UsersManagement (même
// dossier admin) utilise déjà le DataTable complet. La liste des rôles
// rejoint le moteur ; la grille de permissions de l'éditeur reste inchangée.
// Vérification de SOURCE (pas de node_modules installés dans ce lane —
// cf. ListViewCallReady.test.mjs) :
//   node --test src/pages/admin/RolesManagementDataTable.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'RolesManagement.jsx'), 'utf8')

test('la liste des rôles utilise le moteur DataTable, plus de <table> HTML brute avec th répétée', () => {
  assert.match(SRC, /from '\.\.\/\.\.\/ui\/datatable'/)
  assert.match(SRC, /<DataTable/)
  assert.doesNotMatch(SRC, /<table className="w-full min-w-\[560px\]/)
})

test('recherche disponible sur la liste des rôles', () => {
  assert.match(SRC, /searchable\s*$/m)
})

test('le dialogue de suppression (VX234) et le dialogue de réassignation restent intacts', () => {
  assert.match(SRC, /Supprimer ce rôle \?/)
  assert.match(SRC, /Réassigner avant de supprimer/)
  assert.match(SRC, /AlertDialogAction onClick=\{\(\) => handleDelete\(pendingDelete\)\}/)
})

test('la grille de permissions (éditeur de rôle) reste une grille de cartes, pas migrée', () => {
  assert.match(SRC, /PERMISSION_GROUPS/)
  assert.match(SRC, /group\.codes\.map/)
})
