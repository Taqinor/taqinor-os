import { useEffect, useState } from 'react'
import { Card, Badge, EmptyState, Spinner } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT1 — Plan des chambres/unités.
   ----------------------------------------------------------------------------
   Grille des chambres de l'établissement avec badge statut coloré. Lecture
   scopée société côté serveur (TenantMixin) ; filtre optionnel par statut.
   ========================================================================== */

const STATUT_TONE = {
  libre: 'success',
  occupee: 'info',
  sale: 'warning',
  en_nettoyage: 'warning',
  hors_service: 'danger',
}

export default function PlanChambres() {
  const [chambres, setChambres] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statutFiltre, setStatutFiltre] = useState('')

  const load = (statut) => {
    setLoading(true)
    setError(null)
    hospitalityApi
      .listChambres(statut ? { statut } : undefined)
      .then((res) => setChambres(res.data?.results ?? res.data ?? []))
      .catch(() => setError('Plan des chambres indisponible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load(statutFiltre)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statutFiltre])

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement du plan des chambres…
      </div>
    )
  }
  if (error) {
    return <EmptyState title="Plan des chambres indisponible" description={error} />
  }
  if (!chambres?.length) {
    return (
      <EmptyState
        title="Aucune chambre"
        description="Créez un type de chambre puis une chambre pour démarrer."
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2 text-sm">
        {['', 'libre', 'occupee', 'sale', 'en_nettoyage', 'hors_service'].map((s) => (
          <button
            key={s || 'tous'}
            type="button"
            onClick={() => setStatutFiltre(s)}
            className={
              'rounded-full border px-3 py-1 ' +
              (statutFiltre === s ? 'bg-primary/15 border-primary' : 'border-border')
            }
          >
            {s || 'Tous'}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {chambres.map((c) => (
          <Card key={c.id} className="flex flex-col gap-1 p-3">
            <div className="text-base font-semibold">{c.nom || c.numero}</div>
            <div className="text-xs text-muted-foreground">
              {c.type_chambre_libelle}
              {c.etage ? ` · Étage ${c.etage}` : ''}
            </div>
            <Badge tone={STATUT_TONE[c.statut] || 'neutral'}>
              {c.statut_display || c.statut}
            </Badge>
          </Card>
        ))}
      </div>
    </div>
  )
}
