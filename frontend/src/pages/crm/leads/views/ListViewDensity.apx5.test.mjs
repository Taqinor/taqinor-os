// APX5 — La vue Liste assume « je vois TOUT » : UNE ligne par lead.
// ----------------------------------------------------------------------------
// Le COMPTAGE (>=18 lignes visibles en 1440x900, preference compacte)
// appartient a la gate e2e APX8. Ce fichier verrouille les invariants qui le
// rendent possible et qu'une future edition casserait sans bruit :
//   - la cellule Lead tient sur UNE rangee (sinon la hauteur de ligne redevient
//     fonction du contenu : deux lignes voisines de hauteurs differentes) ;
//   - la hauteur vient du jeton de densite PARTAGE (--row-py), jamais d'un
//     padding fige ;
//   - la frontiere de lanes est respectee : `.data-table` (APX34) et
//     `densityOverride` (NTUX17) ne sont pas touches.
//   node --test src/pages/crm/leads/views/ListViewDensity.apx5.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const SRC = lf(readFileSync(join(HERE, 'ListView.jsx'), 'utf8'))
const CSS = lf(readFileSync(join(HERE, '../../../../index.css'), 'utf8'))
const TOKENS = lf(readFileSync(join(HERE, '../../../../design/tokens.css'), 'utf8'))
const SWITCHER = lf(readFileSync(join(HERE, '../ViewSwitcher.jsx'), 'utf8'))

const bloc = () => {
  const i = CSS.indexOf('APX5 — LA VUE LISTE ASSUME')
  assert.ok(i > -1, 'bloc CSS APX5 introuvable')
  const debut = CSS.lastIndexOf('/*', i)
  const suivant = CSS.indexOf('/* ====', i)
  return suivant > -1 ? CSS.slice(debut, suivant) : CSS.slice(debut)
}
const celluleLead = () => {
  const start = SRC.indexOf('<td data-label="Lead"')
  const end = SRC.indexOf('<td data-label="Stade"', start)
  assert.ok(end > start, 'cellule Lead introuvable')
  return SRC.slice(start, end)
}

test('APX5 : la hauteur de ligne vient du jeton de densite PARTAGE, plus d\'un padding fige', () => {
  const b = bloc()
  assert.match(b, /\.lv-table td \{\s*\n\s*padding: var\(--row-py\) 12px;\s*\n\s*\}/)
  assert.match(b, /\.lv-table th \{\s*\n\s*padding: var\(--row-py\) 12px;\s*\n\s*\}/)
  // Le jeton existe dans LES DEUX densites (sinon la regle serait morte).
  assert.match(TOKENS, /\[data-density='compact'\] \{[^}]*--row-py: 0\.375rem;/s)
  assert.match(TOKENS, /--row-py: 0\.625rem;/)
})

test('APX5 : FRONTIERE — `.data-table` (APX34) et `densityOverride` (NTUX17) ne sont pas touches', () => {
  const b = bloc().replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(b, /\.data-table/)
  assert.doesNotMatch(b, /densityOverride/)
  // Le <table> porte bien les DEUX classes : c'est precisement pour cela que
  // la regle doit viser `.lv-table` et jamais `.data-table`.
  assert.match(SRC, /className="data-table lv-table calm-list"/)
})

test('APX5 : la cellule Lead tient sur UNE rangee (nom · societe · archive · contacts)', () => {
  const b = bloc()
  assert.match(b, /\.lv-lead-cell \{\s*\n\s*flex-direction: row;/)
  assert.match(b, /flex-wrap: nowrap;/)
  const cell = celluleLead()
  assert.match(cell, /className="lv-lead-name"/)
  assert.match(cell, /className="lv-lead-societe"/)
  assert.match(cell, /className="lv-lead-archived-by"/)
  assert.match(cell, /className="lv-lead-contact"/)
})

test('APX5 : nom et societe tronquent au lieu de passer a la ligne', () => {
  const b = bloc()
  for (const sel of ['.lv-lead-cell .lv-lead-name', '.lv-lead-cell .lv-lead-societe']) {
    const i = b.indexOf(`${sel} {`)
    assert.ok(i > -1, `regle ${sel} absente`)
    const regle = b.slice(i, b.indexOf('}', i))
    assert.match(regle, /white-space: nowrap/)
    assert.match(regle, /text-overflow: ellipsis/)
    assert.match(regle, /overflow: hidden/)
  }
})

test('APX5 : rien n\'est perdu — « Archive » condense en pastille garde son detail en infobulle', () => {
  const cell = celluleLead()
  // VX243(a) : QUI a archive et QUAND restent lisibles, dans le title.
  assert.match(cell, /title=\{`Archivé\$\{lead\.archived_by_nom \? ` par \$\{lead\.archived_by_nom\}` : ''\}/)
  assert.match(cell, /\$\{lead\.archived_at \? ` le \$\{formatDate\(lead\.archived_at\)\}` : ''\}`\}/)
  // La condition de rendu est inchangee (silencieux sur un lead vivant).
  assert.match(cell, /\{lead\.is_archived && \(lead\.archived_by_nom \|\| lead\.archived_at\) && \(/)
})

test('APX5 : les icones de contact (QX25) sont poussees a droite par la FEUILLE DE STYLE', () => {
  // Le style inline qui les empilait sous le nom (`marginTop: 2px`) a disparu :
  // une seule source de mise en page.
  assert.doesNotMatch(celluleLead(), /marginTop: '2px'/)
  assert.match(bloc(), /\.lv-lead-contact \{[^}]*margin-left: auto;/s)
})

test('APX5 : le repli mobile (cartes empilees) garde sa mise en COLONNE', () => {
  const b = bloc()
  const i = b.indexOf('@media (max-width: 768px)')
  assert.ok(i > -1, 'repli mobile absent du bloc APX5')
  assert.match(b.slice(i), /\.lv-lead-cell \{\s*\n\s*flex-direction: column;/)
})

test('APX5 : l\'infobulle du ViewSwitcher annonce la vue la plus dense', () => {
  assert.match(SWITCHER, /hint: 'la vue la plus dense'/)
  // ... sans jamais devenir un second libelle : elle DERIVE du nom accessible.
  assert.match(SWITCHER, /title: hint \? `\$\{label\} — \$\{hint\}` : label,/)
  assert.match(SWITCHER, /\{ value: 'liste', label: 'Vue liste'/)
})

test('APX5 : aucun hex en dur (tokens semantiques uniquement)', () => {
  assert.doesNotMatch(bloc().replace(/\/\*[\s\S]*?\*\//g, ''), /#[0-9a-fA-F]{3,8}\b/)
})
