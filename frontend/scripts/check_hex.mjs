#!/usr/bin/env node
// VX121 — Garde CI « zéro couleur hors token » (index.css).
//
// L'intégralité de index.css (~500 occurrences hex historiques) n'a PAS été
// migrée en une seule tâche : ce garde protège les blocs de composants déjà
// tokenisés (form-control/modal/table/lead-nav/page-loading/page-error…)
// contre une RÉGRESSION — un futur commit qui réintroduit un hex codé en dur
// dans l'un de ces blocs fait échouer la CI. `GUARDED_SELECTORS` grandit à
// mesure qu'un futur passage tokenise un nouveau bloc (ajouter son sélecteur
// ici fait immédiatement partie du garde — jamais l'inverse : ne JAMAIS
// retirer un sélecteur de cette liste pour faire passer un hex).
//
// `design/tokens.css` (les PRIMITIVES de la palette de marque en OKLCH/hex)
// est HORS PÉRIMÈTRE : c'est le fichier qui DÉFINIT les tokens, tout le
// reste doit les CONSOMMER via `var()`. Le bloc `:root` de index.css lui-même
// (un seul token local, `--ease-out`) est également exempté.
//
// Zéro dépendance (Node stdlib pur), même esprit que check_bundle_budget.mjs.
//
// Usage :
//   node scripts/check_hex.mjs             # scanne src/index.css
//   node scripts/check_hex.mjs --file=src/foo.css
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_ROOT = path.resolve(__dirname, '..')

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/g

// Sélecteurs déjà migrés sur les tokens sémantiques (VX121 + prédécesseurs
// VX4/VX6/VX17) — leur corps doit rester 0 % hex codé en dur pour toujours.
const GUARDED_SELECTORS = [
  '.page-loading',
  '.page-error',
  '.empty-state',
  '.data-table',
  '.data-table th',
  '.data-table td',
  '.lines-table-wrap',
  '.lines-table',
  '.lines-table th',
  '.lines-table td',
  '.modal-overlay',
  '.modal',
  '.modal-lg',
  '.modal-xl',
  '.modal-header',
  '.modal-title',
  '.modal-close',
  '.modal-body',
  '.modal-footer',
  '.lead-nav',
  '.lead-nav button',
  '.lead-nav-icon',
  '.lead-nav-badge',
  '.form-control',
  '.form-select',
  '.form-error-box',
]

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// Neutralise les commentaires CSS (un hex documenté en commentaire — ex.
// « pas le bleu vif #1d4ed8 » — n'est pas une couleur consommée). Remplace
// chaque caractère non-saut-de-ligne par une espace pour préserver la
// numérotation de ligne d'origine.
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
}

function lineAt(css, index) {
  return css.slice(0, index).split('\n').length
}

export function checkHex(css) {
  const clean = stripComments(css)
  const violations = []

  for (const selector of GUARDED_SELECTORS) {
    const re = new RegExp(`${escapeRegExp(selector)}\\s*\\{([^}]*)\\}`, 'g')
    let m
    while ((m = re.exec(clean)) !== null) {
      const body = m[1]
      const bodyStart = m.index + m[0].indexOf(body)
      const hexMatches = body.match(HEX_RE)
      if (hexMatches) {
        for (const hex of hexMatches) {
          const offsetInBody = body.indexOf(hex)
          violations.push({
            selector,
            hex,
            line: lineAt(clean, bodyStart + offsetInBody),
          })
        }
      }
    }
  }

  violations.sort((a, b) => a.line - b.line)
  return violations
}

function parseArgs(argv) {
  const out = { file: 'src/index.css' }
  for (const arg of argv) {
    const m = arg.match(/^--file=(.+)$/)
    if (m) out.file = m[1]
  }
  return out
}

function main() {
  const { file } = parseArgs(process.argv.slice(2))
  const target = path.isAbsolute(file) ? file : path.join(FRONTEND_ROOT, file)

  let css
  try {
    css = readFileSync(target, 'utf8')
  } catch (err) {
    console.error(`[check_hex] ERREUR lecture ${target}: ${err.message}`)
    process.exit(1)
  }

  const violations = checkHex(css)

  if (violations.length > 0) {
    console.error(`[check_hex] ${violations.length} couleur(s) hex hors token dans ${file} :\n`)
    for (const v of violations) {
      console.error(`  L${v.line}: ${v.hex}  (sélecteur ${v.selector})`)
    }
    console.error(
      '\n[check_hex] Ces sélecteurs sont déjà tokenisés — poser un token '
      + '(design/tokens.css) plutôt qu\'un hex codé en dur.',
    )
    process.exit(1)
  }

  console.log(
    `[check_hex] OK — 0 couleur hex hors token sur ${GUARDED_SELECTORS.length} `
    + `sélecteur(s) protégé(s) dans ${file}.`,
  )
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  main()
}
