// AFAC61 — FactureList : les refus serveur d'avoir et d'échéance affichent la raison
// du serveur via `frenchError` (plus de `detail ?? texte fixe`). Garde de source
// (FactureList monte trop de dépendances pour un test comportemental léger).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'FactureList.jsx'), 'utf8')

test('création d\'avoir et échéance : frenchError, plus de detail ?? texte fixe', () => {
  assert.match(src, /import \{ frenchError \} from '..\/..\/lib\/frenchError'/)
  assert.match(src, /toast\.error\(frenchError\(err, "Création de l'avoir impossible\."\)\)/)
  assert.match(src, /toast\.error\(frenchError\(err, 'Mise à jour de l’échéance impossible\.'\)\)/)
  assert.doesNotMatch(src, /err\?\.response\?\.data\?\.detail \?\? "Création de l'avoir/)
  assert.doesNotMatch(src, /err\?\.response\?\.data\?\.detail \?\? 'Mise à jour de l’échéance/)
})

test("sondage du PDF : l'erreur est affichée une fois et la boucle continue (AFAC62)", () => {
  const m = src.match(/const poll = async \(\) => \{[\s\S]*?\n      setTimeout\(poll, 2000\)/)
  assert.ok(m, 'bloc poll introuvable')
  assert.doesNotMatch(m[0], /catch \{/)
  assert.match(m[0], /catch \(err\) \{[\s\S]*erreurSignalee[\s\S]*toast\.error\(frenchError\(err,[\s\S]*setTimeout\(poll, 2000\)/)
})
