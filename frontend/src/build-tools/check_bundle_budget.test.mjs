import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { randomBytes } from 'node:crypto'

import { checkBundleBudget } from '../../scripts/check_bundle_budget.mjs'

// YHARD7 — budget de performance du bundle. Ces tests fabriquent un faux
// dossier `dist/assets/` avec des fichiers .js de taille contrôlée (pas de
// vrai `vite build`, pour rester rapide et déterministe) et vérifient que
// `checkBundleBudget` détecte correctement un dépassement de budget par
// chunk et un dépassement de budget total.

function makeDistDir() {
  const dir = mkdtempSync(path.join(tmpdir(), 'bundle-budget-test-'))
  mkdirSync(path.join(dir, 'assets'))
  return dir
}

// Des octets ALÉATOIRES sont quasi-incompressibles (gzip ne les réduit pas) :
// écrire N Ko de bytes aléatoires produit ~N Ko gzippés, en UNE passe (rapide
// et déterministe côté taille, contrairement à un contenu répétitif qu'il
// faudrait faire grossir itérativement pour atteindre une taille gzippée
// cible précise).
function writeJsOfGzipSizeKb(filePath, targetGzipKb) {
  writeFileSync(filePath, randomBytes(Math.ceil(targetGzipKb * 1024)))
}

test('passes when all chunks are within budget', () => {
  const dir = makeDistDir()
  try {
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'index-abc.js'), 5)
    const result = checkBundleBudget(dir)
    assert.equal(result.violations.length, 0)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('flags a chunk that exceeds the per-chunk budget', () => {
  const dir = makeDistDir()
  try {
    // 350 Ko est le budget par défaut d'un chunk générique — on dépasse large.
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'huge-chunk.js'), 400)
    const result = checkBundleBudget(dir)
    assert.ok(result.violations.length >= 1)
    assert.ok(result.violations.some((v) => v.includes('huge-chunk.js')))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('vendor chunk (recharts) gets its own more generous budget', () => {
  const dir = makeDistDir()
  try {
    // 380 Ko dépasse le budget générique (350) mais reste sous le budget
    // dédié "recharts" (450) — ne doit PAS être flagué.
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'recharts-xyz.js'), 380)
    const result = checkBundleBudget(dir)
    assert.equal(result.violations.length, 0)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('throws a clear error when assets dir is missing (build not run)', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'bundle-budget-empty-'))
  try {
    assert.throws(() => checkBundleBudget(dir), /Dossier assets introuvable/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

// ── VX185 — le budget mesurait chaque chunk ISOLÉMENT, jamais ce que
// index.html PRÉCHARGE au boot (le vrai bug : un vendor lourd importé via le
// barrel `ui/index.js` dans un composant statique se retrouvait en
// <link rel="modulepreload"> sur TOUTE page, /login inclus). ────────────────

test('no index.html: no modulepreload violation (backward-compatible, existing tests never build one)', () => {
  const dir = makeDistDir()
  try {
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'index-abc.js'), 5)
    const result = checkBundleBudget(dir)
    assert.equal(result.preloadCount, 0)
    assert.equal(result.violations.length, 0)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('flags a heavy vendor chunk (recharts/pdfjs-dist/datatable/roof-tool) preloaded at boot', () => {
  const dir = makeDistDir()
  try {
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'index-abc.js'), 5)
    writeFileSync(
      path.join(dir, 'index.html'),
      '<html><head>'
      + '<link rel="modulepreload" href="/assets/index-abc.js">'
      + '<link rel="modulepreload" href="/assets/datatable-xyz123.js">'
      + '</head><body></body></html>',
    )
    const result = checkBundleBudget(dir)
    assert.equal(result.preloadCount, 2)
    assert.ok(result.violations.some((v) => v.includes('datatable-xyz123.js')))
    assert.ok(result.violations.some((v) => v.includes('datatable')))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('a non-heavy chunk in modulepreload is never flagged', () => {
  const dir = makeDistDir()
  try {
    writeJsOfGzipSizeKb(path.join(dir, 'assets', 'index-abc.js'), 5)
    writeFileSync(
      path.join(dir, 'index.html'),
      '<html><head><link rel="modulepreload" href="/assets/index-abc.js"></head><body></body></html>',
    )
    const result = checkBundleBudget(dir)
    assert.equal(result.preloadCount, 1)
    assert.equal(result.violations.length, 0)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('chunk count metric is reported and a runaway chunk count fails', () => {
  const dir = makeDistDir()
  try {
    // 501 minuscule chunks > le plafond MAX_CHUNK_COUNT (500).
    for (let i = 0; i < 501; i += 1) {
      writeJsOfGzipSizeKb(path.join(dir, 'assets', `icon-${i}.js`), 0.1)
    }
    const result = checkBundleBudget(dir)
    assert.equal(result.chunkCount, 501)
    assert.ok(result.violations.some((v) => v.includes('NOMBRE DE CHUNKS')))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
