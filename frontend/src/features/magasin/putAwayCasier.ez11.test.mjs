// EZ11 — Le casier EFFECTIF redevient vrai (fin de la donnée fausse en
// silence). L'écran appelait `rangerPutAway(row.id)` SANS casier alors que TOUT
// existait déjà côté API : `rangerPutAway(id, binId)` envoie `{bin}`,
// `PutAwayViewSet.ranger` valide un `bin` optionnel borné société et pose
// `bin_effectif`, et `getBinLocations` liste les casiers. Ranger AILLEURS
// enregistrait donc le casier SUGGÉRÉ, pas le vrai. Correction 100 % frontend.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = readFileSync(path.join(__dirname, 'PutAwayScreen.jsx'), 'utf8')
const api = readFileSync(path.join(__dirname, '..', '..', 'api', 'installationsApi.js'), 'utf8')

test('le paramètre casier est enfin branché', () => {
  assert.match(src, /const ranger = async \(row, binId\) => \{/)
  assert.match(src, /installationsApi\.rangerPutAway\(row\.id, binId\)/)
  // On regarde le CODE, pas la prose : le commentaire de tête a le droit de
  // citer l'ancien appel pour raconter le bug.
  const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /rangerPutAway\(row\.id\)/)
  // L'API l'acceptait déjà : rien n'a été ajouté côté client HTTP.
  assert.match(api, /rangerPutAway: \(id, binId\) =>/)
  assert.match(api, /binId \? \{ bin: binId \} : \{\}/)
})

test('le chemin par DÉFAUT reste à un seul tap', () => {
  // « Ranger » appelle toujours `ranger(row)` sans casier → le serveur retombe
  // sur le casier suggéré, exactement comme avant.
  assert.match(src, /id: 'ranger',[\s\S]{0,160}?onClick: \(\) => ranger\(row\)/)
  // « Ranger ailleurs… » est une action EN PLUS, pas un détour impose.
  assert.match(src, /id: 'ranger-ailleurs'/)
})

test('le casier suggéré est PRÉ-CHOISI dans le dialogue', () => {
  assert.match(src, /setBinChoisi\(row\.bin_suggere \? String\(row\.bin_suggere\) : null\)/)
  assert.match(src, /data-testid="putaway-casier-dialog"/)
  assert.match(src, /data-testid="putaway-casier-confirmer"/)
})

test('la liste des casiers vient de l’endpoint EXISTANT', () => {
  assert.match(src, /installationsApi\.getBinLocations\(\{ archived: '0' \}\)/)
  // Aucun autre appel réseau n'a été introduit sur cet écran.
  assert.deepEqual(
    [...new Set(src.match(/installationsApi\.\w+/g) ?? [])].sort(),
    ['installationsApi.getBinLocations', 'installationsApi.getPutAways',
      'installationsApi.rangerPutAway'],
  )
})

test('le retour utilisateur NOMME le casier réellement enregistré', () => {
  assert.match(src, /const casier = res\.data\?\.bin_effectif_code/)
  assert.match(src, /casier \? ` — casier \$\{casier\}\.` : '\.'/)
})
