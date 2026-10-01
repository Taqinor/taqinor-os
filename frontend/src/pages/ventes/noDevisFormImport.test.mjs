// QJR540 — le modal d'édition DevisForm est SUPPRIMÉ : ses blocs (calepinage,
// badge périmé, pièces jointes, compteurs, bandeau « en attente de signature »)
// vivent dans l'Édition complète (DevisGenerator en ?edit=). Garde : le fichier
// n'existe plus et aucun module de src/ ne l'importe à nouveau.
//   node --test src/pages/ventes/noDevisFormImport.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = join(HERE, '..', '..')

function* fichiers(dir) {
  for (const nom of readdirSync(dir)) {
    if (nom === 'node_modules') continue
    const chemin = join(dir, nom)
    if (statSync(chemin).isDirectory()) yield* fichiers(chemin)
    else if (/\.(jsx?|mjs|tsx?)$/.test(nom)) yield chemin
  }
}

test('DevisForm.jsx n\'existe plus', () => {
  assert.equal(existsSync(join(HERE, 'DevisForm.jsx')), false)
})

test('aucun import de ./DevisForm dans src/', () => {
  const importe = /from\s+['"][^'"]*\/DevisForm['"]|import\(\s*['"][^'"]*\/DevisForm['"]\s*\)/
  const fautifs = []
  for (const f of fichiers(SRC)) {
    if (importe.test(readFileSync(f, 'utf8'))) fautifs.push(relative(SRC, f))
  }
  assert.deepEqual(fautifs, [])
})
