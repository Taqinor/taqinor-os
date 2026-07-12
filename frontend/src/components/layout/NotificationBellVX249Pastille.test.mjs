// VX249(c) — pastille "pour moi/action" (pleine) vs "information société"
// (contour) : UN token, consommé À L'IDENTIQUE par la cloche
// (NotificationBell.jsx), Ma file (MesActivitesPage.jsx) et le Dashboard
// (Dashboard.jsx). Défaut prouvé : VX83/84/86 avaient chacun posé cette
// distinction (« pour moi » vs alertes société) sans jamais partager de
// convention visuelle — ce test couvre les 3 surfaces.
// Verified against SOURCE (no node_modules in this worktree/lane).
//   node --test src/components/layout/NotificationBellVX249Pastille.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const BELL_SRC = readFileSync(join(HERE, 'NotificationBell.jsx'), 'utf8')
const MAFILE_SRC = readFileSync(join(HERE, '../../pages/activities/MesActivitesPage.jsx'), 'utf8')
const DASH_SRC = readFileSync(join(HERE, '../../pages/Dashboard.jsx'), 'utf8')
const TOKENS_SRC = readFileSync(join(HERE, '../../design/tokens.css'), 'utf8')

test('tokens.css définit UN seul token pastille (pleine vs contour), jamais 3 conventions différentes', () => {
  assert.match(TOKENS_SRC, /\.vx-pastille\s*\{/)
  assert.match(TOKENS_SRC, /\.vx-pastille-mine\s*\{/)
  assert.match(TOKENS_SRC, /\.vx-pastille-company\s*\{/)
})

test('NotificationBell.jsx : « Activités en retard (pour moi) » + Approbations = mine, Garanties/Factures/Contrats/Visites = société', () => {
  const mineCount = (BELL_SRC.match(/vx-pastille-mine/g) || []).length
  const companyCount = (BELL_SRC.match(/vx-pastille-company/g) || []).length
  assert.equal(mineCount, 2, 'Approbations + Activités en retard (pour moi)')
  assert.equal(companyCount, 4, 'Garanties + Factures impayées + Contrats + Visites dues')
})

test('MesActivitesPage.jsx : « Ma file » est ENTIÈREMENT personnelle — jamais la variante société', () => {
  assert.match(MAFILE_SRC, /vx-pastille vx-pastille-mine/)
  assert.doesNotMatch(MAFILE_SRC, /vx-pastille-company/)
})

test('Dashboard.jsx : PriorityCard expose un prop `mine`, consommé par le même token', () => {
  assert.match(DASH_SRC, /mine = false,/)
  assert.match(DASH_SRC, /mine \? 'vx-pastille-mine' : 'vx-pastille-company'/)
})

test('Dashboard.jsx : « Mes leads »/« Mes devis »/« Mes tickets » portent `mine`, « SLA en retard » garde le défaut société', () => {
  for (const title of ['Mes leads à relancer', "Mes devis qui expirent ≤ 7 j", 'Mes tickets urgents']) {
    const start = DASH_SRC.indexOf(`title="${title}"`)
    assert.ok(start >= 0, `titre introuvable : ${title}`)
    const block = DASH_SRC.slice(start, start + 200)
    assert.match(block, /\bmine\b/, `"${title}" doit porter la prop mine`)
  }
  const slaStart = DASH_SRC.indexOf('title="SLA en retard"')
  assert.ok(slaStart >= 0)
  const slaBlock = DASH_SRC.slice(slaStart, slaStart + 200)
  assert.doesNotMatch(slaBlock, /\bmine\b/, '"SLA en retard" reste société (défaut)')
})

test('MesActivitesPage.jsx : la famille VX223 "rappel" a désormais sa propre icône (jamais le repli générique silencieux)', () => {
  assert.match(MAFILE_SRC, /rappel: PhoneIncoming,/)
})
