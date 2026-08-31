// QJR36 (audit L3 29/08/2026, origine QJF4) — sur N'IMPORTE QUELLE exception
// de `ventesApi.composerDevis` (dry-run serveur résidentiel), l'écran
// appelait `composeLocalement()` après un simple `console.error` : le vendeur
// recevait une composition JS que le dépôt documente lui-même comme
// divergente du serveur (câbles, marques épinglées, ordre des lignes,
// arrondi des panneaux) — sans AUCUN signal, et le devis pouvait être
// enregistré/envoyé sur cette composition.
//
// Correctif : réutilise le PATRON déjà posé par `sizingServeurMessage`
// (état + bannière visible) pour rendre ce repli visible, SANS changer son
// comportement (`composeLocalement()` reste appelé exactement pareil).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que
// DevisGeneratorSizingServeur.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorCompositionSourceLocale.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR36 — un état compositionSourceLocale existe (même patron que sizingServeurMessage)', () => {
  assert.match(DG, /const \[compositionSourceLocale, setCompositionSourceLocale\] = useState\(null\)/)
})

test('QJR36 — le catch du dry-run résidentiel pose compositionSourceLocale AVANT composeLocalement, sans changer le repli', () => {
  const idx = DG.indexOf("const { data } = await ventesApi.composerDevis(body)")
  assert.ok(idx > -1, "l'appel composerDevis est introuvable")
  // Fenêtre élargie (700→1300) : QJR99 a ajouté la note de bascule dans le
  // catch ; l'ordre et le contenu vérifiés, eux, sont inchangés.
  const bloc = DG.slice(idx, idx + 1300)
  // Succès : la bannière est effacée AVANT d'appliquer la composition serveur.
  assert.match(bloc, /setCompositionSourceLocale\(null\)\s*\n\s*appliquerCompositionServeur\(data\)/,
    'le succès doit effacer compositionSourceLocale avant appliquerCompositionServeur')
  // Échec : console.error est CONSERVÉ (comportement inchangé), la raison
  // est posée, et composeLocalement() reste appelé exactement comme avant.
  assert.match(bloc, /catch \(err\) \{/)
  assert.match(bloc, /console\.error\('composerDevis \(dry-run\) indisponible, repli local :', err\)/,
    'le console.error existant doit rester (comportement inchangé)')
  // QJR99 — la raison n'est plus rédigée dans ce catch : `raisonRepli` (moitié
  // pure de `useComposition`) la produit, ce qui la rend STRUCTURELLE. La cause
  // brute qu'elle reçoit est INCHANGÉE, et l'ordre catch → pose → repli aussi.
  assert.match(bloc, /setCompositionSourceLocale\(raisonRepli\(err\?\.message \|\| 'panne réseau\/serveur'\)\)/)
  assert.match(DG, /import \{ raisonRepli \} from '\.\.\/\.\.\/features\/ventes\/quote\/hooks\/useComposition'/,
    'la raison de repli doit venir du module de composition, jamais d\'une phrase locale')
  // composeLocalement() doit venir APRÈS la pose de l'état, dans le même catch.
  const catchIdx = bloc.indexOf('catch (err) {')
  const setIdx = bloc.indexOf('setCompositionSourceLocale(raisonRepli(err')
  const composeIdx = bloc.indexOf('composeLocalement()', catchIdx)
  assert.ok(catchIdx > -1 && setIdx > catchIdx && composeIdx > setIdx,
    'ordre attendu : catch → setCompositionSourceLocale(raison) → composeLocalement()')
})

test('QJR36 — la bannière est rendue avec le texte EXACT et un data-testid stable, gardée par compositionSourceLocale', () => {
  const idx = DG.indexOf('data-testid="composition-source-locale"')
  assert.ok(idx > -1, 'la bannière de repli local est introuvable')
  const bloc = DG.slice(idx - 200, idx + 300)
  assert.match(bloc, /\{compositionSourceLocale && \(/,
    'la bannière doit être gardée par compositionSourceLocale (jamais rendue par défaut)')
  assert.match(bloc,
    /Composition établie localement \(serveur indisponible\) — les\s*\n\s*quantités peuvent différer du devis serveur\./,
    'le texte exact de la bannière fondateur doit être rendu verbatim')
})

test('QJR36 — les autres marchés (industriel/commercial), qui n\'appellent jamais le dry-run serveur, ne POSENT jamais de raison — au plus ils EFFACENT (QJR211)', () => {
  // Le composeLocalement() de fin de fonction (branche non-résidentielle,
  // comportement local historique) ne doit JAMAIS écrire une raison de repli
  // (il n'a pas de dry-run à raconter) — seul le catch du dry-run résidentiel
  // le fait. QJR211 l'a fait passer de « aucune mention de l'état » à
  // « efface la bannière sur un succès » (une bannière de repli résidentiel
  // antérieure ne doit pas survivre à un marché qui a composé avec succès) :
  // ce test vérifie l'invariant qui SURVIT à QJR211, pas le texte exact.
  const idx = DG.lastIndexOf('if (composeLocalement()) setCompositionSourceLocale(null)')
  assert.ok(idx > -1, "l'appel de clôture de handleAutoFill (branches non-résidentielles) est introuvable")
  const bloc = DG.slice(Math.max(0, idx - 120), idx)
  assert.doesNotMatch(bloc, /setCompositionSourceLocale\(raisonRepli/,
    'les marchés sans dry-run serveur ne doivent jamais ÉCRIRE une raison de repli (ils peuvent seulement effacer, QJR211)')
})
