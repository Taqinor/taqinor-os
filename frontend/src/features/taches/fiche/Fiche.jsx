/* TCH43 — point de montage de la fiche d'une tâche (`?tache=<id>`), VIDE à dessein :
   la coquille l'ouvre déjà, TCH84 y construit Quand · Échéance · Projet · Priorité, ★,
   notes et check-list (TCH85 : Plus). Rien de visible tant que ce n'est pas construit —
   le module est invisible jusqu'à l'activation (TCH131). */
export default function Fiche({ id }) {
  return <div className="sr" data-fiche={id} role="presentation" />
}
