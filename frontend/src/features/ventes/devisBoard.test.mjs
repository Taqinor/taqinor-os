// QJR205 — Le Kanban ventes affiche le MÊME prix que la liste.
//   `DevisKanbanBoard.jsx` rendait `d.total_ttc` et `devisBoard.js` sommait
//   `Number(d.total_ttc)` pour l'en-tête de colonne, pendant que
//   `DevisList.jsx` rend `d.total_affiche ?? d.total_ttc` — deux champs
//   produits par deux chaînes différentes pour le même devis sur deux écrans
//   de la même application. Échange de lecture de champ SEULEMENT, aucune
//   arithmétique nouvelle côté écran.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { devisBoardColumns } from './devisBoard.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const kanbanSrc = readFileSync(
  path.join(__dirname, '..', '..', 'pages', 'ventes', 'DevisKanbanBoard.jsx'),
  'utf8',
)

// Fixture : un devis à deux options où `total_affiche` (option 1, la seule
// qui doit compter — jamais la somme des deux) diverge de `total_ttc`.
const DEVIS_DEUX_OPTIONS = {
  id: 42,
  statut: 'envoye',
  reference: 'DV-2026-0099',
  client_nom: 'Client Test',
  total_ttc: 220000, // somme des deux options, valeur historique du champ
  total_affiche: 120000, // total réel de l'option 1 — ce que la liste montre
}

test('(exécuté) devisBoardColumns totalise la colonne sur total_affiche, jamais total_ttc seul', () => {
  const cols = devisBoardColumns([DEVIS_DEUX_OPTIONS])
  const envoye = cols.find(c => c.key === 'envoye')
  assert.equal(envoye.total, 120000, 'le total de colonne doit être le total_affiche (option 1), pas total_ttc')
  assert.notEqual(envoye.total, 220000, 'ne doit plus additionner total_ttc seul (bug avant QJR205)')
})

test('(exécuté) sans total_affiche, le repli sur total_ttc reste vert (comportement historique préservé)', () => {
  const cols = devisBoardColumns([{ id: 1, statut: 'brouillon', total_ttc: 5000 }])
  assert.equal(cols.find(c => c.key === 'brouillon').total, 5000)
})

test('la carte Kanban lit le même champ que la vue liste (total_affiche ?? total_ttc)', () => {
  // Avant QJR205 : `d.total_ttc != null ? formatMAD(d.total_ttc) : '—'` —
  // la carte n'aurait jamais lu total_affiche. On vérifie l'expression
  // exacte utilisée par DevisList.jsx pour le même devis (grep de parité,
  // pas une régression réintroduite par un futur refactor du champ).
  assert.match(kanbanSrc, /d\.total_affiche\s*\?\?\s*d\.total_ttc/, 'la carte doit lire total_affiche ?? total_ttc, comme DevisList.jsx')
  assert.doesNotMatch(
    kanbanSrc,
    /\{d\.total_ttc\s*!=\s*null\s*\?\s*formatMAD\(d\.total_ttc\)\s*:\s*'—'\}/,
    'ancienne lecture directe de total_ttc réintroduite',
  )
})
