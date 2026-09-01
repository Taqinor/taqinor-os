// QJR215 — L'écran générateur pose, lit et régénère une surcharge, et montre
// le bloc `effectif`.
//
// AVANT ce correctif : `features/ventes/quote/overrides.js` était un module
// AJOUTÉ TESTÉ mais IMPORTÉ PAR PERSONNE côté écran (QJR214 lui a donné un
// client API — `ventesApi.lireOverrides/poserOverrides/regenererOverride` —
// mais AUCUN chemin de `DevisGenerator.jsx` ne les appelait). Aucun chemin ne
// permettait donc de poser une surcharge depuis l'écran.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE (même patron que
// DevisGeneratorReplyLocal.test.mjs / DevisGeneratorProvenanceDV3.test.mjs).
//
// Run : node --test src/pages/ventes/DevisGeneratorOverrides.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR215 — lecture du registre À L’OUVERTURE d’un devis existant', () => {
  assert.match(DG, /import \{ CHEMINS_AUTORISES \} from '\.\.\/\.\.\/features\/ventes\/quote\/overrides'/)
  assert.match(DG, /const chargerOverrides = \(id\) => \{/)
  assert.match(DG, /ventesApi\.lireOverrides\(id\)/)
  // Déclenché par un effet calé sur editDevis?.id (pas un bouton — l'ouverture
  // du devis suffit), jamais à la création (pas encore d'id serveur).
  assert.match(
    DG,
    /useEffect\(\(\) => \{\s*\n\s*if \(editDevis\?\.id\) chargerOverrides\(editDevis\.id\)\s*\n\s*\}, \[editDevis\?\.id\]\)/,
  )
})

test('QJR215 — pose EXPLICITE : le vendeur DÉCLARE un chemin + une valeur (JSON tolérant), jamais deviné', () => {
  assert.match(DG, /const poserOverride = async \(\) => \{/)
  assert.match(DG, /ventesApi\.poserOverrides\(editDevis\.id, \{\s*\n\s*\[ovChemin\]: \{ valeur \},\s*\n\s*\}\)/)
  // La valeur est déclarée par le vendeur (état ovValeur/ovChemin), pas
  // recalculée depuis une autre entrée de l'écran.
  assert.match(DG, /const \[ovChemin, setOvChemin\] = useState\(CHEMINS_AUTORISES\[0\]\)/)
  assert.match(DG, /const \[ovValeur, setOvValeur\] = useState\(''\)/)
})

test('QJR215 — round-trip complet : la réponse du PATCH remplace l’état local (relecture), pas de second GET nécessaire', () => {
  const idx = DG.indexOf('const poserOverride = async () => {')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx, idx + 700)
  assert.match(bloc, /const \{ data \} = await ventesApi\.poserOverrides/)
  assert.match(bloc, /setOverridesReg\(data\)/)
})

test('QJR215 — régénération : DELETE ?chemin= reçoit la valeur moteur, remplace l’état local', () => {
  assert.match(DG, /const regenererOverride = async \(chemin\) => \{/)
  const idx = DG.indexOf('const regenererOverride = async (chemin) => {')
  const bloc = DG.slice(idx, idx + 500)
  assert.match(bloc, /ventesApi\.regenererOverride\(editDevis\.id, chemin\)/)
  assert.match(bloc, /setOverridesReg\(data\)/)
})

test('QJR215 — un refus 400 est affiché TEL QUEL, jamais avalé', () => {
  assert.match(DG, /const messageErreurOverrides = \(err\) => \{/)
  assert.match(DG, /const \[overridesErreur, setOverridesErreur\] = useState\(null\)/)
  // L'erreur est posée dans le catch de poserOverride ET de regenererOverride
  // (jamais un simple `.catch(() => {})` qui avalerait le refus).
  const idxPoser = DG.indexOf('const poserOverride = async () => {')
  const blocPoser = DG.slice(idxPoser, idxPoser + 700)
  assert.match(blocPoser, /setOverridesErreur\(messageErreurOverrides\(err\)\)/)
  const idxRegen = DG.indexOf('const regenererOverride = async (chemin) => {')
  const blocRegen = DG.slice(idxRegen, idxRegen + 500)
  assert.match(blocRegen, /setOverridesErreur\(messageErreurOverrides\(err\)\)/)
  // Rendu : le message est bien affiché à l'écran, gardé par overridesErreur.
  assert.match(DG, /\{overridesErreur && \(/)
  assert.match(DG, /data-testid="overrides-erreur"/)
})

test('QJR215 — messageErreurOverrides gère les TROIS formes de refus du serveur (jamais une phrase générique quand un texte existe)', () => {
  const idx = DG.indexOf('const messageErreurOverrides = (err) => {')
  assert.ok(idx > -1)
  const fin = DG.indexOf('\n  }', idx)
  const corps = DG.slice(idx, fin + 4)
  // {"detail": "..."} et {"chemin": "..."} : valeur texte directe.
  assert.match(corps, /const brut = Object\.values\(data\)\[0\]/)
  // {"chemin": ["..."]} : DRF range le détail dans une liste.
  assert.match(corps, /Array\.isArray\(brut\) \? brut\[0\] : brut/)
})

test('QJR215 — le panneau « Surcharges » n’existe QUE sur un devis déjà enregistré (editDevis?.id)', () => {
  const idx = DG.indexOf('data-testid="overrides-panel"')
  assert.ok(idx > -1, 'le panneau overrides est introuvable')
  const avant = DG.slice(Math.max(0, idx - 400), idx)
  assert.match(avant, /\{editDevis\?\.id && \(/)
})

test('QJR215 — le bloc effectif montre auto/manuel/effectif CÔTE À CÔTE, et un régénérer par chemin en mode manuel', () => {
  assert.match(DG, /data-testid="overrides-effectif-table"/)
  assert.match(DG, /\{v\.auto == null \? '—' : JSON\.stringify\(v\.auto\)\}/)
  assert.match(DG, /\{v\.manuel == null \? '—' : JSON\.stringify\(v\.manuel\)\}/)
  assert.match(DG, /\{v\.effectif == null \? '—' : JSON\.stringify\(v\.effectif\)\}/)
  assert.match(DG, /data-testid=\{`overrides-regenerer-\$\{chemin\}`\}/)
  // Un chemin resté automatique n'a pas de bouton régénérer (rien à régénérer).
  assert.match(DG, /\{v\.source === 'manuel' && \(/)
})

test('QJR215 — la liste des chemins proposés vient de CHEMINS_AUTORISES (contrat), jamais une énumération recopiée', () => {
  assert.match(DG, /\{CHEMINS_AUTORISES\.map\(\(c\) => \(/)
})
