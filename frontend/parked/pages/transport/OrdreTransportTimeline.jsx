// NTLOG8 — Timeline chronologique d'un ordre de transport : chaque
// changement de statut (de l'ordre OU d'une étape) et chaque note manuelle
// apparaissent horodatés, via le chatter générique `records.Activity`
// (`ChatterViewSetMixin`, endpoints `chatter/historique` / `chatter/noter`
// — jamais un nouveau modèle `*Activity` maison, ARC8).
//
// Réutilise le composant `ChatterTimeline` partagé (VX23) plutôt que de
// réinventer le regroupement par jour / les libellés de note/modification.
//
// Composant RÉUTILISABLE (prend `ordreId` en prop) — pas encore raccordé à
// une route/écran détail d'ordre de transport (hors périmètre de cette
// tâche ; Files: `frontend/src/pages/transport/` seulement).
import { useCallback, useState } from 'react'

import api from '../../api/axios'
import useResource from '../../hooks/useResource'
import ChatterTimeline from '../../components/ChatterTimeline'
import { Button, Spinner, Textarea } from '../../ui'

export default function OrdreTransportTimeline({ ordreId }) {
  const [note, setNote] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const { data, loading, error, refetch } = useResource(
    () => api.get(`/transport/ordres-transport/${ordreId}/chatter/historique/`),
    ordreId,
    { initialData: [], select: (res) => res.data, enabled: !!ordreId },
  )

  const envoyerNote = useCallback(async () => {
    const body = note.trim()
    if (!body) return
    setEnvoi(true)
    try {
      await api.post(`/transport/ordres-transport/${ordreId}/chatter/noter/`, { body })
      setNote('')
      await refetch()
    } finally {
      setEnvoi(false)
    }
  }, [note, ordreId, refetch])

  if (!ordreId) return null

  // `ChatterActivitySerializer` renvoie `user_username` — `ChatterTimeline`
  // (composant générique VX23) lit `user_nom` : simple alias, pas de nouveau
  // composant.
  const entries = (data ?? []).map((e) => ({ ...e, user_nom: e.user_username }))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
          rows={2}
          className="flex-1"
        />
        <Button onClick={envoyerNote} loading={envoi} disabled={!note.trim()}>
          Noter
        </Button>
      </div>
      {loading && <Spinner />}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && !error && (
        <ChatterTimeline
          entries={entries}
          emptyLabel="Aucun événement pour le moment."
        />
      )}
    </div>
  )
}
