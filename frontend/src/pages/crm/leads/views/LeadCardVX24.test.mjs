// VX24 — Anatomie de carte Kanban à 2 niveaux : UNE seule pilule d'alerte
// prioritaire au premier plan (perdu > rappel > expiré), « Inactif N j » +
// horloge relégués en pied discret, ScoreBadge à côté du nom (le score
// n'existait jusqu'ici QUE dans la vue Liste). Verified against SOURCE (no
// node_modules in this worktree/lane).
//   node --test src/pages/crm/leads/views/LeadCardVX24.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

test('VX24 : LeadCard importe ScoreBadge depuis features/crm', () => {
  assert.match(SRC, /import ScoreBadge from '\.\.\/\.\.\/\.\.\/\.\.\/features\/crm\/ScoreBadge'/)
})

test('VX24 : ScoreBadge est rendu à côté du nom dans la tête de carte', () => {
  const headStart = SRC.indexOf("<div className=\"kb-card-head\">")
  const headEnd = SRC.indexOf('</button>', headStart) // fin du bouton ⚡ qui clôt la tête
  const head = SRC.slice(headStart, headEnd)
  assert.match(head, /<span className="kb-card-name">\{nomComplet\}<\/span>/)
  assert.match(head, /<ScoreBadge lead=\{lead\} \/>/)
})

test('VX24 : une seule pilule alertePill dérivée (perdu > rappel > expiré), pas 3 pilules empilées', () => {
  assert.match(SRC, /const alertePill = perdu\s*\n?\s*\?/)
  assert.match(SRC, /: lead\.contact_preference === 'phone_ok'/)
  assert.match(SRC, /: dernierDevisExpire/)
  // La tête de carte ne doit plus empiler 3 blocs conditionnels séparés.
  const headStart = SRC.indexOf('<div className="kb-card-head">')
  const headEnd = SRC.indexOf('</button>', headStart)
  const head = SRC.slice(headStart, headEnd)
  assert.match(head, /\{alertePill && \(/)
  assert.doesNotMatch(head, /\{perdu && <span className="kb-badge-perdu">/)
})

test("VX24 : « Inactif N j » et l'horloge sont rendus dans le pied de carte (kb-card-foot), pas la tête", () => {
  const footStart = SRC.indexOf('<div className="kb-card-foot">')
  assert.ok(footStart > -1, 'kb-card-foot introuvable')
  const footEnd = SRC.indexOf('</article>', footStart)
  const foot = SRC.slice(footStart, footEnd)
  assert.match(foot, /Inactif \{jInactif\} j/)
  assert.match(foot, /kb-act-clock kb-foot-clock/)
})
