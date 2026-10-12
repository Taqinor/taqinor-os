// ENF28 (ENF19) — colonne « Supprimer » partagée des listes de reporting
// (classeurs, configurations de tableau de bord) : bouton icône poubelle en fin
// de ligne. Un seul exemplaire au lieu de deux copies.
import { Trash2 } from 'lucide-react'
import { IconButton } from '../../ui'

export function colonneSupprimer(onRemove, width = 100) {
  return {
    id: 'actions', header: '', width, align: 'right',
    accessor: () => '',
    cell: (v, r) => (
      <IconButton variant="ghost" label="Supprimer" onClick={() => onRemove(r)}>
        <Trash2 />
      </IconButton>
    ),
  }
}
