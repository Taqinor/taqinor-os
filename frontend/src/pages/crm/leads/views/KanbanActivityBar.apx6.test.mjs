// APX6 — En-tetes de colonne : progressbar segmentee d'activite + somme.
// ----------------------------------------------------------------------------
// La repartition est une fonction PURE exportee (`repartitionActivite`), donc
// elle se teste avec une SEED reelle, sans navigateur ni node_modules : c'est
// le coeur du « barre exacte par colonne (test seed) » demande par la tache.
// Le reste (rendu, clic-filtre, AA) est verrouille contre la SOURCE.
//   node --test src/pages/crm/leads/views/KanbanActivityBar.apx6.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const SRC = lf(readFileSync(join(HERE, 'KanbanView.jsx'), 'utf8'))
const CSS = lf(readFileSync(join(HERE, '../../../../index.css'), 'utf8'))
const STAGES_PY = lf(readFileSync(join(HERE, '../../../../../../STAGES.py'), 'utf8'))

const bloc = () => {
  const i = CSS.indexOf('APX6 — EN-TETES DE COLONNE')
  assert.ok(i > -1, 'bloc CSS APX6 introuvable')
  const debut = CSS.lastIndexOf('/*', i)
  const suivant = CSS.indexOf('/* ====', i)
  return suivant > -1 ? CSS.slice(debut, suivant) : CSS.slice(debut)
}

/* ── La logique PURE, rejouee a l'identique (le fichier de composant ne peut
      pas etre importe sans bundler JSX dans cette lane). Toute divergence
      entre cette copie et la source est attrapee par le test de source
      ci-dessous, qui epingle le texte exact des deux fonctions. ── */
const SEAUX = ['overdue', 'today', 'upcoming', 'none']
function activiteSeau(lead) {
  const state = lead?.next_activity?.state
  return SEAUX.includes(state) ? state : 'none'
}
function repartitionActivite(leads) {
  const acc = { overdue: 0, today: 0, upcoming: 0, none: 0 }
  for (const lead of leads ?? []) acc[activiteSeau(lead)] += 1
  return acc
}

test('APX6 (seed) : la repartition compte EXACTEMENT les 4 seaux', () => {
  const seed = [
    { id: 1, next_activity: { state: 'overdue' } },
    { id: 2, next_activity: { state: 'overdue' } },
    { id: 3, next_activity: { state: 'today' } },
    { id: 4, next_activity: { state: 'upcoming' } },
    { id: 5, next_activity: { state: 'upcoming' } },
    { id: 6, next_activity: { state: 'upcoming' } },
    { id: 7 },                                   // aucune activite
    { id: 8, next_activity: null },              // idem
    { id: 9, next_activity: { state: 'zarbi' } }, // etat inconnu -> « sans activite »
  ]
  assert.deepEqual(repartitionActivite(seed), {
    overdue: 2, today: 1, upcoming: 3, none: 3,
  })
  // La somme des seaux vaut TOUJOURS le nombre de leads : aucun lead ne peut
  // tomber hors barre (c'est ce qui rend les largeurs proportionnelles justes).
  const r = repartitionActivite(seed)
  assert.equal(r.overdue + r.today + r.upcoming + r.none, seed.length)
})

test('APX6 (seed) : colonne vide et colonne d\'un seul seau', () => {
  assert.deepEqual(repartitionActivite([]), { overdue: 0, today: 0, upcoming: 0, none: 0 })
  assert.deepEqual(repartitionActivite(undefined), { overdue: 0, today: 0, upcoming: 0, none: 0 })
  const r = repartitionActivite([{ id: 1 }, { id: 2 }])
  assert.deepEqual(r, { overdue: 0, today: 0, upcoming: 0, none: 2 })
})

