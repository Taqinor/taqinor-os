// ENF28 (ENF19) — en-tête de carte des listes du portail : le contenu à gauche,
// le badge de statut à droite (livraisons client, commissions partenaire).
// Un seul exemplaire au lieu de deux copies.
import { Badge } from '../../ui'

export default function EnteteCarteStatut({ ton, libelle, children }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div>{children}</div>
      <Badge tone={ton || 'neutral'}>
        {libelle}
      </Badge>
    </div>
  )
}
