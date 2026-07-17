import { useEffect, useState } from 'react'
import { Card, Badge, Button, EmptyState, Spinner } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT9 — Housekeeping mobile : tâches de ménage de la femme/homme de
   chambre connecté(e). Grandes cibles tactiles ; bouton « Marquer terminé »
   repasse la chambre à ``libre`` côté serveur (services.terminer_tache_menage).
   Lecture scopée : le backend filtre déjà aux tâches assignées à l'utilisateur
   (sauf Responsable/Admin, qui voient tout).
   ========================================================================== */

export default function Menage() {
  const [taches, setTaches] = useState(null)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    hospitalityApi
      .listTachesMenage({ statut: 'a_faire' })
      .then((res) => setTaches(res.data?.results ?? res.data ?? []))
      .catch(() => setError('Tâches de ménage indisponibles.'))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const terminer = (id) => {
    setBusyId(id)
    hospitalityApi
      .terminerTacheMenage(id)
      .then(() => setTaches((prev) => prev.filter((t) => t.id !== id)))
      .catch(() => setError('Impossible de marquer cette tâche terminée.'))
      .finally(() => setBusyId(null))
  }

  if (error) {
    return <EmptyState title="Housekeeping indisponible" description={error} />
  }
  if (!taches) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement de mes tâches…
      </div>
    )
  }
  if (!taches.length) {
    return (
      <EmptyState
        title="Aucune tâche à faire"
        description="Toutes vos chambres assignées sont à jour."
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {taches.map((tache) => (
        <Card key={tache.id} className="flex items-center justify-between gap-4 p-4">
          <div className="flex flex-col gap-1">
            <div className="text-lg font-semibold">
              Chambre {tache.chambre_numero}
            </div>
            <Badge tone="info">{tache.type_tache_display}</Badge>
          </div>
          <Button
            size="lg"
            disabled={busyId === tache.id}
            onClick={() => terminer(tache.id)}
          >
            {busyId === tache.id ? <Spinner className="size-4" /> : 'Marquer terminé'}
          </Button>
        </Card>
      ))}
    </div>
  )
}
