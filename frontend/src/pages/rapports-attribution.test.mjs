// ZSAL6 — Rapport d'attribution des leads (Rapports.jsx, onglet Ventes &
// pipeline). Vérification de SOURCE (JSX, pas de node_modules installés dans
// ce lane — cf. SigneDialog.test.mjs pour la même convention).
//   node --test src/pages/rapports-attribution.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'Rapports.jsx'), 'utf8')

test('charge via crmApi.getAttributionLeads, même filtre de période que sales/stock/service', () => {
  assert.match(SRC, /import crmApi from '\.\.\/api\/crmApi'/)
  assert.match(SRC, /crmApi\.getAttributionLeads\(attrParams\)/)
  assert.match(SRC, /attrParams\.debut = from/)
  assert.match(SRC, /attrParams\.fin = to/)
})

test('changer la période remet aussi la carte attribution en chargement', () => {
  const resetBody = SRC.slice(
    SRC.indexOf('const resetPeriodCards ='), SRC.indexOf('const onFrom ='))
  assert.match(resetBody, /delete next\.attribution/)
})

test('affiche les deux tables ZSAL6 : par commercial et par source', () => {
  assert.match(SRC, /Par commercial/)
  assert.match(SRC, /Par source/)
  assert.match(SRC, /attribution\?\.par_commercial/)
  assert.match(SRC, /attribution\?\.par_source/)
})

test('drill-down par commercial réutilise le filtre owner déjà existant (pas de route inventée)', () => {
  const attribBody = SRC.slice(
    SRC.indexOf("renderReportCard('attribution'"), SRC.indexOf("{/* ── Stock"))
  assert.match(attribBody, /\/crm\/leads\?owner=\$\{encodeURIComponent\(r\.commercial\)\}/)
  // Pas de lien canal inventé : LeadsPage ne filtre pas par canal aujourd'hui.
  assert.doesNotMatch(attribBody, /\/crm\/leads\?canal=/)
})
