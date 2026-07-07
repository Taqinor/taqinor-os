import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

/* WR8 — Verrouille le contrat du catalogue d'actions agentiques (AG1).
   C'est un endpoint DJANGO (apps/agent) : la méthode DOIT viser le chemin
   ABSOLU `/api/django/agent/actions/` pour que l'intercepteur iaApi NE
   préfixe PAS `/api/fastapi` (les autres méthodes iaApi ciblent FastAPI). */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'iaApi.js'), 'utf8')

test('getAgentActions → GET /api/django/agent/actions/', () => {
  assert.match(src, /getAgentActions:[\s\S]*?iaApi_instance\.get\('\/api\/django\/agent\/actions\/'\)/)
})

test('getAgentActions cible bien Django (chemin absolu /api/django), pas FastAPI', () => {
  // Le chemin commence par /api/ → l'intercepteur ne le re-préfixe pas.
  assert.match(src, /getAgentActions:[\s\S]*?'\/api\/django\//)
})

/* YHARD2 — journal des actions IA confirmées + annulation. Mêmes endpoints
   DJANGO absolus (apps/agent), même raison (pas de préfixe /api/fastapi). */

test('getAgentActionLogs → GET /api/django/agent/logs/', () => {
  assert.match(src, /getAgentActionLogs:[\s\S]*?iaApi_instance\.get\('\/api\/django\/agent\/logs\/'\)/)
})

test('undoAgentAction → POST /api/django/agent/logs/<id>/annuler/', () => {
  assert.match(src, /undoAgentAction:[\s\S]*?iaApi_instance\.post\(`\/api\/django\/agent\/logs\/\$\{id\}\/annuler\/`\)/)
})
