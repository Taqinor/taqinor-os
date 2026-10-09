// Groupe EDC (fondateur 09/10/2026) — gardes SOURCE des blocs CSS de
// l'Édition complète du devis. Le contrat EDC impose UN bloc en FIN
// d'`index.css` par tâche (jamais la réécriture d'une règle existante) : ces
// gardes vérifient que chaque bloc est là, qu'il porte les sélecteurs promis, et
// que les règles d'origine qu'il neutralise sont restées intactes.
// Exécuté en CI : node --test src/pages/ventes/generator/edc.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const lire = (rel) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8')
  .replace(/\r\n/g, '\n')
const cssBrut = lire('../../../index.css')
// Commentaires retirés : ils citent des règles qui piégeraient les regex.
const sansCommentaires = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '')

/** Texte du bloc EDC<n> : de son en-tête jusqu'à l'en-tête suivant (ou la fin). */
function blocEdc(n) {
  const debut = cssBrut.indexOf(`/* ── EDC${n} — `)
  assert.ok(debut >= 0, `le bloc EDC${n} doit exister en fin d'index.css`)
  const suite = cssBrut.indexOf('/* ── EDC', debut + 10)
  return sansCommentaires(cssBrut.slice(debut, suite < 0 ? undefined : suite))
}

test('EDC2 : le plafond 980 px d’origine (LDPQ1) est INTACT — neutralisé, jamais édité', () => {
  assert.match(
    sansCommentaires(cssBrut),
    /\n\.ldp-edit \.gen-embedded \{ max-width: 980px; margin: 0 auto; \}/,
    'la règle d’origine `.ldp-edit .gen-embedded { max-width: 980px; margin: 0 auto; }` doit rester telle quelle',
  )
})

test('EDC2 : le bloc est APRÈS toutes les règles qu’il neutralise (ordre de cascade)', () => {
  const bloc = cssBrut.indexOf('/* ── EDC2 — ')
  assert.ok(bloc > cssBrut.indexOf('.ldp-edit .gen-embedded { max-width: 980px'))
  // Le collage VX16 (`top: var(--header-h, 64px)`, media lg) est AVANT le bloc.
  assert.ok(bloc > cssBrut.indexOf('top: var(--header-h, 64px);'))
})

test('EDC2 : sélecteurs promis — neutralisation, conteneur, rail et total condensé', () => {
  const b = blocEdc(2)
  assert.match(b, /\.ldp-body \.ldp-edit \.gen-embedded \{[^}]*max-width: none;[^}]*margin: 0;/)
  assert.match(b, /\.gen-root \{[^}]*container-type: inline-size;[^}]*container-name: gen;/)
  assert.match(b, /\.gen-root \.gen-summary-rail \{ display: none; \}/)
  const cq = b.slice(b.indexOf('@container gen (min-width: 1200px)'))
  assert.ok(cq.length > 0, 'la container query `@container gen (min-width: 1200px)` doit exister')
  assert.match(cq, /\.gen-root \.gen-summary-rail \{[^}]*display: flex;[^}]*width: 18rem;[^}]*flex-shrink: 0;[^}]*position: sticky;/)
  assert.match(cq, /top: calc\(var\(--header-h, 0px\)[^;]*var\(--gen-barre-h, 0px\)/)
  assert.match(cq, /\.gen-root \.gen-ttc-condense \{ display: none; \}/)
})

test('EDC : aucun bloc EDC ne pose `table-layout: fixed` ni `position: fixed`', () => {
  const tous = cssBrut.slice(cssBrut.indexOf('/* ── EDC'))
  assert.doesNotMatch(sansCommentaires(tous), /table-layout:\s*fixed/)
  assert.doesNotMatch(sansCommentaires(tous), /position:\s*fixed/)
})

test('EDC2 : le rail du générateur ne porte plus aucune classe `lg:` ni de `top` en ligne', () => {
  const gen = lire('../DevisGenerator.jsx')
  const aside = gen.match(/<aside className="[^"]*"[^>]*>/)
  assert.ok(aside, 'le rail <aside> doit exister')
  assert.equal(aside[0], '<aside className="gen-summary-rail">')
  assert.match(gen, /className=\{embedded \? 'gen-root gen-embedded' : 'gen-root page gen-page'\}/)
  assert.match(gen, /className="gen-ttc-condense /)
  assert.doesNotMatch(gen, /lg:hidden/)
})
