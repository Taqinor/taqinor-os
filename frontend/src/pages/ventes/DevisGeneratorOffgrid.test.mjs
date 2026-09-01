// OFFGRID (ajout produit onduleur hors réseau) — verrou de régression pour le
// contrôle « Raccordement » de DevisGenerator.jsx : même patron « lecture de
// source » que generateurOptions.apx16.test.mjs / dimensionnementKwc.ez5.test.mjs
// (le fichier est trop lourd — ~5000 lignes, wiring API/Redux/Radix — pour un
// rendu React Testing Library fiable à écrire SANS pouvoir l'exécuter ici ;
// cette garde vérifie directement le code livré plutôt que de simuler un DOM).
//
// Contrat vérifié :
//   1. le contrôle « Raccordement » existe, à deux choix, DÉFAUT « Raccordé au
//      réseau » (byte-identique à l'historique) ;
//   2. le sélecteur Scénario est désactivé (jamais retiré du DOM) quand
//      `horsReseau` est vrai — un système hors réseau n'a qu'une option ;
//   3. `composeLocalement`/`handleAutoFill` routent vers la composition
//      hors réseau (`offgrid: horsReseau || undefined`, jamais la branche
//      L-2OPT ni la garde industriel/commercial qui viderait la batterie) ;
//   4. le dry-run serveur porte `hors_reseau: true` quand le contrôle est activé ;
//   5. `validate()` compte un onduleur hors réseau comme un onduleur (devis
//      hors réseau enregistrable sans ligne hybride factice) ;
//   6. le défaut dérive du lead (`raccordement === 'aucun'`), protégé par un
//      drapeau « touché » — jamais réécrit après un choix manuel du vendeur.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const gen = readFileSync(path.join(__dirname, 'DevisGenerator.jsx'), 'utf8')

test('contrôle « Raccordement » : deux choix, id stable, importe isOffgridInverter', () => {
  assert.match(gen, /isBattery, isHybridInverter, isReseauInverter, isOffgridInverter, isPanel, isPompe,/)
  assert.match(gen, /<Label htmlFor="gen-raccordement">Raccordement<\/Label>/)
  assert.match(gen, /<SelectTrigger id="gen-raccordement">/)
  assert.match(gen, /<SelectItem value="reseau">Raccordé au réseau<\/SelectItem>/)
  assert.match(gen, /<SelectItem value="hors_reseau">Hors réseau \(site isolé\)<\/SelectItem>/)
})

test('état : `horsReseau` démarre à `false` (défaut byte-identique), avec son drapeau « touché »', () => {
  assert.match(gen, /const \[horsReseau, setHorsReseau\] = useState\(false\)/)
  assert.match(gen, /const \[horsReseauTouched, setHorsReseauTouched\] = useState\(false\)/)
})

test('le Select Raccordement pose `horsReseauTouched` avant `horsReseau` (choix manuel jamais réécrit)', () => {
  assert.match(gen,
    /value=\{horsReseau \? 'hors_reseau' : 'reseau'\}[\s\S]{0,120}?onValueChange=\{\(v\) => \{[\s\S]{0,80}?setHorsReseauTouched\(true\)[\s\S]{0,80}?setHorsReseau\(v === 'hors_reseau'\)/)
})

test('le sélecteur Scénario est désactivé (jamais retiré du DOM) en hors réseau', () => {
  assert.match(gen,
    /<Select value=\{scenario\} onValueChange=\{onScenarioChange\} disabled=\{horsReseau\}>/)
})

test('défaut dérivé du lead : raccordement === \'aucun\' → horsReseau, protégé par horsReseauTouched', () => {
  assert.match(gen,
    /if \(!horsReseauTouched\) setHorsReseau\(lead\.raccordement === 'aucun'\)/)
})

test('composeLocalement : `offgrid` transmis à autoFillLines, jamais la fusion L-2OPT ni la garde indus/commercial en hors réseau', () => {
  assert.match(gen, /offgrid: horsReseau \|\| undefined,/)
  // La fusion L-2OPT (deux optimiseurs sans/avec) ne s'active plus si horsReseau.
  assert.match(gen,
    /if \(!horsReseau && modeInstallation === 'residentiel'\s*\n\s*&& \(scenario === SCENARIO_LES_DEUX \|\| scenario === SCENARIO_AVEC\)\) \{/)
  // La garde industriel/commercial (qui vide batterie/hybride) ne touche jamais
  // une composition hors réseau — un site isolé porte TOUJOURS sa batterie.
  assert.match(gen,
    /if \(!horsReseau && \(modeInstallation === 'industriel' \|\| modeInstallation === 'commercial'\)\) \{/)
  // Erreur hors réseau (aucun repli silencieux sur l'hybride) remontée à l'écran.
  assert.match(gen, /if \(horsReseau && generated\.offgridErreur\) \{/)
})

test('dry-run serveur : `hors_reseau: true` envoyé quand horsReseau est actif, jamais dimensionnement_avec', () => {
  assert.match(gen, /if \(horsReseau\) body\.hors_reseau = true/)
  assert.match(gen,
    /if \(!horsReseau && \(scenario === SCENARIO_LES_DEUX \|\| scenario === SCENARIO_AVEC\)\) \{/)
})

test('validate() : un onduleur hors réseau compte comme onduleur (devis hors réseau enregistrable seul)', () => {
  assert.match(gen,
    /const hasInverter = has\(d => isReseauInverter\(d\) \|\| isHybridInverter\(d\) \|\| isOffgridInverter\(d\)\)/)
})

test('brouillon local : horsReseau est sauvegardé/restauré comme accessoiresOnly (même patron d\'état)', () => {
  assert.match(gen, /prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,/)
  assert.match(gen,
    /if \(d\.horsReseau != null\) \{ setHorsReseau\(d\.horsReseau\); setHorsReseauTouched\(true\) \}/)
})

test('les gardes de saisie du générateur restent intactes (noValidate, jamais de snap)', () => {
  assert.match(gen, /<form id="gen-form"[\s\S]{0,200}?noValidate/)
  assert.doesNotMatch(gen, /step="0\.\d+"/)
})

// ── MODE_OPTIONS / sizingReducer MODES : contrat gardé, jamais une valeur ────
// hors réseau n'y a été ajoutée (ce n'est PAS un marché, c'est un raccordement).
test('MODE_OPTIONS reste à 4 valeurs — hors réseau n\'y ajoute JAMAIS de marché', () => {
  const m = gen.match(/const MODE_OPTIONS = \[([\s\S]*?)\]/)
  assert.ok(m, 'MODE_OPTIONS introuvable')
  const entries = m[1].match(/value: '\w+'/g) ?? []
  assert.deepEqual(entries, [
    "value: 'residentiel'", "value: 'industriel'",
    "value: 'commercial'", "value: 'agricole'",
  ])
})
