#!/usr/bin/env node
// YHARD7 — Budget de performance du bundle SPA ERP (dev-only, aucune
// dépendance runtime — Node stdlib uniquement : fs + zlib pour le gzip).
//
// Complète `chunkSizeWarningLimit: 900` dans vite.config.js (O66), qui n'est
// qu'un AVERTISSEMENT de build — rien n'échoue la CI aujourd'hui sur une
// régression de taille de bundle. Ce script s'exécute APRÈS `vite build` :
// il lit chaque chunk JS d'entrée dans `dist/`, calcule sa taille gzippée, et
// échoue (exit 1) si un chunk dépasse son budget OU si le total gzippé de
// tous les chunks JS dépasse le budget global.
//
// Budgets volontairement un peu au-dessus de l'existant (`chunkSizeWarningLimit
// = 900 Ko NON gzippé`) pour laisser une marge raisonnable tant qu'aucune
// régression franche n'est introduite — ajustables ci-dessous si un besoin
// métier légitime grossit un chunk (documenter pourquoi dans le commit qui
// change le budget).
//
// Usage :
//   node scripts/check_bundle_budget.mjs             # après `vite build`
//   node scripts/check_bundle_budget.mjs --dist=dist # dossier explicite
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = path.resolve(__dirname, '..')

// Budgets en KB (gzippé). Un chunk INDIVIDUEL ne doit jamais dépasser
// PER_CHUNK_BUDGET_KB ; la somme de tous les chunks JS ne doit jamais dépasser
// TOTAL_BUDGET_KB. Les vendors lourds isolés (recharts/pdfjs-dist/radix-ui/
// react-vendor, cf. vite.config.js manualChunks) ont un budget dédié plus
// généreux — ce sont des dépendances tierces stables, mises en cache à part.
const PER_CHUNK_BUDGET_KB = 350
const TOTAL_BUDGET_KB = 2200
const VENDOR_CHUNK_BUDGETS_KB = {
  recharts: 450,
  'pdfjs-dist': 450,
  'radix-ui': 300,
  'react-vendor': 250,
}

function parseArgs(argv) {
  const out = { dist: 'dist' }
  for (const arg of argv) {
    const m = arg.match(/^--dist=(.+)$/)
    if (m) out.dist = m[1]
  }
  return out
}

function gzipSizeKb(filePath) {
  const buf = readFileSync(filePath)
  const gz = gzipSync(buf, { level: 9 })
  return gz.length / 1024
}

function budgetForChunk(fileName) {
  for (const [vendor, budget] of Object.entries(VENDOR_CHUNK_BUDGETS_KB)) {
    if (fileName.includes(vendor)) return budget
  }
  return PER_CHUNK_BUDGET_KB
}

export function checkBundleBudget(distDir) {
  const assetsDir = path.join(distDir, 'assets')
  if (!existsSync(assetsDir)) {
    throw new Error(
      `Dossier assets introuvable: ${assetsDir}. Lancer "vite build" avant ce script.`,
    )
  }

  const jsFiles = readdirSync(assetsDir).filter((f) => f.endsWith('.js'))
  if (jsFiles.length === 0) {
    throw new Error(`Aucun fichier .js trouvé dans ${assetsDir}.`)
  }

  const violations = []
  let totalKb = 0
  const perFile = []

  for (const fileName of jsFiles) {
    const filePath = path.join(assetsDir, fileName)
    if (!statSync(filePath).isFile()) continue
    const sizeKb = gzipSizeKb(filePath)
    totalKb += sizeKb
    perFile.push({ fileName, sizeKb })

    const budget = budgetForChunk(fileName)
    if (sizeKb > budget) {
      violations.push(
        `  - ${fileName}: ${sizeKb.toFixed(1)} Ko (gzip) > budget ${budget} Ko`,
      )
    }
  }

  if (totalKb > TOTAL_BUDGET_KB) {
    violations.push(
      `  - TOTAL: ${totalKb.toFixed(1)} Ko (gzip) > budget global ${TOTAL_BUDGET_KB} Ko`,
    )
  }

  return { violations, totalKb, perFile }
}

function main() {
  const { dist } = parseArgs(process.argv.slice(2))
  const distDir = path.isAbsolute(dist) ? dist : path.join(FRONTEND_ROOT, dist)

  let result
  try {
    result = checkBundleBudget(distDir)
  } catch (err) {
    console.error(`[check_bundle_budget] ERREUR: ${err.message}`)
    process.exit(1)
  }

  const sorted = [...result.perFile].sort((a, b) => b.sizeKb - a.sizeKb)
  console.log('[check_bundle_budget] Chunks JS (gzip), plus gros en premier :')
  for (const { fileName, sizeKb } of sorted) {
    console.log(`  ${sizeKb.toFixed(1).padStart(8)} Ko  ${fileName}`)
  }
  console.log(
    `[check_bundle_budget] Total gzippé: ${result.totalKb.toFixed(1)} Ko (budget ${TOTAL_BUDGET_KB} Ko)`,
  )

  if (result.violations.length > 0) {
    console.error('\n[check_bundle_budget] BUDGET DÉPASSÉ :')
    console.error(result.violations.join('\n'))
    process.exit(1)
  }

  console.log('[check_bundle_budget] OK — budget respecté.')
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  main()
}
