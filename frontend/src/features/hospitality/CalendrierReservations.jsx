import { useEffect, useState } from 'react'
import { Card, Badge, EmptyState, Spinner } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT3 — Calendrier réservations (vue planning hôtelier, une ligne/chambre).
   ----------------------------------------------------------------------------
   Liste les chambres en lignes et les réservations à venir en badges par
   chambre (fenêtre de lecture simple ; le glisser-déposer complet est NTHOT21,
   hors périmètre ici). Lecture scopée société côté serveur.
   ========================================================================== */

const STATUT_TONE = {
  confirmee: 'success',
  en_attente: 'warning',
  annulee: 'danger',
  no_show: 'danger',
  en_cours: 'info',
  terminee: 'neutral',
}

export default function CalendrierReservations() {
  const [chambres, setChambres] = useState(null)
  const [reservations, setReservations] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([hospitalityApi.listChambres(), hospitalityApi.listReservations()])
      .then(([resChambres, resReservations]) => {
        setChambres(resChambres.data?.results ?? resChambres.data ?? [])
        setReservations(resReservations.data?.results ?? resReservations.data ?? [])
      })
      .catch(() => setError('Calendrier des réservations indisponible.'))
  }, [])

  if (error) {
    return <EmptyState title="Calendrier indisponible" description={error} />
  }
  if (!chambres || !reservations) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement du calendrier…
      </div>
    )
  }
  if (!chambres.length) {
    return (
      <EmptyState
        title="Aucune chambre"
        description="Créez des chambres pour afficher le calendrier des réservations."
      />
    )
  }

  const reservationsParChambre = (chambreId) =>
    reservations.filter((r) => r.chambre === chambreId)

  return (
    <div className="flex flex-col gap-2">
      {chambres.map((chambre) => {
        const items = reservationsParChambre(chambre.id)
        return (
          <Card key={chambre.id} className="flex flex-wrap items-center gap-3 p-3">
            <div className="w-28 shrink-0 font-semibold">
              {chambre.nom || chambre.numero}
            </div>
            {items.length === 0 ? (
              <span className="text-sm text-muted-foreground">
                Aucune réservation à venir.
              </span>
            ) : (
              items.map((r) => (
                <Badge key={r.id} tone={STATUT_TONE[r.statut] || 'neutral'}>
                  {r.date_arrivee} → {r.date_depart}
                  {r.client_nom ? ` · ${r.client_nom}` : ''}
                </Badge>
              ))
            )}
          </Card>
        )
      })}
    </div>
  )
}
