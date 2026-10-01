// QJR652 — un seul helper de téléchargement blob et un seul filenameFromResponse.
// Run : node --test src/utils/noLocalDownloadBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative, sep } from 'node:path'

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..')
const norm = (p) => relative(SRC, p).split(sep).join('/')

function walk(dir, out = []) {
  for (const nom of readdirSync(dir)) {
    const p = join(dir, nom)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.(jsx?|mjs)$/.test(nom) && !/\.test\./.test(nom)) out.push(p)
  }
  return out
}

const fichiers = walk(SRC)

test('aucune définition locale de downloadBlob hors utils/downloadBlob.js et api/importApi.js', () => {
  const autorises = new Set(['utils/downloadBlob.js', 'api/importApi.js'])
  const fautifs = fichiers.filter((f) => !autorises.has(norm(f))
    && /function downloadBlob\(/.test(readFileSync(f, 'utf8'))).map(norm)
  assert.deepEqual(fautifs, [])
})

test('aucune définition locale de filenameFromResponse hors utils/downloadBlob.js', () => {
  const fautifs = fichiers.filter((f) => norm(f) !== 'utils/downloadBlob.js'
    && /function filenameFromResponse\(/.test(readFileSync(f, 'utf8'))).map(norm)
  assert.deepEqual(fautifs, [])
})
