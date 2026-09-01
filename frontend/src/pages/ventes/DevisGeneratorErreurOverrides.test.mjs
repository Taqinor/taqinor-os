// QJR309 — `messageErreurOverrides` (DevisGenerator.jsx:482, utilisé aux deux
// points de pose `poserOverride`/`regenererOverride`) ne lisait que
// `err.response.data` : le refus CLIENT de la liste blanche levé par
// `ventesApi.poserOverrides` (AVANT tout réseau, `cheminsRefuses` — voir
// `frontend/src/api/ventesApi.js`) est un `TypeError` NU, sans `.response` —
// il retombait donc sur le message générique « La surcharge a été refusée par
// le serveur. », qui maquille un refus CLIENT en refus SERVEUR et jette la
// vraie raison (le chemin fautif).
//
// Correctif : distinguer les deux et afficher la raison réelle pour un refus
// client (le message que `ventesApi.poserOverrides` a déjà construit, avec le
// chemin nommé), tout en laissant le message SERVEUR inchangé, mot pour mot.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules pour son propre rendu React : la partie « source » de ce test
// lit donc le fichier en texte, même patron que DevisGeneratorOverrides.test.mjs.
// `cheminsRefuses`, lui, est une fonction PURE (`features/ventes/quote/
// overrides.js`) : la partie « comportement » importe la VRAIE fonction,
// même TypeError que `ventesApi.poserOverrides` construit réellement.
//
// Run : node --test src/pages/ventes/DevisGeneratorErreurOverrides.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { cheminsRefuses } from '../../features/ventes/quote/overrides.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// Reproduit EXACTEMENT le TypeError construit par `ventesApi.poserOverrides`
// (frontend/src/api/ventesApi.js) — même gabarit de message, mêmes chemins
// refusés calculés par la VRAIE `cheminsRefuses`, jamais une copie locale.
function typeErrorRefusListeBlanche(patch) {
  const refuses = cheminsRefuses(patch)
  if (!refuses.length) return null
  return new TypeError('ventesApi.poserOverrides : chemin(s) '
    + `hors liste blanche du contrat QJR1 — ${refuses.join(', ')}.`)
}

test('QJR309 — messageErreurOverrides distingue le TypeError nu (refus client, sans .response) d’une erreur serveur', () => {
  const idx = DG.indexOf('const messageErreurOverrides = (err) => {')
  assert.ok(idx > -1, 'messageErreurOverrides introuvable')
  const fin = DG.indexOf('\n  }', idx)
  const corps = DG.slice(idx, fin + 4)
  assert.match(
    corps,
    /if \(!err\?\.response && err instanceof TypeError && typeof err\.message === 'string'\) \{\s*\n\s*return err\.message\s*\n\s*\}/,
    'un TypeError sans .response doit rendre son propre message (le refus client), jamais la phrase générique',
  )
})

test('QJR309 — le message affiché pour un refus client NOMME le chemin fautif et ne dit JAMAIS que le serveur a refusé', () => {
  const err = typeErrorRefusListeBlanche({ 'chemin.hors.liste': { valeur: 1 } })
  assert.ok(err instanceof TypeError)
  assert.equal(err.response, undefined)

  // Rejoue le corps réel de messageErreurOverrides (comportement, pas juste
  // source) pour prouver que CE `err`-là produit bien le message attendu.
  const idx = DG.indexOf('const messageErreurOverrides = (err) => {')
  const fin = DG.indexOf('\n  }', idx)
  const corps = DG.slice(DG.indexOf('=> {', idx) + 4, fin)
  // eslint-disable-next-line no-new-func
  const messageErreurOverrides = new Function('err', corps)
  const message = messageErreurOverrides(err)

  assert.match(message, /chemin\(s\)/)
  assert.match(message, /hors liste blanche du contrat QJR1/)
  assert.match(message, /chemin\.hors\.liste/, 'le chemin fautif doit être nommé dans le message affiché')
  assert.doesNotMatch(message, /serveur/i,
    'un refus CLIENT ne doit jamais affirmer que le serveur a refusé la surcharge')
})

test('QJR309 — une vraie erreur serveur (err.response.data) affiche toujours le message du serveur, MOT POUR MOT, comme aujourd’hui', () => {
  const idx = DG.indexOf('const messageErreurOverrides = (err) => {')
  const fin = DG.indexOf('\n  }', idx)
  const corps = DG.slice(DG.indexOf('=> {', idx) + 4, fin)
  // eslint-disable-next-line no-new-func
  const messageErreurOverrides = new Function('err', corps)

  const errServeurDetail = { response: { data: { detail: 'Chemin non dérivable pour ce devis.' } } }
  assert.equal(messageErreurOverrides(errServeurDetail), 'Chemin non dérivable pour ce devis.')

  const errServeurListe = { response: { data: { chemin: ['Valeur hors bornes.'] } } }
  assert.equal(messageErreurOverrides(errServeurListe), 'Valeur hors bornes.')

  // Un TypeError NE DOIT PAS reprendre ce chemin serveur (garde de non-régression :
  // .response est bien vérifié en premier, la nouvelle branche ne l'écrase pas).
  const errServeurTypeError = Object.assign(
    new TypeError('peu importe'),
    { response: { data: { detail: 'Refus serveur réel.' } } },
  )
  assert.equal(messageErreurOverrides(errServeurTypeError), 'Refus serveur réel.')
})

test('QJR309 — les deux points de pose (poserOverride, regenererOverride) continuent d’appeler messageErreurOverrides tel quel', () => {
  const idxPoser = DG.indexOf('const poserOverride = async () => {')
  const blocPoser = DG.slice(idxPoser, idxPoser + 700)
  assert.match(blocPoser, /setOverridesErreur\(messageErreurOverrides\(err\)\)/)
  const idxRegen = DG.indexOf('const regenererOverride = async (chemin) => {')
  const blocRegen = DG.slice(idxRegen, idxRegen + 500)
  assert.match(blocRegen, /setOverridesErreur\(messageErreurOverrides\(err\)\)/)
})
