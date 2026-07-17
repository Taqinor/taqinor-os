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
// 2026-07-11 : 2200 -> 2240 Ko. La vague PLAN2 (lanceur d'applications VX9,
// système d'accents module VX8, apps épinglées VX10, fil d'Ariane VX11,
// recherche unifiée VX13, préférences VX46, gestes terrain, etc. — ~15
// fonctionnalités) fait croître le bundle de ~22 Ko gzip (croissance produit
// légitime, pas une régression). Marge relevée d'autant ; le garde continue
// d'attraper toute VRAIE régression au-dessus de 2240.
// 2026-07-12 : 2240 -> 2340 Ko. La vague wave-1 (66 tâches : LeadDetailPage,
// onglet Délégations d'ApprobationsPage, PlanificationPage, CalendarPage sur
// tokens, onglets NotificationBell, ChatterTimeline, journal d'appel, etc.)
// ajoute ~9 Ko gzip — AUCUNE nouvelle dépendance npm, pages toutes lazy-loadées
// (pas de gonflement du chunk partagé) : croissance produit organique.
// CONVENTION (fondateur, 2026-07-12) : on relève ce TOTAL par PALIERS GÉNÉREUX
// (~100 Ko) plutôt qu'au Ko près, pour ne PAS re-bumper à chaque vague. Le vrai
// garde anti-gonflement reste PER_CHUNK_BUDGET_KB (350) + les budgets vendors
// par chunk ; ce total ne sert qu'à attraper une régression MASSIVE. Ici ~91 Ko
// de marge au-dessus du réel (2248.8) — le garde reste actif au-dessus de 2340.
// 2026-07-16 : 2340 -> 2440 Ko. Le batch plateforme (nouveaux frontends santé
// [SanteAgenda, NomenclatureActes], innovation [boîte à idées : liste, détail,
// dashboard, CTA, paramètres], et les 4 modes du générateur de devis QX) porte
// le réel à ~2341.8 Ko — palier généreux habituel (~100 Ko), pas de nouvelle
// dépendance npm, écrans lazy-loadés ; le garde per-chunk (350) reste actif.
// 2026-07-17 : le shell frontend Marketing PLAN_CRM_VENTES (NTMKT1-11 : 9 écrans
// Campagnes/Séquences/Segments/Listes/Événements/Enquêtes/Fidélité/Domaine
// d'envoi + dashboard) ajoute ~26 Ko gzip sur ce même palier 2440 (AUCUNE
// nouvelle dépendance npm) — réel cumulé ~2368 Ko, sous le budget.
const TOTAL_BUDGET_KB = 2440
const VENDOR_CHUNK_BUDGETS_KB = {
  recharts: 450,
  'pdfjs-dist': 450,
  'radix-ui': 300,
  'react-vendor': 250,
  // Outil toiture pro (canvas/3D lourd, isolé) : budget dédié comme les autres
  // vendors lourds — pré-existant à YHARD7 (nouveau gate), pas une régression.
  'roof-tool': 500,
}

// VX185 — YHARD7 mesure chaque chunk ISOLÉMENT, jamais ce que `index.html`
// PRÉCHARGE au boot : un vendor lourd (dont un composant statique du header,
// toujours monté, importe un named export via le barrel `ui/index.js`) se
// retrouvait en `<link rel="modulepreload">` sur TOUTE page, `/login` inclus
// — ~350 Ko gzip avant même l'écran de connexion sur le 4G marocain.
const HEAVY_VENDOR_CHUNK_NAMES = ['recharts', 'pdfjs-dist', 'datatable', 'roof-tool']

// Allowlist COMMENTÉE : un chunk lourd n'y figure QUE si son préchargement au
// boot est un choix délibéré et justifié (commentaire obligatoire). Vide par
// défaut — aucun vendor lourd ne doit précharger au boot aujourd'hui.
const MODULEPRELOAD_ALLOWLIST = new Set([
  // 'recharts-abcd1234.js', // ex. : justification ici si un jour nécessaire
])

// Plafond/métrique du NOMBRE de chunks (prolifération silencieuse — ex. 126
// chunks < 1 Ko gzip d'icônes lucide individuelles, cf. VX189). Généreux :
// n'attrape qu'une régression de structure massive, pas la croissance produit
// normale (chaque écran lazy-loadé ajoute un chunk).
const MAX_CHUNK_COUNT = 400

// Extrait les `<link rel="modulepreload" href="...">` de `dist/index.html` et
// signale tout vendor lourd nommé qui s'y trouve (hors allowlist). Silencieux
// (aucune violation) si `index.html` est absent — ce script peut aussi
// s'exécuter sur un `dist/` partiel en test.
function checkModulePreloads(distDir) {
  const indexPath = path.join(distDir, 'index.html')
  if (!existsSync(indexPath)) return { violations: [], preloadCount: 0 }

  const html = readFileSync(indexPath, 'utf8')
  const preloads = [...html.matchAll(/<link[^>]*rel="modulepreload"[^>]*href="([^"]+)"/g)]
    .map((m) => m[1])

  const violations = []
  for (const href of preloads) {
    const fileName = href.split('/').pop()
    if (MODULEPRELOAD_ALLOWLIST.has(fileName)) continue
    const vendor = HEAVY_VENDOR_CHUNK_NAMES.find((v) => fileName.includes(v))
    if (vendor) {
      violations.push(
        `  - modulepreload: ${fileName} précharge le vendor lourd "${vendor}" au BOOT `
        + `(index.html, toute page dont /login) — importer directement le fichier source `
        + `plutôt que le barrel ui/index.js dans un composant statique, ou ajouter `
        + `${fileName} à MODULEPRELOAD_ALLOWLIST avec une justification si volontaire.`,
      )
    }
  }
  return { violations, preloadCount: preloads.length }
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

  // VX185 — nombre de chunks (métrique + plafond) et modulepreload de vendors
  // lourds (index.html, si présent). Additif : n'affecte aucun des budgets
  // ci-dessus.
  const chunkCount = jsFiles.length
  if (chunkCount > MAX_CHUNK_COUNT) {
    violations.push(
      `  - NOMBRE DE CHUNKS: ${chunkCount} > plafond ${MAX_CHUNK_COUNT}`,
    )
  }
  const { violations: preloadViolations, preloadCount } = checkModulePreloads(distDir)
  violations.push(...preloadViolations)

  return { violations, totalKb, perFile, chunkCount, preloadCount }
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
  console.log(
    `[check_bundle_budget] Chunks: ${result.chunkCount} (plafond ${MAX_CHUNK_COUNT}) · `
    + `modulepreload index.html: ${result.preloadCount}`,
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
