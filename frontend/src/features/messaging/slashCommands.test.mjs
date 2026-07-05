// Run: node --test src/features/messaging/slashCommands.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  activeSlashCommand, filterSlashCommands, resolveSlashSubmit, buildAideText,
  SLASH_COMMANDS,
} from './slashCommands.js'

test('activeSlashCommand : détecte une commande en cours de frappe (sans espace)', () => {
  assert.deepEqual(activeSlashCommand('/le'), { query: 'le', args: [], raw: '/le' })
})

test('activeSlashCommand : null si le texte ne commence pas par /', () => {
  assert.equal(activeSlashCommand('bonjour /lead'), null)
  assert.equal(activeSlashCommand(''), null)
  assert.equal(activeSlashCommand(null), null)
})

test('activeSlashCommand : commande résolue + arguments une fois un espace tapé', () => {
  const tok = activeSlashCommand('/lead Ahmed Casablanca')
  assert.equal(tok.query, 'lead')
  assert.deepEqual(tok.args, ['Ahmed', 'Casablanca'])
  assert.equal(tok.resolved.cmd, 'lead')
})

test('activeSlashCommand : null si la commande après le premier espace est inconnue', () => {
  assert.equal(activeSlashCommand('/inconnue foo'), null)
})

test('filterSlashCommands : filtre par préfixe et marque available selon le registre', () => {
  const allowed = new Set(['crm.lead.create'])
  const items = filterSlashCommands('le', allowed)
  assert.equal(items.length, 1)
  assert.equal(items[0].cmd, 'lead')
  assert.equal(items[0].available, true)
})

test('filterSlashCommands : une commande dont l’action n’est pas dans le registre est available:false', () => {
  const allowed = new Set() // registre vide
  const items = filterSlashCommands('devis', allowed)
  assert.equal(items.length, 1)
  assert.equal(items[0].available, false)
})

test('filterSlashCommands : /aide est toujours available (actionKey null)', () => {
  const items = filterSlashCommands('aide', new Set())
  assert.equal(items.length, 1)
  assert.equal(items[0].available, true)
})

test('filterSlashCommands : préfixe vide renvoie toutes les commandes déclarées', () => {
  assert.equal(filterSlashCommands('', new Set()).length, SLASH_COMMANDS.length)
})

test('resolveSlashSubmit : construit la question langage naturel pour /lead', () => {
  const resolved = resolveSlashSubmit('/lead Ahmed Casablanca')
  assert.equal(resolved.command.cmd, 'lead')
  assert.equal(resolved.question, 'Crée un lead nommé Ahmed (Casablanca).')
})

test('resolveSlashSubmit : /devis construit une question dédiée', () => {
  const resolved = resolveSlashSubmit('/devis Fatima Zahra')
  assert.equal(resolved.command.cmd, 'devis')
  assert.equal(resolved.question, 'Crée un devis pour Fatima Zahra.')
})

test('resolveSlashSubmit : null pour un texte qui n’est pas une commande', () => {
  assert.equal(resolveSlashSubmit('bonjour tout le monde'), null)
  assert.equal(resolveSlashSubmit(''), null)
})

test('resolveSlashSubmit : null pour une commande slash inconnue', () => {
  assert.equal(resolveSlashSubmit('/pasunecommande x'), null)
})

test('buildAideText : liste les commandes hors /aide elle-même, avec statut d’indisponibilité', () => {
  const text = buildAideText(new Set(['crm.lead.create']))
  assert.ok(text.includes('/lead'))
  assert.ok(text.includes('/devis'))
  assert.ok(!text.includes('/aide '))
  // /devis (ventes.devis.creer_auto) n'est pas dans le registre passé → marqué indisponible.
  assert.ok(text.includes('/devis') && text.includes('indisponible pour votre rôle'))
})
