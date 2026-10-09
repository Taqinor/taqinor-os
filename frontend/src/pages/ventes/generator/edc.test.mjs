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

test('EDC4 : barre d’actions collante au palier --z-sticky, repli de hauteur 3.25rem', () => {
  const b = blocEdc(4)
  assert.match(b, /\.gen-root \{ --gen-barre-h: 3\.25rem; \}/)
  assert.match(b, /\.gen-barre-actions \{[^}]*position: sticky;[^}]*top: calc\(var\(--header-h, 0px\) \+ var\(--gen-colle-decalage, 0px\)\);[^}]*z-index: var\(--z-sticky\);/)
  // Jamais au-dessus des popovers Radix : aucun palier overlay/modal/popover.
  assert.doesNotMatch(b, /\.gen-barre-actions \{[^}]*z-index: var\(--z-(overlay|modal|popover)/)
  // La barre de progression VX136 colle au même haut que la barre.
  assert.match(b, /\.gen-root > \.scroll-progress-bar \{[^}]*top: calc\(var\(--header-h, 0px\) \+ var\(--gen-colle-decalage, 0px\)\);/)
})

test('EDC4 : la barre est rendue HORS du formulaire et son Enregistrer vise form="gen-form"', () => {
  const gen = lire('../DevisGenerator.jsx')
  const barre = gen.indexOf('<BarreActionsDevis')
  assert.ok(barre > 0, 'la barre doit être montée par le générateur')
  assert.ok(barre < gen.indexOf('<form id="gen-form"'), 'la barre précède le formulaire, hors de lui')
  const composant = lire('./BarreActionsDevis.jsx')
  assert.match(composant, /type="submit" form=\{formId\}/)
  assert.match(composant, /formId = 'gen-form'/)
  assert.match(composant, /role="toolbar"/)
  assert.match(composant, /aria-label="Actions du devis"/)
})

/** Corps d'un bloc `@media (<requête>) { … }` du texte donné (accolades appariées). */
function blocMedia(texte, requete) {
  const debut = texte.indexOf(`@media (${requete})`)
  assert.ok(debut >= 0, `@media (${requete}) attendu`)
  let profondeur = 0
  for (let i = texte.indexOf('{', debut); i < texte.length; i++) {
    if (texte[i] === '{') profondeur++
    else if (texte[i] === '}') {
      profondeur--
      if (profondeur === 0) return texte.slice(debut, i + 1)
    }
  }
  return assert.fail(`@media (${requete}) non refermé`)
}

test('EDC3 : barre proxy à piste visible, barre native masquée quand la table déborde', () => {
  const b = blocEdc(3)
  assert.match(b, /\.bdc-wrap \{ overflow-x: auto; \}/)
  assert.match(b, /\.bdc-wrap\[data-deborde="true"\] \{ scrollbar-width: none; \}/)
  assert.match(b, /\.bdc-wrap\[data-deborde="true"\]::-webkit-scrollbar \{ display: none; \}/)
  assert.match(b, /\.bdc-proxy \{[^}]*overflow-x: auto;[^}]*scrollbar-width: auto;/)
  assert.match(b, /\.bdc-proxy::-webkit-scrollbar \{ height: 14px; \}/)
  // Paliers locaux dérivés du barème (garde MB3 : aucun z-index en dur).
  assert.doesNotMatch(b, /z-index:\s*\d/)
})

