// NTUX21 — annonces FR + instructions clavier PARTAGÉES pour le
// glisser-déposer d'une liste À PLAT (favoris épinglés, vues personnelles) —
// `@dnd-kit/core` SEUL, même patron que `pages/home/HomeMenu.jsx` (ODY13) :
// `@dnd-kit/sortable` n'est PAS installé et reste interdit (NE PAS FAIRE VX).
// Distinct de `features/kanban/kanbanA11y.js` (cartes ENTRE colonnes) : ici
// une seule liste, « position de » plutôt que « colonne ».
export const dndListScreenReaderInstructions = {
  draggable:
    'Appuyez sur Entrée ou Espace sur la poignée pour commencer à déplacer '
    + 'cet élément. Utilisez les flèches pour choisir sa nouvelle position, '
    + 'Entrée ou Espace pour déposer, Échap pour annuler.',
}

/**
 * Construit l'objet `announcements` FR de @dnd-kit à partir d'un traducteur
 * d'id → libellé (`labelFor`).
 */
export function buildDndListAnnouncements(labelFor = (id) => String(id)) {
  const label = (id) => (id == null ? '' : labelFor(id))
  return {
    onDragStart: ({ active }) => `Déplacement de ${label(active.id)} commencé.`,
    onDragOver: ({ active, over }) => (over
      ? `${label(active.id)} sera placé à la position de ${label(over.id)}.`
      : `${label(active.id)} n'est au-dessus d'aucune position valide.`),
    onDragEnd: ({ active, over }) => (over
      ? `${label(active.id)} déposé à la position de ${label(over.id)}.`
      : `${label(active.id)} reposé à sa place.`),
    onDragCancel: ({ active }) => `Déplacement de ${label(active.id)} annulé.`,
  }
}

/**
 * Nouvel ordre d'une liste À PLAT après un `onDragEnd` de @dnd-kit/core
 * (`{active, over}`), par ids. `ids` = ordre ACTUEL (avant déplacement).
 * Renvoie `null` si rien ne doit bouger (pas de cible, ou déjà en place).
 */
export function reorderIds(ids, { active, over }) {
  if (!over || over.id === active.id) return null
  const next = [...ids]
  const depuis = next.indexOf(active.id)
  const vers = next.indexOf(over.id)
  if (depuis < 0 || vers < 0) return null
  const [deplace] = next.splice(depuis, 1)
  next.splice(vers, 0, deplace)
  return next
}
