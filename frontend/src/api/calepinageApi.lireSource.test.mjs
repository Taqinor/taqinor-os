import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { lireSourceCalepinageApi } from './calepinage/lireSource.mjs'
import { extraireCles } from './calepinageApi.usage.test.mjs'

/* ============================================================================
   SPL292 — `lireSourceCalepinageApi()` recompose la façade et ses fragments.
   ----------------------------------------------------------------------------
   Sans ce lecteur, une clé déplacée dans `api/calepinage/<theme>.js` sortirait
   silencieusement des gardes de SOURCE (`calepinageApi.test.mjs`,
   `calepinageApi.usage.test.mjs`) : faux vert. On le prouve sur un arbre
   TEMPORAIRE (jamais sur le dépôt), puis on vérifie le dépôt réel.
   ========================================================================== */

const here = dirname(fileURLToPath(import.meta.url))

const FACADE = [
  "import api from './axios'",
  "import { fragment } from './calepinage/fragment'",
  '',
  'const calepinageApi = {',
  '  calepinages: {',
  "    layout: (id) => api.get(`/calepinage/calepinages/${id}/layout/`),",
  '    ...fragment,',
  '  },',
  '  moteur: {',
  "    calculer: (corps) => api.post('/calepinage/moteur/calculer/', corps),",
  '  },',
  '}',
  '',
  'export default calepinageApi',
  '',
].join('\n')

const FRAGMENT = [
  "import api from '../axios'",
  "import { pivot } from './_base'",
  '',
  'export const fragment = {',
  '    // CALX1 — première clé déplacée.',
  '    sorties: (id) => api.get(`${pivot(id)}sorties/`),',
  '    archiver: (id) =>',
  '      api.post(`${pivot(id)}archiver/`),',
  '}',
  '',
].join('\n')

const BASE = 'export const pivot = (id) => `/calepinage/calepinages/${id}/`\n'

function arbre(avecFragment) {
  const racine = mkdtempSync(join(tmpdir(), 'spl292-'))
  mkdirSync(join(racine, 'calepinage'))
  writeFileSync(join(racine, 'calepinageApi.js'), FACADE)
  writeFileSync(join(racine, 'calepinage', '_base.js'), BASE)
  if (avecFragment) writeFileSync(join(racine, 'calepinage', 'fragment.js'), FRAGMENT)
  return racine
}

function cles(code) {
  return extraireCles(code).map((c) => `${c.namespace}.${c.cle}`).sort()
}

test('SPL292 — un fragment de 2 clés est spliçé dans `calepinages` à la place de `...fragment,`', () => {
  const racine = arbre(true)
  try {
    // Rouge AVANT lireSource : la façade seule ne porte pas les 2 clés.
    assert.deepEqual(cles(readFileSync(join(racine, 'calepinageApi.js'), 'utf8')),
      ['calepinages.layout', 'moteur.calculer'])
    const texte = lireSourceCalepinageApi(racine)
    assert.deepEqual(cles(texte),
      ['calepinages.archiver', 'calepinages.layout', 'calepinages.sorties', 'moteur.calculer'])
    // Le corps est inséré VERBATIM, commentaire compris, et `_base.js` suit.
    assert.match(texte, / {4}\/\/ CALX1 — première clé déplacée\.\n {4}sorties:/)
    assert.ok(texte.endsWith(BASE))
    assert.doesNotMatch(texte, /\.\.\.fragment,/)
  } finally {
    rmSync(racine, { recursive: true, force: true })
  }
})

test('SPL292 — sans fichier de fragment, la ligne de spread reste telle quelle', () => {
  const racine = arbre(false)
  try {
    const texte = lireSourceCalepinageApi(racine)
    assert.equal(texte, `${FACADE}\n${BASE}`)
  } finally {
    rmSync(racine, { recursive: true, force: true })
  }
})

test('SPL292 — dépôt réel : façade + `_base.js`, 94 clés, la racine `pivot` est lisible', () => {
  const facade = readFileSync(join(here, 'calepinageApi.js'), 'utf8')
  const base = readFileSync(join(here, 'calepinage', '_base.js'), 'utf8')
  const texte = lireSourceCalepinageApi()
  assert.equal(texte, `${facade}\n${base}`)
  assert.equal(extraireCles(texte).length, 94)
  assert.match(texte, /const pivot = \(id\) => `\/calepinage\/calepinages\/\$\{id\}\/`/)
  // Aucun jumeau : `pivot` n'est plus DÉFINI dans la façade.
  assert.doesNotMatch(facade, /const pivot =/)
})
