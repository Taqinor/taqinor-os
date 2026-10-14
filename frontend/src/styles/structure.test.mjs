// SPL282 — structure d'index.css : il ne porte AUCUNE règle, seulement des
// @import et des commentaires. Le CSS vit dans styles/<propriétaire>/NN-<thème>.css,
// importé dans l'ordre d'origine (la cascade en dépend). Le nombre de fichiers
// n'est figé nulle part : tout est recompté depuis index.css et le disque.
import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const INDEX = join(HERE, '..', 'index.css')
const source = readFileSync(INDEX, 'utf8')
const sansCommentaires = source.replace(/\/\*[\s\S]*?\*\//g, '')
const instructions = sansCommentaires.split('\n').map((l) => l.trim()).filter(Boolean)

// Imports hors styles/<dossier>/ : Tailwind, jetons, feuille d'impression.
const IMPORTS_RACINE = new Set([
  '@import "tailwindcss";', '@import "./design/tokens.css";', '@import "./styles/print.css";',
])
const SOUS_DOSSIER = /^@import "\.\/styles\/([^/"]+)\/([^/"]+\.css)";$/
const importsStyles = instructions.map((l) => l.match(SOUS_DOSSIER)).filter(Boolean)

test('SPL282 — index.css ne contient que des @import et des commentaires', () => {
  const regles = instructions.filter((l) => !IMPORTS_RACINE.has(l) && !SOUS_DOSSIER.test(l))
  assert.deepEqual(regles, [], `règle(s) CSS restée(s) dans index.css : ${regles.slice(0, 3).join(' | ')}`)
  assert.ok(importsStyles.length > 0, 'index.css doit importer au moins un fichier de styles/<propriétaire>/')
})

test('SPL282 — chaque @import désigne un fichier existant sous styles/<propriétaire>/', () => {
  for (const [, dossier, fichier] of importsStyles) {
    assert.ok(existsSync(join(HERE, dossier, fichier)), `@import absent du disque : styles/${dossier}/${fichier}`)
  }
  assert.equal(new Set(importsStyles.map((m) => m[0])).size, importsStyles.length, '@import en double')
})

test('SPL282 — la numérotation NN est strictement croissante dans l\'ordre des imports', () => {
  const numeros = importsStyles
    .map(([, , fichier]) => fichier.match(/^(\d+)-/))
    .filter(Boolean)
    .map((m) => Number(m[1]))
  assert.ok(numeros.length > 0, 'aucun fichier numéroté NN-<thème>.css')
  for (let i = 1; i < numeros.length; i += 1) {
    assert.ok(numeros[i] > numeros[i - 1], `NN pas strictement croissant : ${numeros[i - 1]} puis ${numeros[i]}`)
  }
})

test('SPL282 — aucun fichier de styles/<propriétaire>/ n\'est orphelin', () => {
  const importes = new Set(importsStyles.map(([, dossier, fichier]) => `${dossier}/${fichier}`))
  const presents = []
  for (const dossier of readdirSync(HERE)) {
    if (!statSync(join(HERE, dossier)).isDirectory()) continue
    for (const f of readdirSync(join(HERE, dossier))) {
      if (f.endsWith('.css')) presents.push(`${dossier}/${f}`)
    }
  }
  const orphelins = presents.filter((p) => !importes.has(p))
  assert.deepEqual(orphelins, [], `fichier(s) jamais importé(s) par index.css : ${orphelins.join(', ')}`)
})
