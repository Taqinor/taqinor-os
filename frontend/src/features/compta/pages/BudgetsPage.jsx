import { useState } from 'react'
import { Plus, PieChart, GitCompare, Download } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../../ui'
import { formatMAD } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT163 / XACC22 — Budgets & répartition d'un montant annuel.
   ----------------------------------------------------------------------------
   Un budget porte des lignes (compte + 12 mois). Au lieu d'une saisie manuelle
   mois par mois, « Générer une ligne (répartition) » demande un montant ANNUEL
   et une courbe (égale ou saisonnière solaire marocaine) — le serveur calcule
   les 12 montants (services.generer_ligne_budget_repartie).
   ========================================================================== */

const compteAsync = () => comptaApi.comptes.list({ page_size: 500 }).then((res) => {
  const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
  return list.map((c) => ({ value: c.id, label: `${c.numero} — ${c.intitule || c.libelle || ''}` }))
})

const BUDGET_FIELDS = [
  { name: 'annee', label: 'Année', type: 'number', required: true },
  { name: 'libelle', label: 'Libellé' },
]

const LIGNE_FIELDS = [
  { name: 'compte', label: 'Compte', async: compteAsync, required: true },
  { name: 'montant_annuel', label: 'Montant annuel', type: 'number', required: true },
  { name: 'courbe', label: 'Répartition', options: [
    { value: 'egale', label: 'Égale (1/12 par mois)' },
    { value: 'saisonniere', label: 'Saisonnière (activité solaire marocaine)' },
  ] },
  { name: 'libelle', label: 'Libellé (optionnel)' },
]

function BudgetDetailDialog({ budget, onClose, onChanged }) {
  const [ligneDialog, setLigneDialog] = useState(false)
  const [variance, setVariance] = useState(null)
  const [varianceOuvert, setVarianceOuvert] = useState(false)
  const lignes = budget.lignes || []

  // WIR255 — FG149 : variance budget vs réalisé, lue du grand livre.
  const voirVsRealise = async () => {
    try {
      const res = await comptaApi.budgets.vsRealise(budget.id)
      setVariance(res.data)
      setVarianceOuvert(true)
    } catch {
      toast.error('Variance budget vs réalisé indisponible.')
    }
  }

  const exporterVsRealise = async () => {
    try {
      const res = await comptaApi.budgets.vsRealise(budget.id, { export: 'csv' })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, `budget_vs_realise_${budget.annee}.csv`)
    } catch {
      toast.error('Export indisponible.')
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Budget {budget.annee} — {budget.libelle || 'Sans libellé'}</DialogTitle>
        </DialogHeader>

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={voirVsRealise}>
            <GitCompare className="size-4" /> Vs réalisé
          </Button>
          <Button variant="outline" onClick={exporterVsRealise}>
            <Download className="size-4" /> Export CSV
          </Button>
          <Button onClick={() => setLigneDialog(true)}>
            <Plus /> Générer une ligne (répartition)
          </Button>
        </div>

        {varianceOuvert && variance && (
          <ComptaTable
            aria-label="Budget vs réalisé"
            exportName="budget-vs-realise"
            rows={variance.lignes || []}
            getRowKey={(l, i) => l.compte_numero || i}
            columns={[
              { key: 'compte_numero', label: 'Compte', cell: (l) => l.compte_numero },
              { key: 'compte_intitule', label: 'Intitulé', cell: (l) => l.compte_intitule || '—' },
              { key: 'budget', label: 'Budget', align: 'right', numeric: true,
                sortValue: (l) => Number(l.budget) || 0, cell: (l) => formatMAD(l.budget) },
              { key: 'realise', label: 'Réalisé', align: 'right', numeric: true,
                sortValue: (l) => Number(l.realise) || 0, cell: (l) => formatMAD(l.realise) },
              { key: 'variance', label: 'Variance', align: 'right', numeric: true,
                sortValue: (l) => Number(l.variance) || 0, cell: (l) => formatMAD(l.variance) },
            ]}
          />
        )}

        {lignes.length === 0 ? (
          <EmptyState
            icon={PieChart}
            title="Aucune ligne"
            description="Générez une première ligne à partir d'un montant annuel."
          />
        ) : (
          <ComptaTable
            aria-label="Lignes du budget"
            exportName="budget-lignes"
            rows={lignes}
            getRowKey={(l) => l.id}
            columns={[
              { key: 'compte_numero', label: 'Compte', cell: (l) => l.compte_numero },
              { key: 'libelle', label: 'Libellé', cell: (l) => l.libelle || '—' },
              { key: 'montant_annuel', label: 'Montant annuel', align: 'right', numeric: true,
                sortValue: (l) => Number(l.montant_annuel) || 0,
                cell: (l) => formatMAD(l.montant_annuel) },
            ]}
          />
        )}

        {ligneDialog && (
          <CrudDialog
            open
            onClose={() => setLigneDialog(false)}
            title="Générer une ligne (répartition)"
            fields={LIGNE_FIELDS}
            onSubmit={(payload) => comptaApi.budgets.genererLigneRepartie(budget.id, payload)}
            onSaved={() => { setLigneDialog(false); onChanged() }}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function BudgetsPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [detailId, setDetailId] = useState(null)
  const list = useComptaList(comptaApi.budgets.list, undefined)

  const detail = detailId
    ? list.rows.find((b) => b.id === detailId)
    : null

  const reloadAndKeepDetail = () => list.reload()

  const columns = [
    { id: 'annee', header: 'Année', accessor: (r) => r.annee },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
    { id: 'lignes', header: 'Lignes', accessor: (r) => (r.lignes || []).length, searchable: false },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Budgets</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus /> Nouveau budget
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Budgets annuels"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetailId(row.id)}
        exportName="budgets"
        emptyTitle="Aucun budget"
        emptyDescription="Créez un budget annuel pour démarrer."
      />

      {dialogOpen && (
        <CrudDialog
          open
          onClose={() => setDialogOpen(false)}
          title="Nouveau budget"
          fields={BUDGET_FIELDS}
          onSubmit={(payload) => comptaApi.budgets.create(payload)}
          onSaved={list.reload}
        />
      )}

      {detail && (
        <BudgetDetailDialog
          budget={detail}
          onClose={() => setDetailId(null)}
          onChanged={reloadAndKeepDetail}
        />
      )}
    </div>
  )
}
