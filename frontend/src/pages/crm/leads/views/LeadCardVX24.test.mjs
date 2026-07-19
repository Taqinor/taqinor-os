// VX24 / LB13 — Anatomie de carte Kanban à 4 zones (blueprint D3) :
// nom → valeur → UNE ligne d'action → pied. Le ScoreBadge est à côté du nom
// (le score n'existait jusqu'ici QUE dans la vue Liste). UNE seule ligne
// d'action à précédence (perdu > relance retard > ☎ rappel > devis expiré >
// next_activity > SLA premier-contact > facture manquante > suggestion), plus
// jamais un empilement de pilules en tête. Les anciennes « Inactif N j » +
// horloge sont absorbées par la pill d'âge du pied. Verified against SOURCE
// (no node_modules in this worktree/lane).
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
  const headStart = SRC.indexOf('<div className="kb-card-head">')
  assert.ok(headStart > -1, 'kb-card-head introuvable')
  // Fin de la tête : ouverture de la zone VALEUR juste après.
  const headEnd = SRC.indexOf('{/* ── VALEUR', headStart)
  assert.ok(headEnd > headStart, 'fin de tête introuvable')
  const head = SRC.slice(headStart, headEnd)
  assert.match(head, /<span className="kb-card-name">\{nomComplet\}<\/span>/)
  assert.match(head, /<ScoreBadge lead=\{lead\} \/>/)
})

test('VX24 : UNE seule ligne d\'action à précédence (kb-card-actionline), pas 3 pilules empilées', () => {
  // La précédence est un unique arbre ternaire (perdu ? … : relanceEnRetard ? …).
  assert.match(SRC, /const relanceEnRetard =/)
  assert.match(SRC, /const rappelDemande =/)
  assert.match(SRC, /\{perdu \? \(/)
  assert.match(SRC, /kb-card-actionline/)
  // Plus AUCUNE pilule d'alerte empilée en tête (kb-badge-perdu/rappel/expire).
  assert.doesNotMatch(SRC, /kb-badge-perdu/)
  assert.doesNotMatch(SRC, /kb-badge-rappel/)
})

test('VX24 : la pill d\'âge est rendue dans le pied de carte (kb-card-foot), et « Inactif N j »+horloge ont quitté la face', () => {
  const footStart = SRC.indexOf('<div className="kb-card-foot">')
  assert.ok(footStart > -1, 'kb-card-foot introuvable')
  const footEnd = SRC.indexOf('{/* ── Actions rapides', footStart)
  assert.ok(footEnd > footStart, 'fin de pied introuvable')
  const foot = SRC.slice(footStart, footEnd)
  assert.match(foot, /className="kb-age-pill"/)
  // Les anciens marqueurs de tête/pied disparaissent (absorbés par la pill d'âge).
  assert.doesNotMatch(SRC, /Inactif \{jInactif\} j/)
  assert.doesNotMatch(SRC, /kb-foot-inactif/)
})
