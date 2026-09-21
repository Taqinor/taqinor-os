// GED — helpers PURS (sans React) pour l'arborescence documentaire.
//
// Le backend renvoie une LISTE PLATE de dossiers (`apps/ged`), chacun portant
// `id`, `parent` (id du parent ou null), `cabinet`, `nom` et un chemin
// matérialisé `path` (ex. "/1/4/9/"). On reconstruit ici l'arbre côté client
// pour le navigateur arborescent — logique testable, jamais d'appel réseau.

// Construit un arbre imbriqué à partir d'une liste plate de dossiers.
// Renvoie les nœuds RACINES (parent null/absent), chacun augmenté d'un tableau
// `children` (lui-même trié récursivement). Les enfants sont triés par nom
// (locale FR, insensible à la casse) puis par id pour un ordre stable —
// identique à l'ordre `Meta.ordering = ['nom', 'id']` du modèle Folder.
// Robuste aux entrées invalides (null/undefined → []) et aux parents manquants
// (un dossier dont le parent n'est pas dans la liste est traité comme racine,
// jamais perdu).
export function buildFolderTree(folders) {
  const list = Array.isArray(folders) ? folders.filter(Boolean) : []
  const byId = new Map()
  for (const f of list) {
    byId.set(f.id, { ...f, children: [] })
  }
  const roots = []
  for (const f of list) {
    const node = byId.get(f.id)
    const parent = f.parent != null ? byId.get(f.parent) : null
    if (parent && parent !== node) {
      parent.children.push(node)
    } else {
      // Racine, ou parent introuvable/auto-référence → rattaché à la racine
      // (jamais orphelin).
      roots.push(node)
    }
  }
  const sortNodes = (nodes) => {
    nodes.sort((a, b) => {
      const c = String(a.nom ?? '').localeCompare(String(b.nom ?? ''), 'fr', {
        sensitivity: 'base',
      })
      if (c !== 0) return c
      return (a.id ?? 0) - (b.id ?? 0)
    })
    for (const n of nodes) sortNodes(n.children)
    return nodes
  }
  return sortNodes(roots)
}

// Aplatit l'arbre en une liste ordonnée (DFS pré-ordre) en n'incluant QUE les
// branches dépliées : un nœud apparaît toujours, ses enfants seulement si son
// id est dans `expanded` (un Set). Chaque entrée porte une `depth` (0 = racine)
// et `hasChildren` pour le rendu en lignes indentées avec chevron. Sert à
// transformer l'arbre en lignes plates faciles à afficher.
export function flattenVisible(tree, expanded) {
  const open = expanded instanceof Set ? expanded : new Set(expanded ?? [])
  const out = []
  const walk = (nodes, depth) => {
    for (const node of nodes ?? []) {
      const children = node.children ?? []
      const hasChildren = children.length > 0
      out.push({ ...node, depth, hasChildren })
      if (hasChildren && open.has(node.id)) {
        walk(children, depth + 1)
      }
    }
  }
  walk(tree, 0)
  return out
}

// Renvoie l'ensemble (Set) des ids des dossiers ANCÊTRES d'un dossier cible,
// déduit du chemin matérialisé "/1/4/9/" (les pk des ancêtres puis soi). Sert à
// déplier automatiquement la branche menant à un dossier sélectionné. L'id du
// dossier lui-même est INCLUS (utile pour le déplier s'il a des enfants).
export function ancestorIdsFromPath(path) {
  if (!path || typeof path !== 'string') return new Set()
  return new Set(
    path
      .split('/')
      .filter((s) => s !== '')
      .map((s) => Number(s))
      .filter((n) => Number.isFinite(n)),
  )
}

// Compte total des dossiers d'un arbre (tous niveaux confondus). Pratique pour
// un libellé de synthèse (« N dossiers »).
export function countFolders(tree) {
  let n = 0
  const walk = (nodes) => {
    for (const node of nodes ?? []) {
      n += 1
      walk(node.children)
    }
  }
  walk(tree)
  return n
}
