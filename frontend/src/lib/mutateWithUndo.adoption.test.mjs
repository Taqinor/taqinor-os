// EZ14 — Verrous de SOURCE : la liste d'adoption committee + le « zero undo sur
// l'argent » (le comportement lui-meme est couvert par mutateWithUndo.test.jsx).
//   node --test src/lib/mutateWithUndo.adoption.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const lire = (p) => lf(readFileSync(join(HERE, p), 'utf8'))

const UTIL = lire('mutateWithUndo.js')
const TOAST = lire('toast.js')
const LISTE = lire('../pages/crm/leads/views/ListView.jsx')
const KANBAN = lire('../pages/crm/leads/views/KanbanView.jsx')
const SHOWCASE = lire('../pages/ui/UIShowcase.jsx')

/* LA LISTE D'ADOPTION COMMITTEE (>= 6 mutations, exigee par la tache).
   Chaque entree : [fichier, genre, ce que l'utilisateur fait]. */
const ADOPTION = [
  ['ListView', 'lead_archive', 'archiver un lead'],
  ['ListView', 'lead_archive', 'restaurer un lead'],
  ['ListView', 'lead_stage', "changer l'etape en place"],
  ['ListView', 'lead_priorite', 'changer la priorite en place'],
  ['ListView', 'lead_tags', 'changer les etiquettes en place'],
  ['ListView', 'lead_relance', 'changer la date de relance en place'],
  ['KanbanView', 'lead_owner', 'reassigner depuis une carte'],
  ['KanbanView', 'lead_stage', "changer l'etape au clavier (StageMover)"],
]

test('EZ14 : au moins 6 mutations sont passees a l\'undo (liste committee)', () => {
  assert.ok(ADOPTION.length >= 6, `seulement ${ADOPTION.length} adoptions`)
  const genres = new Set(ADOPTION.map(([, g]) => g))
  for (const g of genres) {
    assert.match(UTIL, new RegExp(`^\\s*${g}:`, 'm'), `genre ${g} absent du registre`)
  }
})

test('EZ14 : les adoptions sont REELLEMENT cablees dans les deux vues', () => {
  assert.match(LISTE, /import \{ mutateWithUndo \} from '\.\.\/\.\.\/\.\.\/\.\.\/lib\/mutateWithUndo'/)
  assert.match(KANBAN, /import \{ mutateWithUndo \} from '\.\.\/\.\.\/\.\.\/\.\.\/lib\/mutateWithUndo'/)
  // Liste : archivage / restauration + les 4 champs en place.
  assert.match(LISTE, /kind: 'lead_archive',\s*\n\s*message: 'Lead archivé\.'/)
  assert.match(LISTE, /kind: 'lead_archive',\s*\n\s*message: 'Lead restauré\.'/)
  for (const champ of ['stage', 'priorite', 'tags', 'relance_date']) {
    assert.match(LISTE, new RegExp(`^\\s*${champ}: \\{ kind: 'lead_`, 'm'), `champ ${champ} absent de CHAMPS_UNDO`)
  }
  assert.match(LISTE, /onInlineSave=\{inlineSaveAvecUndo\}/)
  // Kanban : reassignation + etape.
  assert.match(KANBAN, /kind: 'lead_owner'/)
  assert.match(KANBAN, /kind: 'lead_stage'/)
  assert.match(KANBAN, /onReassign=\{reassignAvecUndo\}/)
  assert.match(KANBAN, /onInlineSave=\{inlineSaveAvecUndo\}/)
})

test('EZ14 : ZERO undo sur l\'argent — le grep du registre', () => {
  const registre = UTIL.slice(UTIL.indexOf('export const UNDO_REGISTRY'), UTIL.indexOf('const INTERDIT'))
  const cles = [...registre.matchAll(/^\s{2}(\w+):/gm)].map((m) => m[1])
  assert.ok(cles.length >= 6)
  for (const c of cles) {
    assert.doesNotMatch(
      c,
      /devis|facture|montant|prix|paiement|total|remise|tva|delete|suppression|envoi|email|whatsapp|pdf/i,
      `genre d'argent/envoi dans le registre : ${c}`,
    )
  }
  // Le champ `facture_hiver` (un montant) reste DELIBEREMENT hors undo : il
  // n'apparait pas dans la table des champs qui gagnent l'annulation.
  const i = LISTE.indexOf('const CHAMPS_UNDO')
  const table = LISTE.slice(i, LISTE.indexOf('}', i))
  assert.doesNotMatch(table, /facture_hiver/)
  assert.doesNotMatch(table, /montant|prix|total/i)
})

test('EZ14 : la suppression garde son motif propre (corbeille), pas l\'undo generique', () => {
  // `onDelete` reste sur toastWithUndo sans onCommit + restauration corbeille :
  // c'est une reversibilite SERVEUR (30 min), pas un inverse client.
  const suppr = LISTE.slice(LISTE.indexOf('const onDelete = useCallback'))
  assert.match(suppr.slice(0, 1400), /restaurerCorbeille/)
  assert.doesNotMatch(suppr.slice(0, 1400), /mutateWithUndo/)
})

test('EZ14 : le piege du commit differe est DOCUMENTE a la source', () => {
  assert.match(TOAST, /COMMIT DIFFÉRÉ/)
  assert.match(TOAST, /lib\/mutateWithUndo\.js/)
  // Et l'util ne le reproduit jamais : aucun setTimeout, aucun onCommit dans
  // le CODE (la prose, elle, cite legitimement le piege qu'elle decrit).
  const code = UTIL.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '')
  assert.doesNotMatch(code, /setTimeout/)
  assert.doesNotMatch(code, /onCommit/)
})

test('EZ14 : la doctrine est PUBLIEE dans /ui, et lue depuis le code', () => {
  assert.match(SHOWCASE, /import \{ UNDO_KINDS, UNDO_REGISTRY, UNDO_DURATION_MS \} from '\.\.\/\.\.\/lib\/mutateWithUndo'/)
  assert.match(SHOWCASE, /Annuler ou confirmer/)
  assert.match(SHOWCASE, /\{UNDO_KINDS\.map\(\(k\) => \(/)
  // Les trois interdits sont nommes noir sur blanc.
  assert.match(SHOWCASE, /suppressions dures/)
  assert.match(SHOWCASE, /Un envoi ne se/)
  assert.match(SHOWCASE, /argent/)
})

test('EZ14 : l\'effet sur le chatter est documente (2e ligne, jamais un effacement)', () => {
  assert.match(UTIL, /SECONDE\s*\n?\s*\/\/ ligne d'historique|seconde\s+ligne d'historique|SECONDE/i)
  assert.match(SHOWCASE, /seconde<\/strong> ligne d’historique/)
})
