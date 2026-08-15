// WIR223 — e-facture : l'état était perdu à CHAQUE rechargement (`state.fe`
// vivait seulement en mémoire), si bien que Télécharger / Contrôler /
// Transmettre disparaissaient alors que l'e-facture existait côté serveur — et
// que le seul moyen de les retrouver, re-cliquer « Générer », créait une
// VERSION DE PLUS pour rien.
//
// Assertions au niveau SOURCE (pas de node_modules dans ce worktree) :
//   node --test src/components/EinvoiceActionsWIR223.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'EinvoiceActions.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../api/einvoiceApi.js'), 'utf8')

test('WIR223 : einvoiceApi.list filtre bien par facture (filterset serveur)', () => {
  assert.match(API, /list: \(params\) => api\.get\('\/einvoice\/factures-electroniques\/', \{ params \}\)/)
})

test('WIR223 : le composant réhydrate AU MONTAGE via list({facture_id})', () => {
  assert.match(SRC, /import \{ useEffect, useState \} from 'react'/)
  assert.match(SRC, /einvoiceApi\.list\(\{ facture_id: factureId \}\)/)
  // L'effet dépend de la facture affichée, pas d'un montage unique global.
  assert.match(SRC, /\}, \[factureId\]\)/)
})

test('WIR223 : la version RETENUE est la plus récente (version, puis id)', () => {
  const idx = SRC.indexOf('const derniere = versions.reduce')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, idx + 400)
  assert.match(bloc, /\(b\.version \?\? 0\) > \(a\.version \?\? 0\)/)
  assert.match(bloc, /\(b\.id \?\? 0\) > \(a\.id \?\? 0\)/)
  assert.match(SRC, /setState\(\{ fe: derniere \}\)/)
})

test('WIR223 : liste VIDE → aucun état posé (comportement d\'avant intact)', () => {
  assert.match(SRC, /if \(!Array\.isArray\(versions\) \|\| versions\.length === 0\) return/)
})

test('WIR223 : une liste en erreur ne casse rien et ne génère JAMAIS', () => {
  const idx = SRC.indexOf('einvoiceApi.list({ facture_id: factureId })')
  // Bloc borné à l'effet lui-même (il se termine sur `}, [factureId])`).
  const bloc = SRC.slice(idx, SRC.indexOf('}, [factureId])', idx))
  assert.match(bloc, /\.catch\(\(\) => \{\}\)/)
  // La réhydratation est une LECTURE : elle n'appelle jamais `generer`.
  assert.doesNotMatch(bloc, /einvoiceApi\.generer\(/)
})

test('WIR223 : l\'effet est annulable (pas de setState après démontage)', () => {
  const idx = SRC.indexOf('let actif = true')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, idx + 900)
  assert.match(bloc, /if \(!actif\) return/)
  assert.match(bloc, /return \(\) => \{ actif = false \}/)
})

test('WIR223 : les trois boutons restent conditionnés au même `state.fe`', () => {
  // Ils étaient déjà gatés par `state?.fe` : réhydrater cet état SUFFIT à les
  // faire réapparaître — aucune condition d'affichage n'a été touchée.
  assert.equal((SRC.match(/\{state\?\.fe && \(/g) ?? []).length, 4)
})
