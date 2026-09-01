// WIR181 — Retenues à la source : bordereau de versement, attestation par
// pièce et attestation annuelle jamais accessibles depuis l'écran. Test
// SOURCE (même patron que wir180.test.mjs / FiscalitePage.vx158.test.mjs) :
// vérifie que les 3 wrappers déjà prêts (comptaApi.retenuesSource.*) sont
// bien câblés dans l'onglet RAS de FiscalitePage, sans monter React.
//   node --test src/features/compta/wir181.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'pages/FiscalitePage.jsx'), 'utf8')

test('FiscalitePage : action de ligne « Attestation (PDF) » sur l’onglet RAS, toujours visible', () => {
  const block = SRC.match(/if \(tab === 'retenuesSource'\) \{([\s\S]*?)\n {4}\}/)[1]
  assert.match(block, /id: 'attestation'/)
  assert.match(block, /comptaApi\.retenuesSource\.attestation\(row\.id\)/)
  // « Marquer versée » reste conditionnée à statut !== 'versee' (non-régression).
  assert.match(block, /row\.statut !== 'versee'/)
  assert.match(block, /comptaApi\.retenuesSource\.verser\(row\.id\)/)
})

test('FiscalitePage : bloc bordereau de versement RAS (période → CSV)', () => {
  assert.match(SRC, /downloadBordereauRas/)
  assert.match(SRC, /comptaApi\.retenuesSource\.bordereau\(\{/)
  assert.match(SRC, /export: 'csv',/)
  assert.match(SRC, /rasDateDebut/)
  assert.match(SRC, /rasDateFin/)
})

test('FiscalitePage : bloc attestation annuelle RAS (prestataire + année → PDF)', () => {
  assert.match(SRC, /downloadAttestationAnnuelle/)
  assert.match(SRC, /comptaApi\.retenuesSource\.attestationAnnuelle\(\{ tiers: rasTiers, annee: rasAnnee \}\)/)
  assert.match(SRC, /rasTiersOptions/)
  // Garde-fou : pas d'appel sans les 2 paramètres.
  assert.match(SRC, /if \(!rasTiers \|\| !rasAnnee\)/)
})

test('FiscalitePage : les erreurs 400/503 des exports RAS affichent le detail serveur (toast FR)', () => {
  assert.match(SRC, /import \{ messageErreurBlob \} from '\.\.\/\.\.\/\.\.\/utils\/pdfBlob'/)
  assert.match(SRC, /messageErreurBlob\(err, \{ fallback: 'Téléchargement indisponible\.' \}\)/)
})

test('FiscalitePage : le bloc RAS ne s’affiche que sous l’onglet Retenues à la source', () => {
  assert.match(SRC, /\{tab === 'retenuesSource' && \(/)
  assert.match(SRC, /Bordereau & attestations RAS/)
})
