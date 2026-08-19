// EZ5 — Dimensionner en kWc, pas en nombre de panneaux.
// État d'avant : aucun champ « puissance cible » — on tapait un NOMBRE DE
// PANNEAUX puis on relisait le kWp calculé, alors que le client et le
// commercial disent « 3 kWc ». La conversion existait déjà
// (`panneauxPourKwc`, utilisée par le pré-remplissage depuis le lead) : EZ5 la
// RÉUTILISE, elle ne la réécrit pas.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { panneauxPourKwc } from '../../features/ventes/solar.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const gen = readFileSync(path.join(__dirname, 'DevisGenerator.jsx'), 'utf8')

test('le champ « Puissance cible (kWc) » existe', () => {
  assert.match(gen, /data-testid="gen-kwc-cible"/)
  assert.match(gen, /Puissance cible \(kWc\)/)
  assert.match(gen, /const \[kwcCible, setKwcCible\] = useState\(''\)/)
})

test('la conversion est RÉUTILISÉE, jamais réécrite', () => {
  assert.match(gen, /const n = panneauxPourKwc\(v, panelW\)/)
  // Aucune formule kWc→panneaux recopiée à la main dans l'écran.
  const handlers = gen.slice(gen.indexOf('const onKwcCibleChange'), gen.indexOf('const showSans'))
  assert.doesNotMatch(handlers, /Math\.round\(\s*\w+\s*\*\s*1000\s*\//)
  // U1 (fondateur 20/08/2026) — la conversion partagée est un PLAFOND : on ne
  // descend JAMAIS sous la puissance annoncée (« 8 panneaux par 5 kW »).
  // 3 kWc en panneaux de 550 W → 5,45 → 6 panneaux (5 ne feraient que 2,75 kWc).
  assert.equal(panneauxPourKwc(3, 550), 6)
  // 3 kWc en panneaux de 710 W → 4,23 → 5 panneaux (4 ne feraient que 2,84 kWc).
  assert.equal(panneauxPourKwc(3, 710), 5)
  // Le pivot de la demande fondateur : 5 kWc en 710 Wc font 8 panneaux, pas 7.
  assert.equal(panneauxPourKwc(5, 710), 8)
})

test('les deux champs sont BIDIRECTIONNELS', () => {
  assert.match(gen, /const onKwcCibleChange = \(v\) => \{/)
  assert.match(gen, /const onNbPanneauxChange = \(v\) => \{/)
  // Taper une cible remplit les panneaux…
  assert.match(gen, /onKwcCibleChange[\s\S]{0,220}?setNbPanneaux\(String\(n\)\)/)
  // …et changer les panneaux remet la cible à jour.
  assert.match(gen, /onNbPanneauxChange[\s\S]{0,320}?setKwcCible\(/)
  // Le champ des panneaux passe bien par le nouveau handler.
  assert.match(gen, /id="gen-nbpanneaux"[\s\S]{0,220}?onChange=\{e => onNbPanneauxChange\(e\.target\.value\)\}/)
})

test('un nombre de panneaux posé AILLEURS renseigne la cible, sans écraser une saisie', () => {
  // Pré-remplissage depuis un lead, dimensionnement pompage, reprise de
  // brouillon : la cible se remplit UNIQUEMENT si elle est encore vide.
  assert.match(gen, /if \(kwcCible !== '' \|\| kwp <= 0\) return/)
})

test('la garde de saisie du générateur est intacte (rien n’est jamais rejeté)', () => {
  // Le nouveau champ accepte n'importe quelle valeur tapée.
  assert.match(gen, /id="gen-kwc-cible" type="number" min="0" step="any"/)
  assert.match(gen, /<form id="gen-form"[\s\S]{0,200}?noValidate/)
  assert.doesNotMatch(gen, /step="0\.\d+"/)
})
