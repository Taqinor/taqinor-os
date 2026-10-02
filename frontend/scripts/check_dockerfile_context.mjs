// ERR-QJR5-DOCKERFILE-CONTEXTE-GARDE — garde « import hors frontend/ ».
//
// Le 01/10/2026, QJR663 a fait importer `apps/web/worker/deadLetter.mjs` depuis
// le code ERP (chaine `@roofpro` -> roofPro11/prefill.ts -> lib/lead -> worker/).
// La CI etait verte (checkout complet) mais `frontend/Dockerfile.prod` ne copiait
// pas ce dossier : l'image ne se construisait plus.
//
// Cette garde resout STATIQUEMENT chaque import atteint depuis `frontend/src`
// (chemins relatifs + alias de `vite.config.js`), transitivement, et verifie que
// tout fichier situe HORS de `frontend/` tombe sous un `COPY` de l'etape builder
// du Dockerfile, ET atterrit au meme emplacement relatif que dans le depot
// (sinon les `../apps/web/...` ne se resolvent plus dans l'image).
//
// Le contexte de build est la RACINE du depot (docker-compose.yml :
// `context: .`, `dockerfile: frontend/Dockerfile.prod`), donc les sources COPY
// sont relatives a la racine. Lancer : `node --test scripts/check_dockerfile_context.mjs`.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve, relative, sep, posix } from 'node:path'
import { fileURLToPath } from 'node:url'

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const ROOT = resolve(FRONTEND, '..')
const CODE_EXT = ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']
const toPosix = (p) => p.split(sep).join('/')
const relRoot = (abs) => toPosix(relative(ROOT, abs))
const isInside = (abs, dir) => {
  const r = relative(dir, abs)
  return r === '' || (!r.startsWith('..') && !r.startsWith(sep) && !/^[A-Za-z]:/.test(r))
}

// --- alias Vite (lus dans vite.config.js, jamais dupliques ici) -------------
export function readAliases(configText = readFileSync(join(FRONTEND, 'vite.config.js'), 'utf8')) {
  // Constantes de base : `const NAME = resolvePath(__dir, '<rel>')`.
  const bases = { __dir: FRONTEND }
  for (const m of configText.matchAll(/const\s+(\w+)\s*=\s*resolvePath\(\s*(\w+)\s*,\s*'([^']+)'\s*\)/g)) {
    if (bases[m[2]]) bases[m[1]] = resolve(bases[m[2]], m[3])
  }
  const aliases = []
  // `{ find: '@x', replacement: resolvePath(BASE, 'rel') }` (find string uniquement :
  // les alias regex ciblent des paquets, pas des fichiers hors frontend/).
  for (const m of configText.matchAll(
    /find:\s*'([^']+)'\s*,\s*replacement:\s*resolvePath\(\s*(\w+)\s*,\s*'([^']+)'\s*\)/g,
  )) {
    if (bases[m[2]]) aliases.push({ find: m[1], target: resolve(bases[m[2]], m[3]) })
  }
  // Alias regex pointant sur un fichier local (ex. maplibre-gl) : resolus aussi.
  for (const m of configText.matchAll(
    /find:\s*\/\^?([^/$]+?)\$?\/\s*,\s*replacement:\s*resolvePath\(\s*(\w+)\s*,\s*'([^']+)'\s*\)/g,
  )) {
    if (bases[m[2]]) aliases.push({ find: m[1], exact: true, target: resolve(bases[m[2]], m[3]) })
  }
  return aliases
}

// --- COPY du Dockerfile (etape builder, contexte = racine du depot) ---------
export function readCopies(text = readFileSync(join(FRONTEND, 'Dockerfile.prod'), 'utf8')) {
  const copies = []
  let workdir = '/'
  let stage = 0
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (/^FROM\s/i.test(line)) { stage += 1; workdir = '/'; continue }
    const wd = line.match(/^WORKDIR\s+(\S+)/i)
    if (wd) { workdir = wd[1]; continue }
    const m = line.match(/^COPY\s+(.+)$/i)
    if (!m || stage !== 1) continue // seule l'etape builder construit l'app
    const parts = m[1].split(/\s+/).filter((p) => !p.startsWith('--'))
    if (m[1].includes('--from')) continue
    const dest = parts.pop()
    const absDest = dest.startsWith('/') ? dest : posix.join(workdir, dest)
    for (const src of parts) {
      copies.push({ src: posix.normalize(src).replace(/\/$/, ''), dest: absDest.replace(/\/$/, '') || '/', line })
    }
  }
  return copies
}

