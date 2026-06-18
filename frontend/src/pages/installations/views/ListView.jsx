// Vue LISTE des chantiers — moteur DataTable du système de design (J43).
// Le tri PAR DÉFAUT suit l'ordre d'entonnoir des statuts (jamais alphabétique) :
// la colonne « Statut » trie sur statusOrder() et la vue par défaut l'applique.
import { useMemo } from 'react'
import { Eye } from 'lucide-react'
import {
  statusLabel,
  statusOrder,
} from '../../../features/installations/statuses'
import { DataTable, StatusPill } from '../../../ui'
import { formatDate } from '../../../lib/format'
import importApi, { downloadXlsx } from '../../../api/importApi'

export default function ListView({ items, onOpen }) {
  const columns = useMemo(
    () => [
      {
        id: 'reference',
        header: 'Référence',
        width: 160,
        cell: (value) => <span className="font-semibold">{value ?? '—'}</span>,
        exportValue: (row) => row.reference ?? '',
      },
      { id: 'client_nom', header: 'Client', width: 180, accessor: (r) => r.client_nom ?? '' },
      { id: 'site_ville', header: 'Ville', width: 140, accessor: (r) => r.site_ville ?? '' },
      {
        id: 'statut',
        header: 'Statut',
        width: 190,
        searchable: false,
        // Tri funnel-aware : on trie sur la position d'entonnoir, pas le libellé.
        accessor: (row) => statusOrder(row.statut),
        cell: (value, row) => (
          <span className="flex flex-wrap items-center gap-1.5">
            <StatusPill status={row.statut} label={statusLabel(row.statut)} />
            {row.annule && <StatusPill tone="danger" label="Annulé" />}
          </span>
        ),
        exportValue: (row) => statusLabel(row.statut) + (row.annule ? ' (annulé)' : ''),
      },
      {
        id: 'type_installation',
        header: 'Type',
        width: 160,
        accessor: (r) => r.type_installation_display ?? '',
      },
      {
        id: 'technicien_nom',
        header: 'Technicien',
        width: 150,
        accessor: (r) => r.technicien_nom ?? '',
      },
      {
        id: 'date_pose_prevue',
        header: 'Pose prévue',
        width: 130,
        searchable: false,
        accessor: (r) => r.date_pose_prevue ?? '',
        cell: (value) => formatDate(value),
        exportValue: (row) => formatDate(row.date_pose_prevue),
      },
    ],
    [],
  )

  const rowActions = (row) => [
    { id: 'view', label: 'Voir', icon: Eye, onClick: () => onOpen?.(row) },
  ]

  // Vue par défaut : tri par statut dans l'ordre de l'entonnoir.
  const savedViews = [
    { id: 'funnel', label: 'Entonnoir', sorting: [{ id: 'statut', desc: false }], columnFilters: {}, query: '' },
  ]

  // Export Excel serveur (comportement identique à l'ancienne barre d'outils).
  const handleExport = (rows) => {
    importApi
      .exportList('chantiers', rows.map((r) => r.id))
      .then((r) => downloadXlsx(r.data, 'chantiers.xlsx'))
      .catch(() => {})
  }

  return (
    <DataTable
      data={items ?? []}
      columns={columns}
      getRowId={(row) => row.id}
      searchable={false}
      savedViews={savedViews}
      rowActions={rowActions}
      onRowClick={(row) => onOpen?.(row)}
      onExport={handleExport}
      exportName="chantiers"
      pageSize={25}
      emptyTitle="Aucun chantier"
      emptyDescription="Aucun chantier ne correspond aux filtres."
      aria-label="Liste des chantiers"
    />
  )
}
