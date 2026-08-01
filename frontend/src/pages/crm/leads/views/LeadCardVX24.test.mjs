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

// APX2 — le ScoreBadge a QUITTÉ la tête : le budget de signaux de la carte au
// repos tient sur L2 (montant + icône d'action + micro-badge de score +
// pastille de rotting). La tête ne porte plus que « nom · société ».
test('VX24/APX2 : la tête ne porte que le nom (+ société) ; le score est sur L2', () => {
  const headStart = SRC.indexOf('<div className="kb-card-head">')
  assert.ok(headStart > -1, 'kb-card-head introuvable')
  // Fin de la tête : ouverture de la zone VALEUR juste après.
  const headEnd = SRC.indexOf('{/* ── L2 / VALEUR', headStart)
  assert.ok(headEnd > headStart, 'fin de tête introuvable')
  const head = SRC.slice(headStart, headEnd)
  assert.match(head, /<span className="kb-card-name">\{nomComplet\}<\/span>/)
  assert.match(head, /className="kb-card-societe"/)
  assert.doesNotMatch(head, /<ScoreBadge/)

  // Le score est bien rendu, en micro-badge, dans la ligne VALEUR.
  const valueStart = SRC.indexOf('<div className="kb-card-value">')
  const valueEnd = SRC.indexOf('{/* ── L3 / PIED', valueStart)
  assert.ok(valueEnd > valueStart, 'fin de zone valeur introuvable')
  const value = SRC.slice(valueStart, valueEnd)
  assert.match(value, /className="kb-card-score-micro"/)
  assert.match(value, /<ScoreBadge lead=\{lead\} \/>/)
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

test('VX24/APX2 : la pill d\'âge est rendue dans le pied (L3), et « Inactif N j »+horloge ont quitté la face', () => {
  const footStart = SRC.indexOf('<div className="kb-card-foot">')
  assert.ok(footStart > -1, 'kb-card-foot introuvable')
  // APX2 — le pied (L3) s'arrête à l'ouverture de la ZONE RÉVÉLÉE.
  const footEnd = SRC.indexOf('{/* ── ZONE RÉVÉLÉE', footStart)
  assert.ok(footEnd > footStart, 'fin de pied introuvable')
  const foot = SRC.slice(footStart, footEnd)
  assert.match(foot, /className="kb-age-pill"/)
  // Les anciens marqueurs de tête/pied disparaissent (absorbés par la pill d'âge).
  assert.doesNotMatch(SRC, /Inactif \{jInactif\} j/)
  assert.doesNotMatch(SRC, /kb-foot-inactif/)
})