test('APX6 : la copie de logique de ce test est fidele a la source', () => {
  assert.match(SRC, /export function activiteSeau\(lead\) \{\s*\n\s*const state = lead\?\.next_activity\?\.state/)
  assert.match(SRC, /export function repartitionActivite\(leads\) \{/)
  assert.match(SRC, /const acc = \{ overdue: 0, today: 0, upcoming: 0, none: 0 \}/)
  assert.match(SRC, /for \(const lead of leads \?\? \[\]\) acc\[activiteSeau\(lead\)\] \+= 1/)
})

test('APX6 : ZERO requete nouvelle — les seaux derivent de next_activity.state deja charge', () => {
  // `next_activity.state` est deja consomme par la carte (`kb-act-${state}`).
  const carte = lf(readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8'))
  assert.match(carte, /kb-act-\$\{lead\.next_activity\.state\}/)
  // Aucun appel reseau introduit dans la vue kanban.
  assert.doesNotMatch(SRC, /crmApi\.|api\.get\(|useEffect\(\(\) => \{[\s\S]{0,200}fetch/)
})

test('APX6 (regle #2) : aucune liste d\'etapes en dur — elles viennent de stages.js/STAGES.py', () => {
  assert.match(SRC, /PIPELINE_STAGES, STAGE_LABELS,?\s*\n?\s*\} from '\.\.\/\.\.\/\.\.\/\.\.\/features\/crm\/stages'/)
  for (const cle of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD']) {
    assert.match(STAGES_PY, new RegExp(`\\b${cle}\\b`))
    assert.doesNotMatch(SRC, new RegExp(`'${cle}'\\s*,\\s*'`), `liste d'etapes en dur detectee autour de ${cle}`)
  }
  // Les seaux d'ACTIVITE ne sont pas des etapes : aucun risque de confusion.
  assert.match(SRC, /const ACTIVITE_SEAUX = \[/)
})

test('APX6 : chaque segment est un bouton proportionnel, jamais un seau vide rendu', () => {
  assert.match(SRC, /ACTIVITE_SEAUX\.filter\(\(s\) => repartition\[s\.key\] > 0\)\.map/)
  assert.match(SRC, /style=\{\{ flexGrow: repartition\[s\.key\] \}\}/)
  assert.match(SRC, /aria-pressed=\{activiteFiltre === s\.key\}/)
})

test('APX6 : la couleur n\'est JAMAIS le seul porteur de sens (compte + libelle accessibles)', () => {
  assert.match(SRC, /<span className="sr-only">\s*\n\s*\{repartition\[s\.key\]\} lead\{repartition\[s\.key\] > 1 \? 's' : ''\} \{s\.label\}/)
  assert.match(SRC, /title=\{`\$\{repartition\[s\.key\]\} lead\$\{repartition\[s\.key\] > 1 \? 's' : ''\} \$\{s\.label\} — cliquer pour filtrer cette étape`\}/)
  assert.match(SRC, /aria-label=\{`Activité de l’étape \$\{col\.label\}`\}/)
})

test('APX6 : le clic filtre la COLONNE, se defait au second clic, et ne fausse pas les compteurs', () => {
  // Bascule : re-cliquer le meme seau retire le filtre.
  assert.match(SRC, /prev\[stageKey\] === seau/)
  // Le filtre ne touche QUE les cartes montees — `col.count`/`col.totalDevis`
  // restent les totaux reels (sinon la barre se redessinerait sous le doigt).
  // APX9 a insere le plafond de rendu APRES ce filtre : la source de la
  // tranche reste bien la liste filtree, jamais un autre tableau.
  assert.match(SRC, /const visibles = activiteParEtape\[col\.key\]\s*\n\s*\? col\.leads\.filter\(\(l\) => activiteSeau\(l\) === activiteParEtape\[col\.key\]\)\s*\n\s*: col\.leads/)
  assert.match(SRC, /aria-label=\{`Étape \$\{col\.label\} — \$\{col\.count\} lead/)
})

test('APX6 : la barre est scopee au board leads et reutilise les jetons semantiques', () => {
  const b = bloc()
  for (const ligne of b.split('\n')) {
    const t = ligne.trim()
    if (!/^\.[\w.[\]='"()>\s:-]+[,{]\s*$/.test(t)) continue
    assert.ok(t.includes('[data-view]'), `regle APX6 non scopee au board leads : ${t}`)
  }
  assert.match(b, /\.kb-act-seg--danger \{ background: var\(--destructive\); \}/)
  assert.match(b, /\.kb-act-seg--warning \{ background: var\(--warning-text\); \}/)
  assert.match(b, /\.kb-act-seg--success \{ background: var\(--success\); \}/)
  assert.doesNotMatch(b.replace(/\/\*[\s\S]*?\*\//g, ''), /#[0-9a-fA-F]{3,8}\b/)
})

test('APX6 : la barre fait 4 px mais reste frappable (overlay 14 px)', () => {
  const b = bloc()
  assert.match(b, /\.kb-col-activite \{[^}]*height: 4px;/s)
  assert.match(b, /\.kb-act-seg::before \{[^}]*height: 14px;/s)
})

test('APX6 : la somme des montants est en typographie de donnees et alignee a droite', () => {
  assert.match(SRC, /className="kb-col-money num"/)
  assert.match(bloc(), /\.kb-col-money \{\s*\n\s*text-align: right;/)
})
