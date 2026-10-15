/* « Charger plus (N restant[s]) » d'une colonne de vue Kanban/Prévision. */
export default function BoutonChargerPlus({ restants, onClick }) {
  if (!(restants > 0)) return null
  return (
    <button type="button" className="kb-charger-plus" onClick={onClick}>
      Charger plus ({restants} restant{restants > 1 ? 's' : ''})
    </button>
  )
}
