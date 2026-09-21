import { useCallback, useEffect, useMemo, useState } from 'react'
import { Badge, Button, toast, Spinner, EmptyState } from '../../ui'
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

// WIR236/XFLT13 — taux de complétion des items d'inspection par conducteur
// (`InspectionVehiculeViewSet.taux_completion`) sans AUCUN consommateur
// frontend jusqu'ici.
function TauxCompletionCard() {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    flotteApi.inspections.tauxCompletion()
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data || [] }) })
      .catch((err) => {
        if (!cancelled) setState({ loading: false, error: err?.response?.data?.detail || 'Taux de complétion indisponible.', data: null })
      })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner className="size-4" /> Calcul du taux de complétion…</div>
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  const parConducteur = state.data || []
  if (parConducteur.length === 0) {
    return (
      <div className="rounded-md border border-border p-3 text-sm text-muted-foreground">
        Aucune inspection avec conducteur identifié — rien à mesurer.
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border p-3">
      <p className="text-sm font-medium">Taux de complétion par conducteur</p>
      <ul className="flex flex-col gap-1.5">
        {parConducteur.map((c) => (
          <li key={c.conducteur_id} className="flex items-center justify-between text-sm">
            <span>{c.conducteur_nom} — {c.nb_inspections} inspection(s)</span>
            <Badge tone={c.taux_completion >= 80 ? 'success' : c.taux_completion >= 50 ? 'warning' : 'danger'}>
              {c.taux_completion}%
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  )
}

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
      <TauxCompletionCard />
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
