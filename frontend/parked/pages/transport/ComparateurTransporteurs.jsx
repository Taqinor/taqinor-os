// NTLOG7 — Comparateur de coûts d'affrètement : pour un ordre de transport
// en attente d'affrètement, liste les transporteurs actifs triés par prix
// (tarif de référence) croissant, avec un bouton « Affecter ce
// transporteur » qui pose `installations_transporteur_id` sur l'ordre.
//
// Composant RÉUTILISABLE (prend `ordreId` en prop) — pas encore raccordé à
// une route/écran détail d'ordre de transport (hors périmètre de cette
// tâche ; Files: `frontend/src/pages/transport/` seulement).
import { useCallback } from 'react'

import api from '../../api/axios'
import useResource from '../../hooks/useResource'
import { Badge, Button, Card, EmptyState, Spinner } from '../../ui'
import { formatMAD } from '../../lib/format'

export default function ComparateurTransporteurs({ ordreId, onAffecte }) {
  const { data, loading, error, refetch } = useResource(
    () => api.get(`/transport/ordres-transport/${ordreId}/comparer-transporteurs/`),
    ordreId,
    { initialData: [], select: (res) => res.data, enabled: !!ordreId },
  )

  const affecter = useCallback(
    async (transporteurId) => {
      await api.patch(`/transport/ordres-transport/${ordreId}/`, {
        mode_transport: 'affretement',
        installations_transporteur_id: transporteurId,
      })
      await refetch()
      onAffecte?.(transporteurId)
    },
    [ordreId, refetch, onAffecte],
  )

  if (!ordreId) return null
  if (loading) return <Spinner />
  if (error) {
    return (
      <Card className="p-4 text-sm text-red-600">{error}</Card>
    )
  }
  if (!data?.length) {
    return (
      <EmptyState
        title="Aucun transporteur"
        description="Aucun transporteur actif couvrant cette destination pour le moment."
      />
    )
  }

  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-muted-foreground">
            <th className="p-3 font-medium">Transporteur</th>
            <th className="p-3 font-medium">Type</th>
            <th className="p-3 font-medium">Contact</th>
            <th className="p-3 font-medium text-right">Prix indicatif</th>
            <th className="p-3" />
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.transporteur_id} className="border-b last:border-0">
              <td className="p-3 font-medium">{row.nom}</td>
              <td className="p-3">
                <Badge tone="outline">{row.type_transporteur}</Badge>
              </td>
              <td className="p-3 text-muted-foreground">
                {row.contact || row.telephone || '—'}
              </td>
              <td className="p-3 text-right tabular-nums">
                {formatMAD(row.prix_applicable)}
              </td>
              <td className="p-3 text-right">
                <Button
                  size="sm"
                  onClick={() => affecter(row.transporteur_id)}
                >
                  Affecter ce transporteur
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  )
}
