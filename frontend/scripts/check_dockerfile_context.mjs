// ERR-QJR5-DOCKERFILE-CONTEXTE-GARDE — garde « le contexte de l'image suffit au build ».
//
// Incident du 01/10/2026 : QJR663 a fait importer `apps/web/worker/deadLetter.mjs`
// depuis `apps/web/src/lib/lead.ts` (atteint par l'ERP via l'alias `@roofpro`).
// La CI compile sur le checkout COMPLET donc restait verte, mais l'image
// (`frontend/Dockerfile.prod`, qui ne COPY que des sous-arbres choisis) ne se
// construisait plus. Cette garde résout statiquement chaque import atteint
// depuis `frontend/src` qui tombe HORS de `frontend/` et vérifie qu'il est
// couvert par un `COPY` du Dockerfile.
//
// Usage : `node scripts/check_dockerfile_context.mjs` (depuis frontend/).
// Zéro dépendance. Limite connue : les `import.meta.glob` et imports à
// spécifieur calculé ne sont pas suivis.
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs'
import { dirname, join, resolve, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const EXTS = ['.js', '.jsx', '.mjs', '.cjs', '.ts', '.tsx']
const norm = (p) => p.split(sep).join('/')

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name.startsWith('.')) continue
    const p = join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (EXTS.includes(name.slice(name.lastIndexOf('.'))) && !/\.(test|spec)\./.test(name)) out.push(p)
  }
  return out
}

// Sources des `COPY` (hors --from=, hors dernier argument = destination),
// relatives à la RACINE du dépôt, sans « ./ » ni « / » final.
export function copySources(dockerfileText) {
  const out = []
  for (const raw of dockerfileText.split(/\r?\n/)) {
    const m = raw.match(/^\s*COPY\s+(.*)$/i)
    if (!m) continue
    const args = m[1].split(/\s+/).filter((a) => a && !a.startsWith('--'))
    if (/--from=/i.test(m[1])) continue
    for (const src of args.slice(0, -1)) out.push(src.replace(/^\.\//, '').replace(/\/+$/, ''))
  }
  return out
}

export function isCovered(relFromRepo, sources) {
  return sources.some((s) => s === '.' || relFromRepo === s || relFromRepo.startsWith(`${s}/`))
}

function aliases(viteText, repoRoot) {
  const map = {}
  const webSrc = join(repoRoot, 'apps', 'web', 'src')
  for (const m of viteText.matchAll(/find:\s*'(@\w+)',\s*replacement:\s*resolvePath\(WEB_SRC,\s*'([^']+)'\)/g)) {
    map[m[1]] = join(webSrc, m[2])
  }
  return map
}

function resolveFile(base) {
  const cands = [base, ...EXTS.map((e) => base + e), ...EXTS.map((e) => join(base, 'index' + e))]
  return cands.find((c) => existsSync(c) && statSync(c).isFile()) ?? null
}

function specifiers(text) {
  const out = []
  const re = /(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\brequire\s*\(\s*)(['"])([^'"\n]+)\1/g
  for (const m of text.matchAll(re)) out.push(m[2])
  return out
}

// Retourne la liste triée des fichiers hors `frontend/` atteints par le build
// mais non couverts par un COPY.
export function findUncovered({ repoRoot, dockerfileText }) {
  const frontend = join(repoRoot, 'frontend')
  const sources = copySources(dockerfileText)
  const viteText = readFileSync(join(frontend, 'vite.config.js'), 'utf8')
  const alias = aliases(viteText, repoRoot)
  const inFrontend = (p) => !relative(frontend, p).startsWith('..')
  const seen = new Set()
  const missing = new Set()
  const queue = walk(join(frontend, 'src'))

  while (queue.length) {
    const file = queue.pop()
    if (seen.has(file)) continue
    seen.add(file)
    const text = readFileSync(file, 'utf8')
    for (let spec of specifiers(text)) {
      spec = spec.replace(/\?.*$/, '')
      let base = null
      if (spec.startsWith('.')) base = resolve(dirname(file), spec)
      else {
        const key = Object.keys(alias).find((a) => spec === a || spec.startsWith(`${a}/`))
        if (key) base = join(alias[key], spec.slice(key.length))
      }
      if (!base) continue // paquet npm : hors sujet
      const target = resolveFile(base)
      if (!target || inFrontend(target)) continue
      const rel = norm(relative(repoRoot, target))
      if (!isCovered(rel, sources)) missing.add(rel)
      if (!seen.has(target) && EXTS.some((e) => target.endsWith(e))) queue.push(target)
    }
  }
  return [...missing].sort()
}

const here = dirname(fileURLToPath(import.meta.url))
const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  const repoRoot = resolve(here, '..', '..')
  const dockerfileText = readFileSync(join(repoRoot, 'frontend', 'Dockerfile.prod'), 'utf8')
  const missing = findUncovered({ repoRoot, dockerfileText })
  if (missing.length) {
    console.error('check_dockerfile_context : fichiers importés hors frontend/ NON couverts par un COPY de frontend/Dockerfile.prod :')
    for (const f of missing) console.error(`  - ${f}`)
    console.error('Ajoutez un `COPY <dossier> /build/<dossier>` (le build d\'image échouerait).')
    process.exit(1)
  }
  console.log('check_dockerfile_context : OK — tous les imports hors frontend/ sont couverts par un COPY.')
}
