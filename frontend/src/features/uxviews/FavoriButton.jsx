// NTUX12 — Bouton « épingler » (icône étoile) générique, à déposer sur
// N'IMPORTE QUEL écran de détail (Lead, Devis, Client, Chantier, Ticket…) :
//   <FavoriButton modele="installations.installation" objectId={chantier.id} />
// Aucune dépendance à l'app appelante (contenttype résolu côté serveur depuis
// `modele`, cf. `FavoriUtilisateurSerializer.validate_modele`) — le composant
// reste dans `features/uxviews/` (transverse) et n'importe RIEN d'une app
// métier, satisfaisant la frontière inter-apps même côté frontend.
import { useState } from 'react'
import { Star } from 'lucide-react'
import { Button } from '../../ui'
import { toast } from '../../ui/confirm'
import { useFavoris } from './useFavoris'

export default function FavoriButton({ modele, objectId, size = 'icon', className }) {
  const { loading, isFavori, toggle } = useFavoris()
  const [busy, setBusy] = useState(false)

  if (!modele || objectId == null) return null

  const pinned = isFavori(modele, objectId)
  const label = pinned ? 'Retirer des favoris' : 'Épingler aux favoris'

  const onClick = () => {
    setBusy(true)
    toggle(modele, objectId)
      .catch((err) => {
        const detail = err?.response?.data?.detail
        toast.error(detail || (pinned ? 'Impossible de retirer ce favori.' : "Impossible d'épingler cet élément."))
      })
      .finally(() => setBusy(false))
  }

  return (
    <Button
      type="button"
      size={size}
      variant="ghost"
      className={className}
      loading={busy}
      disabled={loading}
      aria-pressed={pinned}
      title={label}
      onClick={onClick}
    >
      <Star className="size-4" fill={pinned ? 'currentColor' : 'none'} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </Button>
  )
}
