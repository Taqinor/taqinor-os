import { KeyboardCode, closestCenter } from '@dnd-kit/core'

/* ============================================================================
   R2-063 — Outils communs du RÉORDONNANCEMENT des tâches d'une étape (vue Liste et vue Tableau d'un projet) avec
   `@dnd-kit/core` : ce qui se glisse est une tâche (`useDraggable`), ce qui reçoit est une autre tâche de la MÊME
   étape (`useDroppable`, `data.etape`). Le glissé ne parle jamais au serveur : l'écran écrit (`reordonnerTache`,
   liste « projet »), met à jour sur place et annule.
   ========================================================================== */

/** La clé d'étape d'une tâche (`null` : « Sans étape ») : une même chaîne pour les deux vues. */
export const cleEtape = (sectionId) => (sectionId == null ? 'sans' : String(sectionId))

/** Détection : parmi les tâches de la MÊME étape que celle qu'on glisse (elle-même comprise : lâcher sans bouger ne change rien). */
export function detecterDansEtape(args) {
  const etape = args.active?.data?.current?.etape
  const conteneurs = args.droppableContainers.filter((c) => c.data?.current?.etape === etape)
  return closestCenter({ ...args, droppableContainers: conteneurs })
}

/** Clavier : ↑/↓ sautent à la tâche voisine de la même étape (la tâche saisie se pose à sa place). */
export function coordonneesVerticales(event, { context: { active, droppableRects, droppableContainers, collisionRect } }) {
  const bas = event.code === KeyboardCode.Down
  const haut = event.code === KeyboardCode.Up
  if (!active || !collisionRect || (!bas && !haut)) return undefined
  event.preventDefault()
  const etape = active.data?.current?.etape
  const voisines = droppableContainers.getEnabled()
    .filter((c) => c.data?.current?.etape === etape)
    .map((c) => ({ id: c.id, rect: droppableRects.get(c.id) }))
    .filter((c) => c.rect)
    .sort((a, b) => a.rect.top - b.rect.top)
  if (voisines.length === 0) return undefined
  const milieu = collisionRect.top + collisionRect.height / 2
  let ici = voisines.findIndex((c) => milieu >= c.rect.top && milieu <= c.rect.top + c.rect.height)
  if (ici < 0) ici = 0
  const cible = voisines[Math.max(0, Math.min(voisines.length - 1, ici + (bas ? 1 : -1)))]
  return { x: collisionRect.left, y: cible.rect.top }
}
