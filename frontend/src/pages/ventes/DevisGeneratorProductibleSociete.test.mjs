// QJR39 → AGEN11 (D-ACAL-97, contrôle C4-E7) — le productible société
// (`CompanyProfile.productible_kwh_kwc`) n'est plus lu par l'écran : QJR39
// l'avait branché sur un calcul LOCAL (`productibleForCity` → `computeROI`),
// un second moteur dont les chiffres pouvaient diverger de la fiche du lead.
// Depuis AGEN11 le moteur unique (serveur) lit ce réglage et l'écran affiche
// la conception servie : aucun productible, tarif ni rendement ne vit plus
// dans l'état de l'écran, aucun appel de calcul local ne subsiste.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE (patron historique des tests QJR
// de ce fichier) ; mutant : rappeler `productibleForCity(` ou `computeROI(`
// dans l'écran ou son hook d'aperçu ⇒ échec.
//
// Run : node --test src/pages/ventes/DevisGeneratorProductibleSociete.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { lireSourceGenerateur } from './DevisGeneratorSource.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = lireSourceGenerateur()
const APERCU = readFileSync(join(HERE, 'generator', 'hooks', 'useApercuEtude.js'), 'utf8')

test('AGEN11 — aucun calcul local de production, d’économie ni de payback dans l’écran devis', () => {
  for (const appel of ['productibleForCity(', 'computeROI(', 'paybackMoteurHoraire(']) {
    assert.ok(!DG.includes(appel), `${appel} ne doit plus être appelé par l'écran devis`)
    assert.ok(!APERCU.includes(appel), `${appel} ne doit plus être appelé par useApercuEtude`)
  }
})

test('AGEN11 — l’état de l’écran ne porte plus ni productible, ni tarif du kWh, ni rendement', () => {
  const idx = DG.indexOf('const [quoteLogic, setQuoteLogic] = useState({')
  assert.ok(idx > -1, 'état quoteLogic introuvable')
  const etat = DG.slice(idx, DG.indexOf('})', idx))
  for (const cle of ['productible', 'kwhPrice', 'efficiency']) {
    assert.ok(!new RegExp(`\\b${cle}\\s*:`).test(etat), `quoteLogic ne doit plus porter « ${cle} »`)
  }
  assert.ok(!DG.includes('data?.productible_kwh_kwc'), 'le productible société est lu par le moteur, pas par l’écran')
})

test('AGEN11 — l’aperçu de l’écran passe par le moteur unique (hook de conception)', () => {
  assert.match(APERCU, /useConceptionEcran\(/)
})
