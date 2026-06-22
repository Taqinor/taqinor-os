import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildFolderTree,
  flattenVisible,
  ancestorIdsFromPath,
  countFolders,
} from './tree.js'

// Jeu d'essai : une liste plate de dossiers comme la renvoie l'API ged.
//   Racine A (1)
//     ├─ A2 (3)
//     └─ A1 (2)
//   Racine B (4)
const FLAT = [
  { id: 1, parent: null, nom: 'Racine A', path: '/1/' },
  { id: 2, parent: 1, nom: 'A1', path: '/1/2/' },
  { id: 3, parent: 1, nom: 'A2', path: '/1/3/' },
  { id: 4, parent: null, nom: 'Racine B', path: '/4/' },
]

test('buildFolderTree imbrique les enfants sous leur parent', () => {
  const tree = buildFolderTree(FLAT)
  assert.equal(tree.length, 2) // deux racines
  assert.deepEqual(tree.map((n) => n.nom), ['Racine A', 'Racine B'])
  const a = tree[0]
  assert.equal(a.children.length, 2)
  // Tri par nom : A1 avant A2 (alphabétique, pas l'ordre d'insertion).
  assert.deepEqual(a.children.map((n) => n.nom), ['A1', 'A2'])
  assert.equal(tree[1].children.length, 0) // Racine B est une feuille
})

test('buildFolderTree : entrée vide / invalide → []', () => {
  assert.deepEqual(buildFolderTree(null), [])
  assert.deepEqual(buildFolderTree(undefined), [])
  assert.deepEqual(buildFolderTree([]), [])
  // Les nœuds falsy sont ignorés sans planter.
  assert.equal(buildFolderTree([null, { id: 9, parent: null, nom: 'X' }]).length, 1)
})

test('buildFolderTree : parent introuvable → traité comme racine (jamais perdu)', () => {
  const tree = buildFolderTree([
    { id: 5, parent: 999, nom: 'Orphelin' }, // parent absent de la liste
  ])
  assert.equal(tree.length, 1)
  assert.equal(tree[0].nom, 'Orphelin')
})

test('flattenVisible : seules les branches dépliées apparaissent', () => {
  const tree = buildFolderTree(FLAT)
  // Rien déplié : seules les deux racines.
  const collapsed = flattenVisible(tree, new Set())
  assert.deepEqual(collapsed.map((n) => n.nom), ['Racine A', 'Racine B'])
  assert.equal(collapsed[0].depth, 0)
  assert.equal(collapsed[0].hasChildren, true)
  assert.equal(collapsed[1].hasChildren, false) // Racine B = feuille

  // Racine A dépliée : ses deux enfants apparaissent, indentés (depth 1).
  const open = flattenVisible(tree, new Set([1]))
  assert.deepEqual(open.map((n) => n.nom), ['Racine A', 'A1', 'A2', 'Racine B'])
  assert.deepEqual(open.map((n) => n.depth), [0, 1, 1, 0])
})

test('flattenVisible accepte un tableau d\'ids déplié comme un Set', () => {
  const tree = buildFolderTree(FLAT)
  const rows = flattenVisible(tree, [1])
  assert.deepEqual(rows.map((n) => n.nom), ['Racine A', 'A1', 'A2', 'Racine B'])
})

test('ancestorIdsFromPath : extrait les ids du chemin matérialisé', () => {
  assert.deepEqual([...ancestorIdsFromPath('/1/4/9/')].sort((a, b) => a - b), [1, 4, 9])
  assert.deepEqual([...ancestorIdsFromPath('/')], [])
  assert.deepEqual([...ancestorIdsFromPath('')], [])
  assert.deepEqual([...ancestorIdsFromPath(null)], [])
})

test('countFolders compte tous les niveaux', () => {
  assert.equal(countFolders(buildFolderTree(FLAT)), 4)
  assert.equal(countFolders([]), 0)
})
