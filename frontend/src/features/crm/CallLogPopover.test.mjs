// VX87 — Journal d'appel en un geste : structure du composant + du hook de
// nudge. Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/features/crm/CallLogPopover.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'CallLogPopover.jsx'), 'utf8')
// LW37 — le composer (dont CallLogPopover) a migré de LeadForm vers l'onglet
// Historique du cockpit (`TimelineTab`).
const TIMELINE_SRC = readFileSync(join(HERE, 'workspace', 'TimelineTab.jsx'), 'utf8')
const LEADCARD_SRC = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'views', 'LeadCard.jsx'), 'utf8',
)
const LISTVIEW_SRC = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'views', 'ListView.jsx'), 'utf8',
)

test('VX87 : le popover appelle crmApi.logInteraction (ressuscite le site d\'appel)', () => {
  assert.match(SRC, /crmApi\.logInteraction\(leadId, \{/)
})

test('VX87 : la « prochaine action » pose relance_date via updateLead dans le MÊME geste', () => {
  assert.match(SRC, /crmApi\.updateLead\(leadId, \{ relance_date: dateInDays\(nextActionDays\) \}\)/)
})

test('VX87 : les 5 issues OUTCOME_LABELS (hors clé vide) sont proposées comme choix', () => {
  assert.match(SRC, /OUTCOME_CHOICES = Object\.entries\(OUTCOME_LABELS\)\.filter/)
})

test('VX87 : 4 délais de prochaine action (J+0/1/3/7)', () => {
  assert.match(SRC, /key: 0.*Aujourd/)
  assert.match(SRC, /key: 1.*Demain/)
  assert.match(SRC, /key: 3.*Dans 3 j/)
  assert.match(SRC, /key: 7.*Dans 7 j/)
})

test('VX87 : useCallEndedNudge s\'abonne à visibilitychange', () => {
  assert.match(SRC, /export function useCallEndedNudge/)
  assert.match(SRC, /document\.addEventListener\('visibilitychange', onVisibilityChange\)/)
})

test('VX87 : TimelineTab (onglet Historique du cockpit) monte CallLogPopover', () => {
  assert.match(TIMELINE_SRC, /import CallLogPopover from '\.\.\/CallLogPopover'/)
  assert.match(TIMELINE_SRC, /<CallLogPopover/)
})

test('VX87 : LeadCard.jsx arme le nudge sur les deux liens tel: (swipe + contact)', () => {
  assert.match(LEADCARD_SRC, /useCallEndedNudge/)
  const armCount = (LEADCARD_SRC.match(/armCallNudge\(\)/g) || []).length
  assert.ok(armCount >= 2, `attendu ≥2 sites d'armement, trouvé ${armCount}`)
})

test('VX87 : ListView.jsx arme le nudge sur les deux liens tel: (icône compacte + colonne)', () => {
  assert.match(LISTVIEW_SRC, /useCallEndedNudge/)
  const armCount = (LISTVIEW_SRC.match(/armCallNudgeFor\(lead\)/g) || []).length
  assert.ok(armCount >= 2, `attendu ≥2 sites d'armement, trouvé ${armCount}`)
})
