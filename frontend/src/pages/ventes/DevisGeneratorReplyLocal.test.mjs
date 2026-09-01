// QJR211 — La bannière « composition établie localement (serveur indisponible) »
// s'efface quand elle ne décrit plus rien.
//
// `DevisGenerator.jsx:2573` pose `compositionSourceLocale(raisonRepli(...))`
// dans le `catch` du dry-run résidentiel, mais AVANT ce correctif elle
// n'était remise à `null` QUE sur le chemin de succès résidentiel
// (`setCompositionSourceLocale(null)` juste avant `appliquerCompositionServeur`)
// : après un repli sur un autre marché (agricole, industriel, commercial), ou
// après un changement d'entrées qui relance le moteur avec succès sur CE
// marché, la bannière restait à l'écran en décrivant un calcul qui ne
// s'applique plus.
//
// Répro du Done= : repli industriel -> succès suivant -> bannière encore
// présente (AVANT le correctif). DevisGenerator.jsx est du JSX/ESM non
// exécutable par `node --test` sans node_modules (même contrainte que
// DevisGeneratorCompositionSourceLocale.test.mjs, DevisGeneratorSizingServeur
// .test.mjs) : ce test lit donc le SOURCE.
//
// Run : node --test src/pages/ventes/DevisGeneratorReplyLocal.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR211 — succès agricole (pompage) : efface une bannière de repli résidentiel antérieure', () => {
  // Répro : la bannière a été posée par un repli résidentiel PRÉCÉDENT, le
  // vendeur bascule sur agricole et l'auto-remplissage pompage réussit — la
  // bannière décrit alors un calcul résidentiel qui ne s'applique plus.
  const idx = DG.indexOf("if (modeInstallation === 'agricole') {")
  assert.ok(idx > -1, 'la branche agricole de handleAutoFill est introuvable')
  const finBranche = DG.indexOf('setPompageAutoFilled(true)', idx)
  assert.ok(finBranche > -1, 'la fin de la branche agricole (succès) est introuvable')
  const bloc = DG.slice(idx, finBranche)
  assert.match(
    bloc,
    /setLines\(withKeys\(generated\)\)[\s\S]*?setCompositionSourceLocale\(null\)/,
    'AVANT QJR211 : un succès agricole ne remettait jamais compositionSourceLocale à null — ' +
    'la bannière résidentielle antérieure survivait au changement de marché',
  )
})

test('QJR211 — succès indus/commercial : le composeLocalement() de clôture efface aussi la bannière', () => {
  // Répro EXACTE du Done= : repli industriel -> succès suivant -> avant
  // QJR211, `composeLocalement()` de clôture (branches non-résidentielles)
  // n'effaçait rien, laissant la bannière du repli précédent affichée.
  const closingCall = 'if (composeLocalement()) setCompositionSourceLocale(null)'
  assert.ok(
    DG.includes(closingCall),
    'AVANT QJR211 : le composeLocalement() de clôture (indus/commercial) était un appel nu ' +
    "(`composeLocalement()`), sans effacer compositionSourceLocale sur un succès",
  )
  // Un ÉCHEC de composeLocalement() (garde-fous internes, ex. "Entrez le
  // nombre de panneaux") ne doit PAS effacer la bannière — seul un VRAI
  // succès (valeur de retour truthy) l'efface. La forme conditionnelle
  // ci-dessus (`if (composeLocalement()) ...`) encode exactement cela :
  // pas de forme inconditionnelle qui effacerait même sur un échec.
  assert.doesNotMatch(
    DG,
    /composeLocalement\(\)\s*\n\s*setCompositionSourceLocale\(null\)/,
    'la bannière ne doit s’effacer QUE sur un succès (valeur de retour truthy), jamais inconditionnellement',
  )
})

test('QJR211 — le succès résidentiel (dry-run) continue d’effacer la bannière (comportement QJR36 préservé)', () => {
  const idx = DG.indexOf('const { data } = await ventesApi.composerDevis(body)')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx, idx + 300)
  assert.match(bloc, /setCompositionSourceLocale\(null\)\s*\n\s*appliquerCompositionServeur\(data\)/)
})

test('QJR211 — le catch du dry-run résidentiel POSE toujours la raison (repli lui-même inchangé)', () => {
  assert.match(
    DG,
    /setCompositionSourceLocale\(raisonRepli\(err\?\.message \|\| 'panne réseau\/serveur'\)\)\s*\n\s*composeLocalement\(\)/,
    'le repli résidentiel doit continuer à poser la raison AVANT son propre composeLocalement() ' +
    '(ce composeLocalement()-là ne doit PAS effacer ce qu’il vient de poser)',
  )
})

test('QJR211 — le testid et le texte de la bannière (contrat DOM) restent inchangés', () => {
  assert.match(DG, /data-testid="composition-source-locale"/)
  assert.match(DG, /data-testid="composition-source-locale-raison"/)
  assert.match(DG, /\{compositionSourceLocale && \(/)
})
