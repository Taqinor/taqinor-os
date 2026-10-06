// U3-900 (fondateur 29/08/2026, « ALL sizing goes through the new sizing
// tool, and i said ALL sizing ») — verrouille la SUPPRESSION du repli
// `estimerPanneaux` (panneaux/900 MAD) dans autoQuote.js : le backend a déjà
// supprimé la règle (apps/ventes/dimensionnement.py, services.py
// _panneaux_dimensionnement_horaire) ; ce test verrouille le CÔTÉ ÉCRAN.
//
// autoQuote.js ne peut pas être importé tel quel par `node --test` (voir
// autoQuote.paliers.test.mjs) : ce test lit donc le SOURCE, même patron.
//
// Run : node --test src/features/ventes/autoQuote.Panneaux900.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')

test("autoQuote.js : n'importe plus estimerPanneaux depuis solar.js", () => {
  const idx = SRC.indexOf("} from './solar'")
  assert.ok(idx > -1, "l'import de solar.js est introuvable")
  const bloc = SRC.slice(Math.max(0, idx - 900), idx)
  assert.ok(!/\bestimerPanneaux\b/.test(bloc),
    "estimerPanneaux ne doit plus être importé : la règle des 900 MAD est supprimée")
})

test("autoQuote.js : n'appelle plus JAMAIS estimerPanneaux (aucune occurrence exécutable)", () => {
  // Les seules occurrences tolérées sont dans des COMMENTAIRES expliquant la
  // suppression (préfixés `//`) — jamais un appel `estimerPanneaux(`.
  assert.ok(!/estimerPanneaux\(/.test(SRC),
    'un appel estimerPanneaux(...) subsiste — la règle des 900 MAD doit être totalement retirée')
})

test('CIQ127 — autoQuote.js : `panels` ne vient QUE d\'une taille explicite, jamais d\'un nombre deviné', () => {
  assert.match(SRC, /const panels = tailleKwc > 0 \? panneauxPourKwc\(tailleKwc, PANEL_W_DEFAUT\) : 0/)
})

// U3-MOTEUR (fondateur 29/08/2026, « ALL sizing goes through the new sizing
// tool ») — le DERNIER contournement : au-dessus du seuil de facture, le
// devis auto RÉSIDENTIEL chiffrait lui-même les paliers de 5 kWc
// (`optimalKwcByPayback`) et expédiait le résultat en `target_kwc` souverain,
// si bien que ces devis-là ne touchaient jamais le moteur horaire.
test('CIQ127 — autoQuote.js : plus AUCUN balayage local par paliers, pour aucun marché', () => {
  assert.ok(!/optimalKwcByPayback\(|parametresBalayageCI\(|estimerKwcDepuisFacture\(/.test(SRC),
    'le dimensionnement C&I est celui du moteur serveur (CIQ120), jamais un balayage écran')
})

test("autoQuote.js : le devis auto RÉSIDENTIEL sans taille explicite n'envoie AUCUN target_kwc calculé à l'écran", () => {
  // Preuve structurelle : `kwpAuto` ne peut venir que de `panels`, et `panels`
  // n'est alimenté en résidentiel que par la branche « taille explicite ».
  // QJR576 — LA conversion partagée (kwcPourPanneaux = n × W / 1000).
  assert.match(SRC, /const kwpAuto = panels > 0 \? kwcPourPanneaux\(panels, PANEL_W_DEFAUT\) : 0/,
    'kwpAuto doit rester dérivé de panels uniquement')
  const idx = SRC.indexOf('reponse = await ventesApi.creerDevisAuto({')
  assert.ok(idx > -1, "l'appel creerDevisAuto est introuvable")
  const bloc = SRC.slice(idx, idx + 1600)
  assert.match(bloc, /\.\.\.\(kwpAuto > 0 \? \{ target_kwc: kwpAuto \} : \{\}\)/,
    'target_kwc reste un spread conditionnel — omis quand aucune taille explicite')
  // Aucun appel à l'optimiseur ne doit subsister dans la branche résidentielle
  // (entre la garde `mode === 'residentiel'` et son `return id`).
  const residIdx = SRC.indexOf("if (mode === 'residentiel') {")
  assert.ok(residIdx > -1, 'la branche résidentielle est introuvable')
  const finResid = SRC.indexOf('return id', residIdx)
  const brancheResid = SRC.slice(residIdx, finResid)
  assert.ok(!/optimalKwcByPayback\(/.test(brancheResid),
    "la branche résidentielle ne doit plus chiffrer de palier : c'est le moteur horaire qui dimensionne")
})

test('autoQuote.js : `target_kwc` est OMIS (pas envoyé à 0) quand aucune taille locale — le serveur dimensionne', () => {
  const idx = SRC.indexOf('reponse = await ventesApi.creerDevisAuto({')
  assert.ok(idx > -1, "l'appel creerDevisAuto est introuvable")
  const bloc = SRC.slice(idx, idx + 1400)
  assert.match(bloc, /\.\.\.\(kwpAuto > 0 \? \{ target_kwc: kwpAuto \} : \{\}\)/,
    'target_kwc doit être un spread conditionnel — jamais envoyé quand kwpAuto est 0')
})

test('CIQ127 — autoQuote.js : industriel/commercial partent au serveur, qui refuse en nommant la donnée', () => {
  assert.match(SRC,
    /return creerDevisServeur\(\{ lead, discountStr, onAlertes, targetKwc, marche: mode \}\)/)
  const idx = SRC.indexOf('async function creerDevisServeur(')
  const bloc = SRC.slice(idx, idx + 1200)
  assert.match(bloc, /ventesApi\.creerDevisAuto\(/)
  assert.match(bloc, /\.\.\.\(data\.field \? \{ field: data\.field \} : \{\}\)/)
})
