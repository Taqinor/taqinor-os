// WIR154 — administration Notifications (Paramètres > Notifications) : routage,
// calendrier ouvré/fériés, annonces, gabarits WhatsApp. Vérification de SOURCE
// (JSX, pas de node_modules dans ce lane).
//   node --test src/pages/parametres/notifications-admin-wir154.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (...p) => readFileSync(join(HERE, ...p), 'utf8')
const API = read('..', '..', 'api', 'notificationsApi.js')
const SECTION = read('NotificationsAdminSection.jsx')
const CONST = read('peConstants.js')
const PARAMS = read('ParametresEntreprise.jsx')

test('notificationsApi expose les 4 surfaces admin', () => {
  assert.match(API, /getRoutingRules:[\s\S]*?routing-rules\//)
  assert.match(API, /saveWorkingHours:[\s\S]*?working-hours\/current\//)
  assert.match(API, /createHoliday:/)
  assert.match(API, /publierAnnonce:[\s\S]*?\/publier\//)
  assert.match(API, /submitWhatsAppTemplate:[\s\S]*?\/submit\//)
  assert.match(API, /decisionWhatsAppTemplate:[\s\S]*?\/decision\//)
})

test('la section couvre les 4 panneaux', () => {
  assert.match(SECTION, /function RoutingRulesPanel/)
  assert.match(SECTION, /function CalendrierPanel/)
  assert.match(SECTION, /function AnnoncesPanel/)
  assert.match(SECTION, /function WhatsAppTemplatesPanel/)
  // Actions clés câblées.
  assert.match(SECTION, /notificationsApi\.saveRoutingRule\(null,/)
  assert.match(SECTION, /notificationsApi\.saveWorkingHours\(/)
  assert.match(SECTION, /notificationsApi\.publierAnnonce\(/)
  assert.match(SECTION, /notificationsApi\.submitWhatsAppTemplate\(/)
  assert.match(SECTION, /notificationsApi\.decisionWhatsAppTemplate\(/)
})

test('un onglet Notifications est enregistré et rendu dans Paramètres', () => {
  assert.match(CONST, /key: 'notifications', label: 'Notifications'/)
  assert.match(PARAMS, /import NotificationsAdminSection from '\.\/NotificationsAdminSection'/)
  assert.match(PARAMS, /tab === 'notifications' && <NotificationsAdminSection \/>/)
})
