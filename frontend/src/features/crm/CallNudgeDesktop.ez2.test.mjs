// EZ2 — Verrous de SOURCE du nudge de bureau (le comportement lui-meme est
// couvert par CallNudgeDesktop.ez2.test.jsx, qui pilote de vraies horloges).
//   node --test src/features/crm/CallNudgeDesktop.ez2.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const SRC = lf(readFileSync(join(HERE, 'CallLogPopover.jsx'), 'utf8'))
const LISTE = lf(readFileSync(
  join(HERE, '../../pages/crm/leads/views/ListView.jsx'), 'utf8'))
const CARTE = lf(readFileSync(
  join(HERE, '../../pages/crm/leads/views/LeadCard.jsx'), 'utf8'))

test('EZ2 : les TROIS declencheurs existent, et le mobile garde le sien', () => {
  assert.match(SRC, /document\.addEventListener\('visibilitychange', onVisibilityChange\)/)
  assert.match(SRC, /window\.addEventListener\('focus', onFocus\)/)
  assert.match(SRC, /timerRef\.current = window\.setTimeout\(/)
})

test('EZ2 : LE PREMIER GAGNE — un declencheur desarme les autres', () => {
  assert.match(SRC, /const desarmer = \(\) => \{/)
  assert.match(SRC, /if \(timerRef\.current\) \{ clearTimeout\(timerRef\.current\); timerRef\.current = null \}/)
  // `declencher` desarme AVANT d'afficher : impossible d'en montrer deux.
  assert.match(SRC, /const declencher = \(\) => \{[\s\S]{0,220}?desarmer\(\)/)
})

test('EZ2 : le delai est INJECTABLE (gate e2e via page.clock)', () => {
  assert.match(SRC, /export function useCallEndedNudge\(\{ delayMs = NUDGE_DELAY_MS \} = \{\}\)/)
  assert.match(SRC, /const NUDGE_DELAY_MS = 45 \* 1000/)
  // Les appelants existants n'ont RIEN a changer (defaut).
  assert.match(LISTE, /useCallEndedNudge\(\)/)
  assert.match(CARTE, /useCallEndedNudge\(\)/)
})

test('EZ2 : la fenetre de 10 min est preservee (un onglet en fond ne surprend pas)', () => {
  assert.match(SRC, /const NUDGE_TIMEOUT_MS = 10 \* 60 \* 1000/)
  assert.match(SRC, /if \(elapsed <= NUDGE_TIMEOUT_MS\) setNudgeVisible\(true\)/)
})

test('EZ2 : le demontage nettoie le timer', () => {
  assert.match(SRC, /if \(timerRef\.current\) clearTimeout\(timerRef\.current\)/)
  assert.match(SRC, /window\.removeEventListener\('focus', onFocus\)/)
})

test('EZ2 : le clic tel: de la LISTE arme toujours le nudge (site verifie)', () => {
  assert.match(LISTE, /onClick=\{\(\) => armCallNudgeFor\(lead\)\}/)
})
