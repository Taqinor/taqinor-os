// PVORD (fondateur 19/08/2026) — ordre des lignes de devis.
// `createAutoQuote` créait jadis ses lignes à l'écran (C&I) en portant
// `ordre: idx`. CIQ127 — le devis automatique ne crée PLUS AUCUNE ligne à
// l'écran, quel que soit le marché : le serveur compose et ordonne (ordre
// société `ordre_lignes`, PVORD), via `POST /ventes/devis/auto/`. Ce fichier
// verrouille donc l'absence de toute création de ligne côté navigateur.
//
// Lecture du SOURCE (autoQuote.js importe ventesApi/axios, non importable sous
// `node --test`), même patron que LeadDevisPanel.wiring.test.mjs.
// Run : node --test src/features/ventes/autoQuote.ordre.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')

// Ne garde que le CODE : un commentaire peut légitimement mentionner
// l'ancien patron sans que ce soit une régression.
const CODE = SRC
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .split('\n')
  .filter((ligne) => !ligne.trim().startsWith('//'))
  .join('\n')

test('CIQ127 — aucune ligne créée par le navigateur (ni atomique, ni une par une)', () => {
  assert.doesNotMatch(CODE, /addLigneDevis|createDevis\(|createDevisAtomic|lignes,?\s*\}\)/)
  assert.doesNotMatch(CODE, /ordre:\s*idx|ordreLignes/)
})

test('CIQ127 — les quatre marchés passent par POST /ventes/devis/auto/', () => {
  const appels = CODE.match(/ventesApi\.creerDevisAuto\(/g) || []
  assert.equal(appels.length, 2, 'résidentiel + creerDevisServeur (agricole, commercial, industriel)')
})
