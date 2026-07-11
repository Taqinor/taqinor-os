// VX192 — accessibilité clavier PARTAGÉE des 3 kanbans (leads CRM, chantiers
// installations, tâches gestion de projet). Un seul helper d'annonces FR pour
// le lecteur d'écran + les instructions clavier, branché sur le
// `accessibility` de `<DndContext>` (@dnd-kit/core). Chaque kanban passe une
// fonction `labelFor(id)` qui traduit un id d'entité / de colonne en libellé
// humain (référence, nom du lead, libellé d'étape…), de sorte que les
// annonces restent en français et parlantes quel que soit le module.
//
// Complète — ne remplace pas — l'alternative <select> déjà offerte sous chaque
// carte (StageMover/StatutMover) : au clavier seul on peut soit changer
// l'étape via le sélecteur, soit saisir/déplacer/déposer une carte au clavier
// avec ces annonces.

// Instructions lues au focus d'un élément déplaçable (fr).
export const kanbanScreenReaderInstructions = {
  draggable:
    'Pour déplacer une carte au clavier : appuyez sur Espace ou Entrée pour '
    + 'la saisir, les flèches pour la déplacer entre les colonnes, Espace ou '
    + 'Entrée pour la déposer, Échap pour annuler.',
}

/**
 * Construit l'objet `announcements` FR de @dnd-kit à partir d'un traducteur
 * d'id → libellé. `labelFor` reçoit l'id d'un draggable ou d'un droppable et
 * renvoie une chaîne lisible (à défaut, l'id brut).
 */
export function buildKanbanAnnouncements(labelFor = (id) => String(id)) {
  const label = (id) => (id == null ? '' : labelFor(id))
  return {
    onDragStart({ active }) {
      return `Carte ${label(active.id)} saisie.`
    },
    onDragOver({ active, over }) {
      if (over) {
        return `Carte ${label(active.id)} déplacée sur la colonne `
          + `${label(over.id)}.`
      }
      return `Carte ${label(active.id)} n'est plus sur une colonne.`
    },
    onDragEnd({ active, over }) {
      if (over) {
        return `Carte ${label(active.id)} déposée dans la colonne `
          + `${label(over.id)}.`
      }
      return `Carte ${label(active.id)} reposée à sa place.`
    },
    onDragCancel({ active }) {
      return `Déplacement de la carte ${label(active.id)} annulé.`
    },
  }
}
