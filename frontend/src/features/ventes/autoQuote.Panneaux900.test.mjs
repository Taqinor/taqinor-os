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

test('autoQuote.js : le fallback sans besoinKwc/optimiseur laisse `panels` à 0, jamais un nombre deviné', () => {
  const idx = SRC.indexOf('let panels = 0')
  assert.ok(idx > -1, 'panels doit être initialisé à 0 (aucune supposition par défaut)')
  const bloc = SRC.slice(idx, idx + 3200)
  assert.match(bloc, /panels = opt\.nbPanneaux > 0 \? opt\.nbPanneaux : 0/,
    "l'échec de l'optimiseur local doit laisser panels à 0, jamais un repli 900 MAD")
})

test('autoQuote.js : `target_kwc` est OMIS (pas envoyé à 0) quand aucune taille locale — le serveur dimensionne', () => {
  const idx = SRC.indexOf('reponse = await ventesApi.creerDevisAuto({')
  assert.ok(idx > -1, "l'appel creerDevisAuto est introuvable")
  const bloc = SRC.slice(idx, idx + 1400)
  assert.match(bloc, /\.\.\.\(kwpAuto > 0 \? \{ target_kwc: kwpAuto \} : \{\}\)/,
    'target_kwc doit être un spread conditionnel — jamais envoyé quand kwpAuto est 0')
})

test('autoQuote.js : industriel/commercial refusent explicitement plutôt que de créer un devis sans panneau', () => {
  assert.match(SRC,
    /if \(\(mode === 'industriel' \|\| mode === 'commercial'\) && panels <= 0\) \{/,
    'la garde industriel/commercial sans taille locale est introuvable')
  const idx = SRC.indexOf("if ((mode === 'industriel' || mode === 'commercial') && panels <= 0) {")
  const bloc = SRC.slice(idx, idx + 300)
  assert.match(bloc, /throw \{/)
  assert.match(bloc, /detail:/)
})
