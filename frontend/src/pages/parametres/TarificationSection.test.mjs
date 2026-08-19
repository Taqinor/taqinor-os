// ORDRE FONDATEUR (19/08/2026) — barème ONEE réglable par société : verrou de
// SOURCE (JSX, pas de node_modules installés dans ce lane — cf.
// avance-cf-repartition.test.mjs) sur les valeurs 2026 (TVA 20 %) affichées
// par défaut et sur le câblage écran → API → page Paramètres.
//   node --test src/pages/parametres/TarificationSection.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'TarificationSection.jsx'), 'utf8')
const HOST = readFileSync(join(HERE, 'ParametresEntreprise.jsx'), 'utf8')
const API = readFileSync(join(HERE, '..', '..', 'api', 'parametresApi.js'), 'utf8')

test('DEFAULT_TIERS porte les six valeurs 2026 (TVA 20 %, ancre fondateur > 500 kWh)', () => {
  assert.match(SRC, /prix_kwh_ttc: '0\.916272'/)
  assert.match(SRC, /prix_kwh_ttc: '1\.091388'/)
  assert.match(SRC, /prix_kwh_ttc: '1\.187388'/)
  assert.match(SRC, /prix_kwh_ttc: '1\.405116'/)
  // Ancre fondateur (19/08/2026, facture réelle) : tranche > 500 kWh.
  assert.match(SRC, /prix_kwh_ttc: '1\.622856'/)
  // Plus aucune trace des anciennes valeurs (TVA 2025, 18 %).
  assert.doesNotMatch(SRC, /0\.9010|1\.0732|1\.1676|1\.3817|1\.5958/)
})

test('les prix de palier restent des champs libres (step="any", jamais snap/reject)', () => {
  assert.match(SRC, /type="number" step="any"[\s\S]*?aria-label=\{`Prix palier \$\{i \+ 1\}`\}/)
})

test('save() enregistre via parametresApi.updateTariffSettings, avec toast d’erreur', () => {
  assert.match(SRC, /parametresApi\.updateTariffSettings\(payload\)/)
  assert.match(SRC, /toast\.error\(/)
})

test('la section est câblée sur l’onglet « tarification » de Paramètres > Entreprise', () => {
  assert.match(HOST, /import TarificationSection from '\.\/TarificationSection'/)
  assert.match(HOST, /tab === 'tarification' && <TarificationSection \/>/)
})

test('parametresApi expose getTariffSettings/updateTariffSettings', () => {
  assert.match(API, /getTariffSettings/)
  assert.match(API, /updateTariffSettings/)
})
