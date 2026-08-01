// APX3 — Chrome vertical du board leads : 286 -> <=240 px.
// ----------------------------------------------------------------------------
// La MESURE en pixels appartient a la gate e2e APX8 (seul un vrai navigateur
// calcule des hauteurs). Ce fichier verrouille les DEUX invariants qu'aucune
// mesure ne couvre et qu'une reprise de densite casse tres facilement :
//
//   1. le SCOPE — `.kb-board` / `.kb-col*` / `.lp-view-area` sont PARTAGES avec
//      Installations, Planification et Interventions (`.lp-page` sans
//      `data-view`), qui appartiennent a d'autres lanes. Toute regle APX3 doit
//      etre prefixee par le discriminant `[data-view]`, sinon on bouge des
//      pixels chez les voisins sans jamais le voir.
//   2. LB33 — la chaine `:has()` de HAUTEUR reste litteralement en place (on ne
//      touche que des paddings/marges).
//
//   node --test src/pages/crm/leads/LeadsBoardChrome.apx3.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
// Normalisation CRLF : le depot est monte sur Windows, les regex de ce fichier
// raisonnent en \n (sinon elles passent/echouent selon la machine).
const lf = (s) => s.replace(/\r\n/g, '\n')
const CSS = lf(readFileSync(join(HERE, '../../../index.css'), 'utf8'))
const LEADS = lf(readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8'))

const blocApx3 = () => {
  const i = CSS.indexOf('APX3 — REPRENDRE LE CHROME VERTICAL DU BOARD')
  assert.ok(i > -1, 'bloc CSS APX3 introuvable')
  // On repart de l'OUVERTURE du commentaire d'en-tete : sinon le stripper de
  // commentaires ci-dessous verrait un `*/` orphelin et laisserait passer la
  // prose (qui CITE les regles LB33 qu'on affirme ne pas redefinir).
  const debut = CSS.lastIndexOf('/*', i)
  // ... et on s'ARRETE au bandeau du bloc suivant : sinon ce fichier auditerait
  // le CSS des taches d'apres (APX4 et suivantes), qui ont leurs propres
  // regles de scope.
  const suivant = CSS.indexOf('/* ====', i)
  return suivant > -1 ? CSS.slice(debut, suivant) : CSS.slice(debut)
}
/** Le bloc APX3 SANS ses commentaires — les assertions « ne redefinit pas X »
    doivent porter sur les declarations, pas sur la prose qui cite LB33. */
const declarationsApx3 = () => blocApx3().replace(/\/\*[\s\S]*?\*\//g, '')

test('APX3 : le discriminant [data-view] n\'existe QUE sur LeadsPage', () => {
  // C'est CE fait qui rend le scoping sur, et il doit rester vrai.
  assert.match(LEADS, /className=\{`page lp-page\$\{[^`]*\}`\}\s*\n?\s*data-view=\{view\}/)
})

test('APX3 : toute regle du bloc est scopee au board LEADS (jamais aux 3 autres .lp-page)', () => {
  const bloc = blocApx3()
  const selecteurs = []
  for (const ligne of bloc.split('\n')) {
    const t = ligne.trim()
    // Lignes de selecteur : commencent par `.` et se terminent par `{` ou `,`.
    if (/^\.[\w.[\]='"()>\s:-]+[,{]\s*$/.test(t)) selecteurs.push(t)
  }
  assert.ok(selecteurs.length >= 8, `trop peu de selecteurs analyses (${selecteurs.length})`)
  for (const sel of selecteurs) {
    assert.ok(
      sel.includes('[data-view]'),
      `regle APX3 NON scopee au board leads (fuite vers Installations/Planification/Interventions) : ${sel}`,
    )
  }
})

test('APX3 : le shell ne perd QUE son padding HAUT (bas/gauche/droite partages par tout l\'ERP)', () => {
  const bloc = blocApx3()
  assert.match(bloc, /\.layout-content:has\(> \.route-fade > \.lp-page\[data-view\]\) \{\s*\n\s*padding-top: 1rem;\s*\n\s*\}/)
  // Aucune autre propriete de padding n'est touchee sur `.layout-content`.
  const regle = bloc.slice(bloc.indexOf('.layout-content:has('))
  const corps = regle.slice(regle.indexOf('{'), regle.indexOf('}'))
  assert.doesNotMatch(corps, /padding-bottom|padding-left|padding-right|padding:/)
})

test('APX3 : les 4 postes de chrome sont bien repris', () => {
  const bloc = blocApx3()
  assert.match(bloc, /\.lp-page\[data-view\] > \.lp-view-area \{[^}]*margin-top: 0\.25rem;[^}]*padding: 0\.25rem;/s)
  assert.match(bloc, /\.lp-page\[data-view\] \.kb-board \{[^}]*padding: 0\.5rem;/s)
  assert.match(bloc, /\.lp-page\[data-view\] \.kb-col-header \{[^}]*padding: 0\.3rem 0\.55rem 0\.25rem;/s)
})

test('APX3 : la cible tactile du chevron reste >= 44 px malgre la boite retrecie', () => {
  const bloc = blocApx3()
  const coarse = bloc.slice(bloc.indexOf('@media (pointer: coarse)'))
  assert.ok(coarse.length > 0, 'aucune regle (pointer: coarse) dans le bloc APX3')
  const jusqua = coarse.slice(0, 600)
  assert.match(jusqua, /\.lp-page\[data-view\] \.kb-col-collapse-btn::before/)
  assert.match(jusqua, /width: 44px/)
  assert.match(jusqua, /height: 44px/)
})

test('APX3 : LB33 intact — la chaine :has() de HAUTEUR n\'est pas touchee', () => {
  // L'invariant nomme intouchable : le shell borne + la zone de vue extensible.
  assert.match(CSS, /\.layout-content > \.route-fade:has\(> \.lp-page\) \{\s*\n\s*height: 100%;\s*\n\s*\}/)
  assert.match(CSS, /\.lp-page > \.lp-view-area \{\s*\n\s*flex: 1 1 auto;\s*\n\s*min-height: 0;/)
  // APX3 ne redefinit NI height NI flex NI overflow sur cette chaine.
  const decl = declarationsApx3()
  assert.doesNotMatch(decl, /height: 100%/)
  assert.doesNotMatch(decl, /flex: 1 1 auto/)
  assert.doesNotMatch(decl, /overflow/)
})

test('APX3 : aucun hex en dur (tokens semantiques uniquement)', () => {
  assert.doesNotMatch(declarationsApx3(), /#[0-9a-fA-F]{3,8}\b/)
})
