// LW4 — Perte de données #3 : « a »/le bouton Archiver jetaient les éditions
// non sauvées sans confirmation (`toggleArchive` appelait `onSaved();onClose()`
// directement, sans passer par `confirmLeaveIfDirty`, contrairement à
// `guardedClose`). Et « Créer un autre » (rafale de création) ne remettait
// pas `customData` à zéro → le lead suivant héritait silencieusement des
// champs personnalisés du précédent.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/pages/crm/LeadFormLW4ArchiveAndBurstReset.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FORM_SRC = readFileSync(join(HERE, 'LeadForm.jsx'), 'utf8').replace(/\r\n/g, '\n')

function extractToggleArchive(src) {
  const start = src.indexOf('const toggleArchive = async () => {')
  assert.ok(start >= 0, 'toggleArchive introuvable')
  const end = src.indexOf('\n  }\n', start)
  assert.ok(end >= 0, 'fin de toggleArchive introuvable')
  return src.slice(start, end + 5)
}

function extractCreerUnAutreReset(src) {
  const start = src.indexOf('if (creerUnAutre) {')
  assert.ok(start >= 0, "bloc « Créer un autre » introuvable")
  const end = src.indexOf('nomRef.current?.focus()', start)
  assert.ok(end >= 0, "fin du bloc « Créer un autre » introuvable")
  return src.slice(start, end + 'nomRef.current?.focus()'.length)
}

test('LW4 : toggleArchive passe par confirmLeaveIfDirty(isDirty) avant d\'archiver', () => {
  const fn = extractToggleArchive(FORM_SRC)
  assert.match(fn, /if \(!confirmLeaveIfDirty\(isDirty\)\) return/)
  // La garde doit précéder le PATCH d'archivage (setArchiveBusy).
  const guardIdx = fn.indexOf('confirmLeaveIfDirty(isDirty)')
  const busyIdx = fn.indexOf('setArchiveBusy(true)')
  assert.ok(guardIdx >= 0 && busyIdx >= 0 && guardIdx < busyIdx,
    'la garde doit être vérifiée AVANT de lancer l\'archivage')
})

test('LW4 : le reset « Créer un autre » remet aussi customData à zéro', () => {
  const block = extractCreerUnAutreReset(FORM_SRC)
  assert.match(block, /setCustomData\(\{\}\)/)
})
