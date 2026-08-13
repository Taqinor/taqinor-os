// FE-SCA41 — exports ventes volumineux : gérer la réponse 202 (journal-ventes
// / export-comptable) en pollant GET /export/status/<job_id>/ jusqu'à
// {status:'ready', download_url, filename} puis déclencher le téléchargement.
// Sous le seuil (200), rien ne change. Assertions au niveau SOURCE (pas de
// node_modules dans ce worktree/lane — FactureList.jsx importe react-redux/ui,
// non exécutable en isolation) :
//   node --test src/pages/ventes/FactureListFE_SCA41.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FACTURE_LIST_SRC = readFileSync(join(HERE, 'FactureList.jsx'), 'utf8')
const VENTES_API_SRC = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')

test('FE-SCA41 : ventesApi expose exportStatus (GET /ventes/export/status/<job_id>/)', () => {
  assert.match(
    VENTES_API_SRC,
    /exportStatus: \(jobId\) => api\.get\(`\/ventes\/export\/status\/\$\{jobId\}\/`\)/,
  )
})

test('FE-SCA41 : asyncExportPayload ne se déclenche que sur un 202 (200 synchrone inchangé)', () => {
  const start = FACTURE_LIST_SRC.indexOf('async function asyncExportPayload')
  assert.notEqual(start, -1)
  const block = FACTURE_LIST_SRC.slice(start, start + 300)
  assert.match(block, /if \(res\.status !== 202\) return null/)
})

test('FE-SCA41 : pollExportJobAndDownload sonde exportStatus jusqu\'à ready/error', () => {
  const start = FACTURE_LIST_SRC.indexOf('async function pollExportJobAndDownload')
  assert.notEqual(start, -1)
  const block = FACTURE_LIST_SRC.slice(start, start + 900)
  assert.match(block, /ventesApi\.exportStatus\(jobId\)/)
  assert.match(block, /data\.status === 'ready'/)
  assert.match(block, /data\.status === 'error'/)
  // Le téléchargement final utilise l'URL pré-signée renvoyée par le job.
  assert.match(block, /a\.href = data\.download_url/)
  assert.match(block, /a\.download = data\.filename \|\| fallbackFilename/)
})

test('FE-SCA41 : export-comptable xlsx bascule sur le job async + toast "arrière-plan"', () => {
  const start = FACTURE_LIST_SRC.indexOf('const handleExportComptable')
  const block = FACTURE_LIST_SRC.slice(start, start + 900)
  assert.match(block, /const job = await asyncExportPayload\(res\)/)
  assert.match(block, /toast\.info\('Export volumineux — génération en arrière-plan\.'\)/)
  assert.match(block, /await pollExportJobAndDownload\(job\.job_id, filename\)/)
})

test('FE-SCA41 : journal des ventes bascule sur le job async + toast "arrière-plan"', () => {
  const start = FACTURE_LIST_SRC.indexOf('const handleJournalComptable')
  const block = FACTURE_LIST_SRC.slice(start, start + 900)
  assert.match(block, /const job = await asyncExportPayload\(r\)/)
  assert.match(block, /toast\.info\('Export volumineux — génération en arrière-plan\.'\)/)
  assert.match(block, /await pollExportJobAndDownload\(job\.job_id, filename\)/)
})
