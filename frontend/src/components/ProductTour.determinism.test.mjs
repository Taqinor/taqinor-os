// L-FRONT (lot 4, 24/08) — ProductTour.test.jsx est un test vitest flaky connu
// (2 PR flakés) : la cause trouvée est le `queueMicrotask(() => { setActiveKey
// /setStep/setOpen })` de l'effet de déclenchement automatique
// (ProductTour.jsx) — un aller-retour microtask INUTILE, hors du flush
// react-dom synchrone que `act()`/`fireEvent`/`render` couvrent déjà pour un
// effet « normal » (voir Avatar.jsx/FollowToggle.jsx/WelcomeMoment.jsx… —
// TOUS utilisent un simple `// eslint-disable-next-line
// react-hooks/set-state-in-effect`, jamais un queueMicrotask). Empilé sur la
// promesse déjà async de `fetchTours()`, cet aller-retour supplémentaire
// pouvait faire dépasser le budget par défaut de `findByText`/`waitFor` sous
// charge CI — ProductTour.jsx n'est pas exécutable sous `node --test` (JSX,
// react-dom, react-router) : ce test lit donc le SOURCE, même patron que
// DevisGeneratorEtudeHoraire.test.mjs.
//
// Run : node --test src/components/ProductTour.determinism.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PT = readFileSync(join(HERE, 'ProductTour.jsx'), 'utf8')

test('ProductTour : aucun appel à queueMicrotask() — plus d\'aller-retour microtask artificiel dans l\'effet de déclenchement', () => {
  // Le mot "queueMicrotask" reste cité en commentaire (pourquoi ce patron a
  // été retiré) — c'est l'APPEL (la parenthèse ouvrante) qui doit avoir
  // disparu.
  assert.ok(!/queueMicrotask\(/.test(PT),
    'un appel à queueMicrotask() réintroduirait le retard artificiel qui rendait ProductTour.test.jsx flaky sous charge CI')
})

test('ProductTour : setActiveKey/setStep/setOpen posés SYNCHRONEMENT dans l\'effet [tour, pathname] (même patron que le reste du dépôt)', () => {
  const idx = PT.indexOf('const eligible = toursActifs && Boolean(tour) && !tour.vu && isNewUser(user)')
  assert.ok(idx > -1, "le calcul d'éligibilité est introuvable")
  const bloc = PT.slice(idx, idx + 1600)
  assert.match(bloc, /setActiveKey\(eligible \? tour\.tour_key : null\)/)
  assert.match(bloc, /setStep\(0\)/)
  assert.match(bloc, /setOpen\(eligible\)/)
  // Les 3 lignes doivent être des appels DIRECTS (pas enveloppés dans un
  // callback différé) : aucune parenthèse ouvrante `(() =>` entre le calcul
  // d'éligibilité et le dernier `setOpen`.
  const findByText = bloc.indexOf('setOpen(eligible)')
  const entreDeux = bloc.slice(0, findByText)
  assert.doesNotMatch(entreDeux, /\(\(\)\s*=>/,
    'un callback différé (queueMicrotask/setTimeout/Promise.resolve().then) réintroduirait le même aller-retour microtask')
  assert.doesNotMatch(entreDeux, /setTimeout/)
  assert.doesNotMatch(entreDeux, /Promise\.resolve\(\)\.then/)
})

test('ProductTour : le lint react-hooks/set-state-in-effect reste explicitement couvert (même convention que le reste du dépôt)', () => {
  const occurrences = (PT.match(/react-hooks\/set-state-in-effect/g) || []).length
  assert.ok(occurrences >= 3,
    'chacun des 3 setState synchrones (activeKey/step/open) doit porter son propre eslint-disable, comme Avatar.jsx/FollowToggle.jsx')
})
