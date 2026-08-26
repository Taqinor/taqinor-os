import { useState } from 'react'
import { Plus, PieChart, Download, BarChart3 } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState, Card, Input, Label, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '../../../ui'
import { formatMAD } from '../../../lib/format'
import { stampedFilename } from '../../../utils/downloadBlob'
import { store } from '../../../store'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'
// WIR254 — « Exécution budgétaire » (NTFIN25) réutilise le rendu générique
// d'EtatsPage au lieu d'en réinventer un pour ce seul écran.
import { EtatRender } from './EtatsPage.jsx'

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

// WIR255 — FG149 : variance budget-vs-réalisé, jusqu'ici sans aucun bouton
// (endpoint `vs_realise` déjà prêt côté serveur). Affichage sur clic +
// export CSV.
function VsRealisePanel({ budget }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const charger = () => {
    setLoading(true)
    comptaApi.budgets.vsRealise(budget.id)
      .then((res) => setData(res.data))
      .catch(() => toast.error('Variance budget vs réalisé indisponible.'))
      .finally(() => setLoading(false))
  }

  const exporterCsv = async () => {
    try {
      const res = await comptaApi.budgets.vsRealise(budget.id, { export: 'csv' })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      const societe = store.getState().parametres?.profile?.nom
      comptaApi.downloadBlob(blob, stampedFilename('budget-vs-realise', 'csv', societe))
    } catch {
      toast.error('Export CSV indisponible.')
    }
  }

  return (
    <div className="flex flex-col gap-2 border-t pt-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-display text-sm font-semibold">Vs réalisé</h4>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={charger}>
            <BarChart3 className="size-4" /> {data ? 'Actualiser' : 'Charger'}
          </Button>
          <Button variant="outline" size="sm" onClick={exporterCsv}>
            <Download className="size-4" /> Export CSV
          </Button>
        </div>
      </div>
      {loading ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Chargement…</p>
      ) : data ? (
        <EtatRender data={data} />
      ) : (
        <EmptyState title="Aucune donnée chargée" description="Cliquez sur Charger pour voir la variance." />
      )}
    </div>
  )
}

function BudgetDetailDialog({ budget, onClose, onChanged }) {
  const [ligneDialog, setLigneDialog] = useState(false)
  const lignes = budget.lignes || []

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Budget {budget.annee} — {budget.libelle || 'Sans libellé'}</DialogTitle>
        </DialogHeader>

        <div className="flex justify-end">
          <Button onClick={() => setLigneDialog(true)}>
            <Plus /> Générer une ligne (répartition)
          </Button>
        </div>

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

        <VsRealisePanel budget={budget} />

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

// WIR254 — NTFIN25 : `etats/execution-budgetaire` (budget − engagé − réalisé
// par compte/centre de coût) n'avait aucun client ni écran. Panneau autonome
// (année seule, aucun budget préalable requis côté écran).
function ExecutionBudgetairePanel() {
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const charger = () => {
    setLoading(true)
    setError(null)
    comptaApi.etats.executionBudgetaire({ annee })
      .then((res) => setData(res.data))
      .catch(() => setError('État indisponible pour cette année.'))
      .finally(() => setLoading(false))
  }

  return (
    <Card className="mt-4 p-4 sm:p-5">
      <h3 className="mb-3 font-display text-base font-semibold">Exécution budgétaire (engagements)</h3>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="eb-annee">Année</Label>
          <Input id="eb-annee" type="number" className="w-28" value={annee}
            onChange={(e) => setAnnee(e.target.value)} />
        </div>
        <Button variant="outline" size="sm" onClick={charger}>Charger</Button>
      </div>
      {loading ? (
        <p className="py-4 text-center text-sm text-muted-foreground">Chargement…</p>
      ) : error ? (
        <EmptyState title="Indisponible" description={error} />
      ) : data ? (
        <EtatRender data={data} />
      ) : (
        <EmptyState title="Aucune donnée chargée" description="Choisissez une année puis cliquez sur Charger." />
      )}
    </Card>
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

      <ExecutionBudgetairePanel />

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
