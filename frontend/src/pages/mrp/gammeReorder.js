// NTMFG27 — algorithme de réordonnancement pur pour l'Assistant de création
// de gamme (AssistantCreationGamme.jsx). Extrait dans ce fichier voisin car
// un fichier composant ne doit exporter QUE son composant
// (react-refresh/only-export-components) — testable sans simuler un vrai
// geste de glisser-déposer (jsdom ne prête pas aux pointer events de dnd-kit).

// Déplace l'élément `fromIndex` à `toIndex`, renvoie un NOUVEAU tableau
// (jamais de mutation en place).
export function moveItem(list, fromIndex, toIndex) {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0
      || fromIndex >= list.length || toIndex >= list.length) {
    return list
  }
  const copie = list.slice()
  const [item] = copie.splice(fromIndex, 1)
  copie.splice(toIndex, 0, item)
  return copie
}
