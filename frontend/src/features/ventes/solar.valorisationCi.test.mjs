// CIQ228 — la valorisation C&I n'a plus de jumeau JS : solar.js n'EXPORTE plus
// le rachat 82-21 net ni l'injection (la revente vient de `economie_ci`,
// servie par le serveur). Remplace la parité Python ↔ JS de QX50 (retirée par
// CIQ201). AGEN13 — `KWH_PRICE` a suivi (plus de calcul local du ROI).
// Exécuté : on importe le module, on lit ses exports.
// Run : node --test src/features/ventes/solar.valorisationCi.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import * as solar from './solar.js'

const SUPPRIMES = [
  ['INJECTION', '_82_21'], ['netTarif', '8221'], ['injection', '8221'],
  ['tarifMt', 'Moyen'], ['TARIF_MT', '_ONEE'], ['computeEtude', 'Industrielle'],
].map((p) => p.join(''))

test('CIQ228 — aucun symbole de valorisation C&I exporté par solar.js', () => {
  for (const nom of SUPPRIMES) assert.equal(nom in solar, false, nom)
})

