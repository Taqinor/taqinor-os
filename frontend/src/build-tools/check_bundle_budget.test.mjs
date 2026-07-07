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
