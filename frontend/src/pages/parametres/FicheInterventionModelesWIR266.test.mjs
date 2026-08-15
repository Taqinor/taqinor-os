// WIR266 — le drapeau `obligatoire` d'un champ de fiche d'intervention (le
// gate de clôture ZFSM1 : un champ obligatoire non renseigné BLOQUE la clôture)
// était rendu en badge… et réglable NULLE PART. Le formulaire d'ajout ne
// l'envoyait pas (tout champ naissait facultatif) et aucune bascule n'existait
// ensuite. Aucun changement backend : `saveFicheChamp` l'accepte déjà.
//
// Assertions au niveau SOURCE (pas de node_modules dans ce worktree) :
//   node --test src/pages/parametres/FicheInterventionModelesWIR266.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'FicheInterventionModelesSection.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/installationsApi.js'), 'utf8')

test('WIR266 : saveFicheChamp gère bien création ET mise à jour', () => {
  assert.match(API, /saveFicheChamp: \(id, data\) => id/)
})

test('WIR266 : la CRÉATION envoie désormais `obligatoire`', () => {
  const idx = SRC.indexOf('const addChamp')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, SRC.indexOf('const basculerObligatoire'))
  assert.match(bloc, /obligatoire,/)
  assert.match(SRC, /const \[obligatoire, setObligatoire\] = useState\(false\)/)
  // Le formulaire se réinitialise après ajout (le prochain champ ne naît pas
  // obligatoire par surprise).
  assert.match(bloc, /setObligatoire\(false\)/)
})

test('WIR266 : la case « Obligatoire (bloque la clôture) » existe au formulaire', () => {
  assert.match(SRC, /data-testid=\{`nouveau-champ-obligatoire-\$\{template\.id\}`\}/)
  assert.match(SRC, /Obligatoire \(bloque la clôture\)/)
  assert.match(SRC, /onCheckedChange=\{\(v\) => setObligatoire\(!!v\)\}/)
})

test('WIR266 : bascule d\'un champ EXISTANT via un PATCH PARTIEL', () => {
  const idx = SRC.indexOf('const basculerObligatoire')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, idx + 700)
  // Seul `obligatoire` est renvoyé : aucun risque d'écraser libellé/type/unité.
  assert.match(bloc, /saveFicheChamp\(champ\.id, \{ obligatoire: !champ\.obligatoire \}\)/)
  // La liste est rechargée depuis le parent (jamais un état local divergent).
  assert.match(bloc, /onChanged\?\.\(\)/)
})

test('WIR266 : chaque champ existant porte sa bascule, reliée à sa valeur serveur', () => {
  assert.match(SRC, /data-testid=\{`champ-obligatoire-\$\{c\.id\}`\}/)
  assert.match(SRC, /checked=\{!!c\.obligatoire\}/)
  assert.match(SRC, /onCheckedChange=\{\(\) => basculerObligatoire\(c\)\}/)
  // Double clic impossible pendant l'aller-retour serveur.
  assert.match(SRC, /disabled=\{bascule === c\.id\}/)
})

test('WIR266 : un échec serveur est affiché, jamais avalé', () => {
  const idx = SRC.indexOf('const basculerObligatoire')
  const bloc = SRC.slice(idx, idx + 700)
  assert.match(bloc, /setError\(e\?\.response\?\.data\?\.detail \|\| "Modification du champ impossible\."\)/)
})

test('WIR266 : Checkbox est bien importé du système UI', () => {
  assert.match(SRC, /Spinner, Checkbox,\s*\} from '\.\.\/\.\.\/ui'/)
})
