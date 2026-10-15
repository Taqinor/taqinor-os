import { X } from 'lucide-react'

/* Pastille de facette de filtre actif (dimension + valeur) avec sa croix de
   retrait. `facette` : { key, dim, label } ; `onRetirer` remet le filtre à
   vide. Un seul endroit pour la barre de filtres et la rangée de facettes. */
export default function FacetteFiltre({ facette, onRetirer }) {
  return (
    <span className="fb-facet">
      <span className="fb-facet-dim">{facette.dim}</span>
      <span className="fb-facet-val">{facette.label}</span>
      <button
        type="button"
        className="fb-facet-x"
        aria-label={`Retirer le filtre ${facette.dim} : ${facette.label}`}
        onClick={onRetirer}
      ><X aria-hidden="true" /></button>
    </span>
  )
}
