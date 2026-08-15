// WIR274 — aucun composeur de note manuelle sur le devis : `noterDevis`
// existait, wrappé et servi, mais son SEUL appelant était l'auto-note WhatsApp
// (VX222). Un commercial ne pouvait consigner aucune note depuis l'écran.
//
// Assertions au niveau SOURCE (pas de node_modules dans ce worktree) :
//   node --test src/pages/ventes/DevisListWIR274Note.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')

test('WIR274 : le composeur est monté dans le panneau Historique', () => {
  const panneau = SRC.indexOf('Historique des modifications — {d.reference}')
  const champ = SRC.indexOf('data-testid="devis-note-input"')
  assert.notEqual(champ, -1, 'le champ de note doit exister')
  assert.ok(champ > panneau, 'le composeur vit DANS le panneau Historique')
  assert.match(SRC, /data-testid="devis-note-envoyer"/)
})

test('WIR274 : `noterDevis` a désormais DEUX appelants (auto-note VX222 intacte)', () => {
  assert.match(API, /noterDevis: \(id, body\) =>/)
  const appels = (SRC.match(/ventesApi\.noterDevis\(/g) ?? []).length
  assert.equal(appels, 2, 'auto-note WhatsApp + composeur manuel')
})

test('WIR274 : après envoi, le feed est RELU DU SERVEUR (jamais bricolé)', () => {
  const idx = SRC.indexOf('const envoyerNote')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, idx + 900)
  assert.match(bloc, /await ventesApi\.historiqueDevis\(id\)/)
  assert.match(bloc, /setHistoCache\(c => \(\{ \.\.\.c, \[id\]: res\.data \|\| \[\] \}\)\)/)
  // Le champ est vidé une fois la note acceptée, pas avant.
  assert.match(bloc, /setNoteTexte\(''\)/)
})

test('WIR274 : une note vide n\'est jamais postée', () => {
  const idx = SRC.indexOf('const envoyerNote')
  const bloc = SRC.slice(idx, idx + 400)
  assert.match(bloc, /const corps = noteTexte\.trim\(\)/)
  assert.match(bloc, /if \(!corps\) return/)
  assert.match(SRC, /disabled=\{noteBusy \|\| !noteTexte\.trim\(\)\}/)
})

test('WIR274 : composeur gaté au même palier que la garde serveur `noter`', () => {
  assert.match(SRC, /const peutNoter = \['responsable', 'admin'\]\.includes\(role\)/)
  const champ = SRC.indexOf('data-testid="devis-note-input"')
  assert.match(SRC.slice(Math.max(0, champ - 500), champ), /\{peutNoter && \(/)
})

test('WIR274 : l\'échec serveur est affiché, jamais avalé', () => {
  const idx = SRC.indexOf('const envoyerNote')
  const bloc = SRC.slice(idx, idx + 900)
  assert.match(bloc, /toast\.error\(frenchError\(err, "La note n'a pas pu être enregistrée\."\)\)/)
})

test('WIR274 : le commentaire VX23 périmé (« migrera vers ChatterTimeline ») est corrigé', () => {
  assert.doesNotMatch(SRC, /migrera vers ChatterTimeline \(VX23\)/)
  assert.match(SRC, /WIR274 — le commentaire VX23 annonçait une migration/)
})
