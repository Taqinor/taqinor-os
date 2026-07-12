#!/usr/bin/env node
// VX201 — Garde CI anti-régression `dangerouslySetInnerHTML` (dev-only, Node
// stdlib pur, aucune dépendance ajoutée — même famille que
// check_bundle_budget.mjs).
//
// Contexte : le SEUL usage réel de `dangerouslySetInnerHTML` dans tout le
// frontend rend un SVG de QR code généré CÔTÉ SERVEUR (F23 intervention +
// enrôlement 2FA). C'est sûr AUJOURD'HUI mais sans garde, une régression du
// backend (ou un futur call-site copié-collé) pourrait un jour y glisser du
// HTML non fiable sans que personne ne le remarque. `eslint-plugin-react`
// (règle `react/no-danger`) n'est pas une dépendance du projet — ce script
// grep joue le même rôle sans l'ajouter.
//
// Règle : tout `dangerouslySetInnerHTML` dans `src/**/*.{js,jsx}` doit
// respecter L'UNE des deux formes autorisées sur la MÊME ligne :
//   1. passer par le helper sûr `renderTrustedSvg(...)` (lib/trustedSvg.js) ;
//   2. porter un disable documenté explicite :
//      `// check-no-danger-allow: <raison>` sur la ligne précédente.
// Tout autre usage échoue (exit 1) avec le fichier:ligne fautif.
//
// Usage : node scripts/check_no_danger.mjs
import { readFileSync, globSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = path.resolve(__dirname, '..')
const SRC_ROOT = path.join(FRONTEND_ROOT, 'src')

// Attribut JSX réel (`dangerouslySetInnerHTML={...}`) — exclut les mentions en
// prose dans les commentaires (aucun `={` après l'identifiant).
const DANGER_RE = /dangerouslySetInnerHTML\s*=\s*\{/
const ALLOW_RE = /check-no-danger-allow:\s*\S/

function listFiles(dir) {
  // node:fs.globSync est disponible depuis Node 22 (utilisé par ce repo, cf.
  // .github/workflows/ci.yml `node-version: '22'`) — pas de dépendance glob.
  return globSync('**/*.{js,jsx}', { cwd: dir }).map((f) => path.join(dir, f))
}

const offenders = []
for (const file of listFiles(SRC_ROOT)) {
  if (file.includes(`${path.sep}test${path.sep}`) || file.endsWith('.test.js') || file.endsWith('.test.jsx')) continue
  const content = readFileSync(file, 'utf8')
  const lines = content.split('\n')
  // Fichier entier passé par le helper sûr (import + usage) : tous les
  // dangerouslySetInnerHTML de CE fichier sont considérés couverts — le
  // helper garantit lui-même qu'aucun HTML non fiable n'est jamais injecté
  // (renderTrustedSvg renvoie `null` sur tout balisage suspect).
  const fileIsSafe = content.includes('renderTrustedSvg(') && /from ['"].*trustedSvg['"]/.test(content)
  if (fileIsSafe) continue
  lines.forEach((line, idx) => {
    if (!DANGER_RE.test(line)) return
    const prevLine = lines[idx - 1] || ''
    if (ALLOW_RE.test(prevLine) || ALLOW_RE.test(line)) return
    offenders.push(`${path.relative(FRONTEND_ROOT, file)}:${idx + 1}`)
  })
}

if (offenders.length > 0) {
  console.error('check_no_danger: dangerouslySetInnerHTML non whitelisté (ni renderTrustedSvg, ni disable documenté) :')
  offenders.forEach((o) => console.error(`  ${o}`))
  console.error('\nFix : passer par lib/trustedSvg.js (renderTrustedSvg) ou documenter un disable explicite :')
  console.error('  // check-no-danger-allow: <raison>')
  process.exit(1)
}

console.log(`check_no_danger: OK (0 usage non whitelisté)`)