test('EDC3 : en-tête collant et `separate` sur BUREAU seulement — empilement mobile intact', () => {
  const b = blocEdc(3)
  const bureau = blocMedia(b, 'min-width: 769px')
  assert.match(bureau, /\.lines-table-wrap\.bdc-wrap\[data-deborde="false"\] \{ overflow: visible; \}/)
  assert.match(bureau, /\.lines-table\.lines-table-separe \{[^}]*border-collapse: separate;[^}]*border-spacing: 0;/)
  assert.match(bureau, /\.lines-thead-collant th \{[^}]*position: sticky;[^}]*top: var\(--gen-colle-top, 0px\);[^}]*z-index: calc\(var\(--z-base\) \+ 2\);/)
  // Hors de la requête bureau, aucune règle du bloc ne touche la table, son
  // en-tête ou son modèle de bordures (l'empilement mobile reste celui d'origine).
  const horsBureau = b.replace(bureau, '')
  assert.doesNotMatch(horsBureau, /\.lines-table(?!-wrap)[^{]*\{/)
  assert.doesNotMatch(horsBureau, /border-collapse/)
  // Mobile : le conteneur des lignes reste `overflow: visible` (règle mobile
  // d'origine ré-affirmée après `.bdc-wrap`) et sans barre proxy.
  const mobile = blocMedia(b, 'max-width: 768px')
  assert.match(mobile, /\.lines-table-wrap\.bdc-wrap \{ overflow: visible; \}/)
  assert.match(mobile, /\.lines-table-wrap \+ \.bdc-proxy \{ display: none; \}/)
  // La règle mobile d'origine est toujours là, intacte.
  assert.match(sansCommentaires(cssBrut), /\n {2}\.lines-table-wrap \{ overflow: visible; \}\n {2}\.lines-table thead \{ display: none; \}/)
})

test('EDC3 : les trois tableaux d’étude horaire passent par la barre collante (plus d’overflowX en ligne)', () => {
  const gen = lire('../DevisGenerator.jsx')
  assert.doesNotMatch(gen, /overflowX: 'auto'/)
  assert.equal((gen.match(/<BarreDefilementCollante[\s>]/g) || []).length, 3)
  const table = lire('./LigneTable.jsx')
  assert.match(table, /<BarreDefilementCollante className="lines-table-wrap">/)
  assert.match(table, /<table className="lines-table lines-table-separe" ref=\{linesTableRef\}>/)
  assert.match(table, /<thead className="lines-thead-collant">/)
  const index = lire('../../../ui/index.js')
  assert.match(index.trimEnd().split('\n').at(-1), /^export \* from '\.\/BarreDefilementCollante'$/)
})

test('EDC9 : navigation collée sous la barre d’actions, cartes atteintes sous la barre', () => {
  const b = blocEdc(9)
  assert.match(b, /\.gen-nav-sections \{[^}]*position: sticky;[^}]*top: calc\(var\(--header-h, 0px\) \+ var\(--gen-colle-decalage, 0px\) \+ var\(--gen-barre-h, 0px\)\);/)
  assert.match(b, /\.gen-root \[id\^="gen-sec-"\] \{ scroll-margin-top: calc\(var\(--gen-barre-h, 0px\) \+ 3\.5rem\); \}/)
  assert.match(b, /\.gen-nav-puce\[aria-current="true"\] \{/)
  // Mouvement réduit : aucune transition sur les puces ni sur le chevron.
  assert.match(b, /@media \(prefers-reduced-motion: reduce\) \{[^}]*\.gen-nav-puce,\s*\.gen-carte-repli-icone \{ transition: none; \}/)
  assert.doesNotMatch(b, /z-index:\s*\d/)
})

test('EDC9 : ancres de section posées sur les cartes, jamais sur l’argent', () => {
  const gen = lire('../DevisGenerator.jsx')
  for (const [id, libelle] of [
    ['gen-sec-document', 'Document'], ['gen-sec-lead', 'Lead & Client'],
    ['gen-sec-technique', 'Technique'], ['gen-sec-simulation', 'Simulation'],
    ['gen-sec-lignes', 'Lignes'], ['gen-sec-echeancier', 'Échéancier'],
    ['gen-sec-texte', 'Texte client'], ['gen-sec-enregistrer', 'Enregistrement'],
  ]) {
    assert.match(gen, new RegExp(`id="${id}" data-nav-libelle="${libelle}"`), id)
  }
  // Lignes / échéancier : jamais repliables (NN/g) — seules Simulation et
  // Surcharges portent `repliable`.
  assert.equal((gen.match(/\n\s*repliable[\s=]/g) || []).length, 2)
  assert.match(gen, /<NavigationSections \/>/)
})
