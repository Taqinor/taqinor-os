import { useMemo, useState } from 'react'
import { Truck } from 'lucide-react'

import api from '../../api/axios'
import useResource from '../../hooks/useResource'
import { Badge, Card, CardContent, CardHeader, CardTitle, Segmented, Tabs, TabsContent, TabsList, TabsTrigger } from '../../ui'
import { ListShell } from '../../ui/module'
import ComparateurTransporteurs from '../../pages/transport/ComparateurTransporteurs'
import OrdreTransportTimeline from '../../pages/transport/OrdreTransportTimeline'

/* ============================================================================
   NTLOG7/NTLOG8 — Écran `/transport/ordres` : liste des ordres de transport.
   ----------------------------------------------------------------------------
   Coquille de liste UX1 (colonnes numéro/statut/mode/poids, filtre statut).
   Le clic sur une ligne ouvre un panneau de détail sous le tableau — deux
   onglets qui montent les composants déjà livrés par NTLOG7 (comparateur
   d'affrètement) et NTLOG8 (timeline/chatter), au plus simple, sans route
   de détail dédiée.
   ========================================================================== */

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  { value: 'brouillon', label: 'Brouillon' },
  { value: 'planifie', label: 'Planifié' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'livre', label: 'Livré' },
  { value: 'annule', label: 'Annulé' },
]

const STATUT_TONE = {
  brouillon: 'neutral',
  planifie: 'info',
  en_cours: 'warning',
  livre: 'success',
  annule: 'danger',
}

function unwrapList(res) {
  return Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
}

export default function OrdresTransportScreen() {
  const [statutFilter, setStatutFilter] = useState('tous')
  const [selectedId, setSelectedId] = useState(null)

  const params = useMemo(
    () => (statutFilter !== 'tous' ? { statut: statutFilter } : {}),
    [statutFilter],
  )
  const { data: ordres, loading, error } = useResource(
    () => api.get('/transport/ordres-transport/', { params }),
    params,
    { initialData: [], select: unwrapList },
  )

  const selected = ordres.find((o) => o.id === selectedId) || null

  const columns = useMemo(() => [
    {
      id: 'numero',
      header: 'N° ordre',
      width: 160,
      accessor: (o) => o.numero || '',
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span>,
    },
    {
      id: 'destinataire',
      header: 'Destinataire',
      accessor: (o) => o.destinataire_nom || '',
      cell: (v) => <span className="font-medium">{v || '—'}</span>,
    },
    {
      id: 'mode',
      header: 'Mode',
      width: 140,
      accessor: (o) => o.mode_transport_display || o.mode_transport || '',
    },
    {
      id: 'poids',
      header: 'Poids total',
      align: 'right',
      width: 120,
      accessor: (o) => Number(o.poids_total_kg ?? 0),
      cell: (v) => <span className="tabular-nums">{v ? `${v} kg` : '—'}</span>,
    },
    {
      id: 'statut',
      header: 'Statut',
      width: 130,
      accessor: (o) => o.statut || '',
      cell: (v, o) => (
        <Badge tone={STATUT_TONE[v] || 'neutral'}>
          {o.statut_display || v || '—'}
        </Badge>
      ),
    },
  ], [])

  return (
    <div className="flex flex-col gap-4">
      <ListShell
        title="Ordres de transport"
        subtitle="Enlèvement/livraison, inter-site, import/export — ordonnancement, comparateur d'affrètement et suivi."
        columns={columns}
        rows={ordres}
        loading={loading}
        error={error}
        searchable
        searchPlaceholder="Rechercher un numéro, un destinataire…"
        exportName="ordres-transport"
        emptyTitle="Aucun ordre de transport"
        emptyDescription="Aucun ordre ne correspond à ces filtres."
        onRowClick={(o) => setSelectedId(o.id)}
      >
        <Segmented
          options={STATUT_FILTERS}
          value={statutFilter}
          onChange={setStatutFilter}
          aria-label="Filtrer par statut"
        />
      </ListShell>

      {selected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Truck className="size-4" aria-hidden="true" />
              {selected.numero || `Ordre #${selected.id}`}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="historique">
              <TabsList>
                <TabsTrigger value="historique">Historique</TabsTrigger>
                <TabsTrigger value="affretement">Comparateur transporteurs</TabsTrigger>
              </TabsList>
              <TabsContent value="historique">
                <OrdreTransportTimeline ordreId={selected.id} />
              </TabsContent>
              <TabsContent value="affretement">
                <ComparateurTransporteurs ordreId={selected.id} />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
