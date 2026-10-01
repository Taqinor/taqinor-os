// QJR644 — UNE seule temporisation de 500 ms pour l'aperçu du moteur horaire.
// `useEtudeHorairePreview` temporise déjà le corps (500 ms) ; `useSizingMoteur`
// rejouait un second `useDebouncedValue(cleCourante, 500)` pour reconstruire
// la clé en vol (deux minuteries synchronisées par simple convention). Le hook
// d'aperçu sert désormais `corpsEnVol` (la clé réellement envoyée) et
// `corpsEchoue` (la clé dont la requête a échoué) ; le second debounce et
// `cleEnVolPourChargement` sont supprimés.
//
// Les fichiers `use*.js` importent React et l'API (non exécutables sous
// `node --test`, cf. `hooks.test.mjs`) : ce test garde leur CÂBLAGE ; la
// décision elle-même est exécutée par `hooks.test.mjs` (moitié pure) et les
// scénarios d'échec périmé par DevisGeneratorSizingServeur / EtudeHoraire.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ici = path.dirname(fileURLToPath(import.meta.url))
const hook = readFileSync(path.join(ici, 'useSizingMoteur.js'), 'utf8')
const apercu = readFileSync(path.join(ici, '..', '..', 'etudeHorairePreview.js'), 'utf8')

test('useSizingMoteur ne rejoue plus de second debounce', () => {
  assert.doesNotMatch(hook, /useDebouncedValue\(/)
  assert.doesNotMatch(hook, /cleEnVolPourChargement/)
})

test('useSizingMoteur attribue l’échec à la clé servie par le hook d’aperçu', () => {
  assert.match(hook, /corpsEchoue/)
  assert.match(hook, /const cleErreur = erreur \? \(corpsEchoue \?\? null\) : null/)
})

test('le hook d’aperçu expose corpsEnVol et corpsEchoue, avec son UNIQUE temporisation de 500 ms', () => {
  assert.match(apercu, /return \{ donnees, chargement, erreur, corpsServi, corpsEnVol, corpsEchoue \}/)
  assert.equal(apercu.match(/useDebouncedValue\(/g)?.length, 1)
  assert.match(apercu, /useDebouncedValue\(corpsKey, 500\)/)
  assert.match(apercu, /setCorpsEnVol\(debouncedKey\)/)
  assert.match(apercu, /setCorpsEchoue\(debouncedKey\)/)
})
