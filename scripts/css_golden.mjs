#!/usr/bin/env node
// SPL280 — golden d'index.css : le découpage en @import (SPL281/SPL282) ne
// déplace AUCUNE règle. Compare sha256(resolveCss(index.css de l'arbre)) à
// sha256(`git show <ref>:frontend/src/index.css`) ; exit 1 si différent.
// Seule normalisation : CRLF → LF sur les DEUX flux, pour la comparaison
// uniquement (copie de travail Windows en CRLF, `git show` en LF) — aucun
// fichier réécrit.
//
// Usage : node scripts/css_golden.mjs --base <ref> [--build]
//   --build : hash du .css émis par `vite build` du ref (worktree temporaire)
//   contre celui de l'arbre courant — INFORMATIF seulement (Tailwind v4 scanne
//   tout le dépôt : un nouveau mot-utilitaire émet une règle de plus). La preuve
//   de référence est l'égalité d'octets de `resolveCss`.
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, symlinkSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const RACINE = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const INDEX = join(RACINE, 'frontend', 'src', 'index.css')

const lf = (s) => s.replace(/\r\n/g, '\n')
const sha = (s) => createHash('sha256').update(lf(s), 'utf8').digest('hex')

async function resolveCss(chemin) {
  const mod = await import(pathToFileURL(join(RACINE, 'frontend', 'src', 'test', 'readCss.mjs')).href)
  return mod.resolveCss(chemin)
}

/** Vrai si l'index.css résolu de `chemin` a les mêmes octets (CRLF→LF) que `reference`. */
export async function memeCss(chemin, reference) {
  return sha(await resolveCss(chemin)) === sha(reference)
}

function cssDuBuild(frontend) {
  execFileSync('npx', ['vite', 'build', '--logLevel', 'error'], {
    cwd: frontend, stdio: 'inherit', shell: process.platform === 'win32',
  })
  const assets = join(frontend, 'dist', 'assets')
  return readdirSync(assets).filter((f) => f.endsWith('.css')).sort()
    .map((f) => readFileSync(join(assets, f), 'utf8')).join('\n')
}

function buildInformatif(base) {
  const tmp = mkdtempSync(join(tmpdir(), 'css-golden-'))
  try {
    execFileSync('git', ['worktree', 'add', '--detach', tmp, base], { cwd: RACINE, stdio: 'ignore' })
    const modules = join(RACINE, 'frontend', 'node_modules')
    if (existsSync(modules)) symlinkSync(modules, join(tmp, 'frontend', 'node_modules'), 'junction')
    const egal = sha(cssDuBuild(join(tmp, 'frontend'))) === sha(cssDuBuild(join(RACINE, 'frontend')))
    console.log(`[css_golden] --build (INFORMATIF) : ${egal ? 'même CSS émis' : 'CSS émis différent'}`)
  } finally {
    execFileSync('git', ['worktree', 'remove', '--force', tmp], { cwd: RACINE, stdio: 'ignore' })
    rmSync(tmp, { recursive: true, force: true })
  }
}

async function main(argv) {
  const i = argv.indexOf('--base')
  const base = i >= 0 ? argv[i + 1] : null
  if (!base) {
    console.error('[css_golden] usage : node scripts/css_golden.mjs --base <ref> [--build]')
    return 2
  }
  const reference = execFileSync('git', ['show', `${base}:frontend/src/index.css`],
    { cwd: RACINE, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  const egal = await memeCss(INDEX, reference)
  console.log(egal
    ? `[css_golden] OK : index.css résolu = ${base}:frontend/src/index.css`
    : `[css_golden] ÉCART : index.css résolu ≠ ${base}:frontend/src/index.css`)
  if (argv.includes('--build')) buildInformatif(base)
  return egal ? 0 : 1
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2))
}
