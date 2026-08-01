import { useCallback, useEffect, useMemo, useState } from 'react'
import { Plus, Pencil, CalendarRange, LogOut } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
// APX33 — le tableau PARTAGÉ de la compta (tri + export CSV) remplace les
// tables écrites à la main.
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX8 — Immobilisations & plan d'amortissement.
   ----------------------------------------------------------------------------
   Registre des immobilisations (CRUD) + consultation du plan d'amortissement
   (dotations) d'une immobilisation via l'action /plan-amortissement/.
   Endpoints /compta/immobilisations/, /dotations/, /cessions/.
   ========================================================================== */

const IMMO_FIELDS = [
  { name: 'reference', label: 'Référence', required: true },
  { name: 'libelle', label: 'Libellé', required: true },
  { name: 'categorie', label: 'Catégorie' },
  { name: 'cout', label: 'Coût HT', type: 'number', required: true },
  { name: 'taux_tva', label: 'Taux TVA (%)', type: 'number' },
  { name: 'date_acquisition', label: 'Date d’acquisition', type: 'date', required: true },
]

function PlanAmortissementDialog({ immo, onClose }) {
  const [plan, setPlan] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    comptaApi.immobilisations.planAmortissement(immo.id)
      .then((res) => setPlan(res.data))
      .catch((err) => {
        if (err?.response?.status === 404) setNotFound(true)
        else toast.error('Plan d’amortissement indisponible.')
      })
      .finally(() => setLoading(false))
  }, [immo.id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const dotations = plan?.dotations || []

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Plan d’amortissement — {immo.libelle}</DialogTitle>
        </DialogHeader>
        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Chargement…</p>
        ) : notFound ? (
          <EmptyState
            icon={CalendarRange}
            title="Aucun plan d’amortissement"
            description="Cette immobilisation n’a pas encore de plan généré."
          />
        ) : (
          <ComptaTable
            aria-label="Plan d’amortissement"
            exportName="plan-amortissement"
            rows={dotations}
            getRowKey={(d) => d.id ?? d.annee}
            columns={[
              { key: 'annee', label: 'Année', sortValue: (d) => Number(d.annee) || 0,
                cell: (d) => d.annee },
              { key: 'date_dotation', label: 'Date', cell: (d) => formatDate(d.date_dotation) },
              { key: 'montant', label: 'Dotation', align: 'right', numeric: true,
                sortValue: (d) => Number(d.montant) || 0, cell: (d) => formatMAD(d.montant) },
              { key: 'cumul', label: 'Cumul', align: 'right', numeric: true,
                sortValue: (d) => Number(d.cumul) || 0, cell: (d) => formatMAD(d.cumul) },
              { key: 'valeur_nette', label: 'Valeur nette', align: 'right', numeric: true,
                sortValue: (d) => Number(d.valeur_nette) || 0, cell: (d) => formatMAD(d.valeur_nette) },
            ]}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function ImmobilisationsPage() {
  const [dialog, setDialog] = useState(null)  // édition CRUD
  const [planImmo, setPlanImmo] = useState(null) // plan d'amortissement

  const list = useComptaList(comptaApi.immobilisations.list, undefined)

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference, width: 150,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'categorie', header: 'Catégorie', accessor: (r) => r.categorie_display || r.categorie || '—' },
    { id: 'cout', header: 'Coût HT', accessor: (r) => Number(r.cout) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'acq', header: 'Acquisition', accessor: (r) => r.date_acquisition, searchable: false,
      align: 'right', cell: (v) => formatDate(v) },
  ], [])

  const ceder = async (row) => {
    const prix = window.prompt('Prix de cession (0 = mise au rebut) :', '0')
    if (prix == null) return
    try {
      await comptaApi.immobilisations.ceder(row.id, {
        date_cession: new Date().toISOString().slice(0, 10),
        prix_cession: Number(prix) || 0,
      })
      toast.success('Cession enregistrée et postée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Cession impossible.'))
    }
  }

  const rowActions = (row) => [
    { id: 'plan', label: 'Plan d’amortissement', icon: CalendarRange,
      onClick: () => setPlanImmo(row) },
    { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) },
    ...(row.actif !== false ? [{
      id: 'ceder', label: 'Céder / mettre au rebut', icon: LogOut, onClick: () => ceder(row),
    }] : []),
  ]

  const submit = (payload) => (dialog?.row
    ? comptaApi.immobilisations.update(dialog.row.id, payload)
    : comptaApi.immobilisations.create(payload))

  return (
    <div className="page">
      <div className="page-header">
        <h2>Immobilisations</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}>
            <Plus /> Nouvelle immobilisation
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Registre des immobilisations"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        onRowClick={(row) => setPlanImmo(row)}
        exportName="immobilisations"
        emptyTitle="Aucune immobilisation"
        emptyDescription="Enregistrez une immobilisation pour démarrer."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier l’immobilisation' : 'Nouvelle immobilisation'}
          fields={IMMO_FIELDS}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}

      {planImmo && (
        <PlanAmortissementDialog immo={planImmo} onClose={() => setPlanImmo(null)} />
      )}
    </div>
  )
}
