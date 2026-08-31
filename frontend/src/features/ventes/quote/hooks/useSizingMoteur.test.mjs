// QJR206 — La garde anti-réponse-périmée s'indexe sur le corps DÉBOUNCÉ, pas
// sur le corps courant. `useSizingMoteur.js` (le hook, PAS sa moitié pure)
// importe React + `useEtudeHorairePreview` (qui importe `ventesApi`/`axios`,
// dépendant de globaux navigateur) — comme documenté dans
// `hooks.test.mjs` : « les fichiers use*.js ... ne sont pas exécutables ici ».
// Confirmé empiriquement (`node --test` sur ce fichier échoue à la
// résolution d'import avant même d'atteindre le code React). La logique du
// CORRECTIF est donc extraite en fonction PURE exportée
// (`cleEnVolPourChargement`, sans aucun hook) et VÉRIFIÉE de deux façons :
//   (1) EXÉCUTION du texte RÉEL de la fonction (extrait du fichier source,
//       jamais recopié à la main) via `new Function` — ce n'est pas une
//       assertion regex sur le comportement, c'est le CODE RÉEL qui tourne ;
//   (2) une assertion de câblage (l'effet utilise bien `cleDebouncee`,
//       jamais `cleCourante`, et le pattern fautif d'avant QJR206 a disparu).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = readFileSync(path.join(__dirname, 'useSizingMoteur.js'), 'utf8')

// ── (1) exécute le VRAI corps de cleEnVolPourChargement, extrait du fichier ──

function extraireFonctionPure(source, nom) {
  const re = new RegExp(`export function ${nom}\\(([^)]*)\\)\\s*\\{([\\s\\S]*?)\\n\\}`)
  const m = source.match(re)
  assert.ok(m, `fonction pure ${nom} introuvable dans useSizingMoteur.js`)
  const [, params, corps] = m
  // Exécute le TEXTE RÉEL du fichier (extrait ci-dessus), pas une copie.
  return new Function(...params.split(',').map(p => p.trim()), corps)
}

const cleEnVolPourChargement = extraireFonctionPure(src, 'cleEnVolPourChargement')

test('(exécuté) en chargement, on retient la clé DÉBOUNCÉE — jamais la clé courante non débouncée', () => {
  // Répro du bug QJR206 : une requête pour "kwc:5" est en vol (chargement),
  // le vendeur tape déjà "kwc:8.52" mais AUCUNE requête n'est encore partie
  // pour cette nouvelle valeur (le debounce local n'a pas encore rattrapé).
  const cleDebouncee = '{"kwc":5}'         // ce qui a réellement été envoyé
  const precedente = null
  assert.equal(
    cleEnVolPourChargement(/* chargement */ true, cleDebouncee, precedente),
    '{"kwc":5}',
    'doit mémoriser la clé RÉELLEMENT en vol (débouncée), pas la frappe courante',
  )
})

test('(exécuté) hors chargement, la valeur mémorisée précédente est conservée telle quelle', () => {
  assert.equal(
    cleEnVolPourChargement(false, '{"kwc":8.52}', '{"kwc":5}'),
    '{"kwc":5}',
    'hors chargement, on ne réécrit pas la clé en vol (elle sert à attribuer une erreur déjà en route)',
  )
})

test('(exécuté) scénario complet : un échec de l’ANCIEN corps ne ferme plus l’attente sur le NOUVEAU', () => {
  // Reproduit le repro exact du Done= : frappe -> échec réseau sur l'ancien
  // corps -> le refus ne doit PAS s'afficher pour le nouveau corps affiché.
  const cleCourante = '{"kwc":8.52}'      // ce que le vendeur voit à l'écran
  const cleDebouncee = '{"kwc":5}'        // le debounce local n'a pas rattrapé
  const cleErreur = cleEnVolPourChargement(true, cleDebouncee, null)
  assert.equal(cleErreur, '{"kwc":5}')
  assert.notEqual(cleErreur, cleCourante, 'AVANT QJR206 : cleEnVol==cleCourante -> refus attribué au corps affiché')
})

// ── (2) câblage : l'effet utilise cleDebouncee, jamais l'ancien patron ──────

test('le hook dérive cleDebouncee via useDebouncedValue (même délai que useEtudeHorairePreview, 500 ms)', () => {
  assert.match(src, /import \{ useDebouncedValue \} from '\.\.\/\.\.\/\.\.\/\.\.\/lib\/debounce'/)
  assert.match(src, /const cleDebouncee = useDebouncedValue\(cleCourante,\s*500\)/)
})

test('l’effet de mémorisation appelle cleEnVolPourChargement(chargement, cleDebouncee, ...), avec cleDebouncee en dépendance', () => {
  assert.match(
    src,
    /cleEnVol\.current = cleEnVolPourChargement\(chargement, cleDebouncee, cleEnVol\.current\)/,
  )
  assert.match(src, /\}, \[chargement, cleDebouncee\]\)/)
})

test('l’ancien patron fautif (mémoriser cleCourante non débouncée) a disparu', () => {
  assert.doesNotMatch(
    src,
    /if \(chargement\) cleEnVol\.current = cleCourante/,
    'régression QJR206 : la clé en vol redevient la clé courante non débouncée',
  )
})
