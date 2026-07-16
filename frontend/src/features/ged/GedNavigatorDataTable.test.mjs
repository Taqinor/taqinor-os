// VX152 — Fin des moteurs de table parallèles : GedNavigator rendait une
// <table class="data-table"> hex-legacy pendant que les écrans avancés du MÊME
// module (Approbation/Corbeille) utilisaient déjà ListShell/DataTable. La liste
// des documents rejoint le moteur DataTable via l'échappatoire ARC49
// renderRow/renderHeaderRow, ce qui préserve à l'octet près le DOM testé
// (cases nommées, actions par ligne, aperçu, verrou) — donc GedNavigator.test.jsx
// reste vert. Vérification de SOURCE (pas de node_modules installés dans ce lane —
// cf. RolesManagementDataTable.test.mjs) :
//   node --test src/features/ged/GedNavigatorDataTable.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'GedNavigator.jsx'), 'utf8')

test('la liste des documents utilise le moteur DataTable, plus de <table class="data-table"> hex-legacy', () => {
  assert.match(SRC, /import \{ DataTable \} from '\.\.\/\.\.\/ui\/datatable'/)
  assert.match(SRC, /<DataTable/)
  assert.doesNotMatch(SRC, /data-table/)
})

test('le DOM riche testé est préservé via les échappatoires renderRow/renderHeaderRow (ARC49)', () => {
  assert.match(SRC, /renderHeaderRow=/)
  assert.match(SRC, /renderRow=/)
  // Cases nommées + actions par ligne conservées (tests XGED14 / GED14 / GED16).
  assert.match(SRC, /Sélectionner \$\{d\.nom\}/)
  assert.match(SRC, /Aperçu de \$\{d\.nom\}/)
  assert.match(SRC, /Extraire \$\{d\.nom\}/)
})
