// ZSAL1 — proposition d'activité de suivi (mode « suggérer ») à la clôture
// d'une activité. On vérifie la SOURCE (fichier JSX, non importable par
// node:test) plutôt que de monter le composant (pas de node_modules installé
// dans ce lane — cf. SigneDialog.test.mjs pour la même convention).
//   node --test src/pages/activities/MesActivitesPage.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'MesActivitesPage.jsx'), 'utf8')

test('ZSAL1 : markDone capture la suggestion renvoyée par le serveur sans rien créer', () => {
  assert.match(SRC, /setSuggestion\(res\?\.data\?\.suggestion/)
  // La création de l'activité de suivi n'arrive que dans acceptSuggestion,
  // jamais dans markDone lui-même (pas de création automatique/silencieuse).
  const markDoneBody = SRC.slice(
    SRC.indexOf('const markDone = async'), SRC.indexOf('const dismissSuggestion'))
  assert.doesNotMatch(markDoneBody, /createActivity/)
})

test('ZSAL1 : accepter la suggestion crée UNE activité de suivi via recordsApi.createActivity', () => {
  const acceptBody = SRC.slice(
    SRC.indexOf('const acceptSuggestion = async'), SRC.indexOf('const teamOverdue'))
  assert.match(acceptBody, /recordsApi\.createActivity\(/)
  assert.match(acceptBody, /activity_type: suggestion\.activity_type/)
  assert.match(acceptBody, /due_date: addDaysIso\(suggestion\.delai_jours\)/)
  assert.match(acceptBody, /setSuggestion\(null\)/)
})

test('ZSAL1 : ignorer la suggestion ne crée rien (dismissSuggestion vide juste l\'état)', () => {
  assert.match(SRC, /const dismissSuggestion = \(\) => setSuggestion\(null\)/)
})

test('ZSAL1 : le bandeau de proposition est rendu conditionnellement (jamais si suggestion est null)', () => {
  assert.match(SRC, /\{suggestion && \(/)
  assert.match(SRC, /Planifier une suite/)
})

// ── addDaysIso, ré-implémentée à l'identique (logique pure, sans horloge
//    système figée ici — on vérifie juste le format et le delta de jours). ──
function addDaysIso(days) {
  const d = new Date()
  d.setDate(d.getDate() + (Number(days) || 0))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

test('addDaysIso : format YYYY-MM-DD et delta correct', () => {
  const today = addDaysIso(0)
  assert.match(today, /^\d{4}-\d{2}-\d{2}$/)
  const plus7 = new Date(addDaysIso(7))
  const base = new Date(today)
  const diffDays = Math.round((plus7 - base) / 86400000)
  assert.equal(diffDays, 7)
})
