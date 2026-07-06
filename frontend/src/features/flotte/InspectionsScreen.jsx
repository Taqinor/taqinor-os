import { useMemo, useState } from 'react'
import { Badge, Button, toast } from '../../ui'
import { ListShell } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import flotteApi from '../../api/flotteApi'
import { formatDateTime } from '../../lib/format'
import useFlotteResource from './useFlotteResource'
import InspectionDialog from './InspectionDialog'

/* ============================================================================
   XFLT13 — Inspections périodiques (check-lists DVIR) (`/flotte/inspections`).
   ----------------------------------------------------------------------------
   Liste des inspections réalisées (dont le nombre d'items en échec) + bouton
   « Nouvelle inspection » qui exécute la check-list du modèle choisi. Un item
   en échec crée automatiquement un signalement (XFLT5), géré côté serveur.
   ========================================================================== */

export default function InspectionsScreen() {
  const [showForm, setShowForm] = useState(false)
  const { data: actifs } = useFlotteResource(flotteApi.actifs.list, {})
  const { data: modeles } = useFlotteResource(flotteApi.modelesInspection.list, { actif: 'true' })
  const { data, loading, error, reload } = useFlotteResource(flotteApi.inspections.list, {})

  const columns = useMemo(() => [
    { id: 'actif', header: 'Actif', width: 180, accessor: (r) => r.actif_label, cell: (v) => v || '—' },
    { id: 'modele', header: 'Check-list', width: 180, accessor: (r) => r.modele_nom, cell: (v) => v || '—' },
    { id: 'conducteur', header: 'Conducteur', width: 150, accessor: (r) => r.conducteur_nom, cell: (v) => v || '—' },
    { id: 'date_inspection', header: 'Date', width: 160, accessor: (r) => r.date_inspection, cell: (v) => (v ? formatDateTime(v) : '—') },
    { id: 'signature_nom', header: 'Signataire', width: 150, accessor: (r) => r.signature_nom, cell: (v) => v || '—' },
    {
      id: 'nb_items_fail',
      header: 'Items en échec',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (r) => r.nb_items_fail ?? 0,
      cell: (v) => (v > 0 ? <Badge tone="danger">{v}</Badge> : <Badge tone="success">0</Badge>),
    },
  ], [])

  const actions = (
    <Button onClick={() => setShowForm(true)}>Nouvelle inspection</Button>
  )

  return (
    <div className="page flex flex-col gap-4">
      <PageHeader
        title="Inspections périodiques"
        subtitle="Check-lists DVIR pré-départ — tout item en échec crée un signalement."
      />
      <ListShell
        title="Inspections réalisées"
        actions={actions}
        columns={columns}
        rows={data}
        loading={loading}
        error={error}
        exportName="inspections"
        emptyTitle="Aucune inspection"
        emptyDescription="Aucune inspection enregistrée."
      />
      {showForm && (
        <InspectionDialog
          actifs={actifs}
          modeles={modeles}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); reload(); toast.success('Inspection enregistrée.') }}
        />
      )}
    </div>
  )
}