function tryFile(base) {
  const cands = [base, ...CODE_EXT.map((e) => base + e), ...CODE_EXT.map((e) => join(base, 'index' + e))]
  for (const c of cands) {
    if (existsSync(c) && statSync(c).isFile()) return c
  }
  return null
}

function resolveSpecifier(spec, fromFile, aliases) {
  const clean = spec.replace(/[?#].*$/, '')
  if (clean.startsWith('.')) return tryFile(resolve(dirname(fromFile), clean))
  for (const a of aliases) {
    if (a.exact ? clean === a.find : clean === a.find || clean.startsWith(a.find + '/')) {
      return tryFile(a.exact ? a.target : resolve(a.target, '.' + clean.slice(a.find.length)))
    }
  }
  return null // paquet npm : hors sujet
}

const IMPORT_RES = [
  /\b(?:import|export)\s+(?:[^'"()]*?\sfrom\s*)?['"]([^'"]+)['"]/g,
  /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  /\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
  /\bnew\s+URL\(\s*['"]([^'"]+)['"]\s*,\s*import\.meta\.url/g,
]

function listSources(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) listSources(p, out)
    else if (CODE_EXT.includes(name.slice(name.lastIndexOf('.'))) && !/\.(test|spec)\.[a-z]+$/.test(name)) out.push(p)
  }
  return out
}

// Retourne Map<fichierExterne, premierImporteur> pour tout fichier atteint hors frontend/.
export function collectOutsideFiles(aliases = readAliases()) {
  const seen = new Set()
  const outside = new Map()
  const queue = listSources(join(FRONTEND, 'src'))
  while (queue.length) {
    const file = queue.pop()
    if (seen.has(file)) continue
    seen.add(file)
    if (!CODE_EXT.some((e) => file.endsWith(e))) continue
    const code = readFileSync(file, 'utf8')
    for (const re of IMPORT_RES) {
      re.lastIndex = 0
      for (const m of code.matchAll(re)) {
        const target = resolveSpecifier(m[1], file, aliases)
        if (!target) continue
        if (!isInside(target, FRONTEND) && !outside.has(target)) outside.set(target, file)
        queue.push(target)
      }
    }
  }
  return outside
}

export function findUncovered(outside, copies) {
  const problems = []
  for (const [file, importer] of outside) {
    const rel = relRoot(file)
    const hit = copies.find((c) => rel === c.src || rel.startsWith(c.src + '/'))
    if (!hit) {
      problems.push(`${rel} (importe par ${relRoot(importer)}) n'est sous aucun COPY de frontend/Dockerfile.prod`)
      continue
    }
    // Meme emplacement relatif dans l'image : /build/<chemin depuis la racine>.
    const inImage = posix.join(hit.dest, rel.slice(hit.src.length))
    if (inImage !== posix.join('/build', rel)) {
      problems.push(`${rel} est copie vers ${inImage} au lieu de ${posix.join('/build', rel)} (${hit.line})`)
    }
  }
  return problems
}

test('tout import hors frontend/ est copie dans l\'image Docker (Dockerfile.prod)', () => {
  const aliases = readAliases()
  assert.ok(aliases.some((a) => a.find === '@roofpro'), 'alias @roofpro introuvable dans vite.config.js')
  const outside = collectOutsideFiles(aliases)
  assert.ok(outside.size > 0, 'aucun import hors frontend/ detecte : la garde est aveugle')
  const problems = findUncovered(outside, readCopies())
  assert.deepEqual(problems, [], `\nFichiers hors contexte Docker :\n  ${problems.join('\n  ')}\n`)
})
