import { useState } from 'react'
import { Plus, Check, X } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, toast } from '../../../ui'
import { formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT160 / XACC24 — File d'approbation des changements de RIB fournisseur.
   ----------------------------------------------------------------------------
   Principe 4-yeux : tant qu'une demande n'est pas approuvée, le payment run
   continue d'utiliser l'ancien RIB (garanti côté serveur, jamais côté écran).
   « Approuver »/« Refuser » sont idempotents — une décision déjà prise ne se
   change pas depuis cet écran.
   ========================================================================== */

const StatutRib = statusPill({
  en_attente: { label: 'En attente', tone: 'warning' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
})

const COLUMNS = [
  { id: 'fournisseur', header: 'Fournisseur', accessor: (r) => r.fournisseur_nom || `#${r.fournisseur_id}` },
  { id: 'ancien_rib', header: 'Ancien RIB', accessor: (r) => r.ancien_rib || '—',
    cell: (v) => <span className="font-mono text-xs">{v}</span> },
  { id: 'nouveau_rib', header: 'Nouveau RIB', accessor: (r) => r.nouveau_rib || '—',
    cell: (v) => <span className="font-mono text-xs">{v}</span> },
  { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
    cell: (v) => <StatutRib status={v} /> },
  { id: 'demandeur', header: 'Demandeur', accessor: (r) => r.demandeur_nom || '—' },
  { id: 'date_creation', header: 'Demandée le', accessor: (r) => r.date_creation,
    searchable: false, cell: (v) => formatDate(v) },
]

const FIELDS = [
  { name: 'fournisseur_id', label: 'Fournisseur (id)', type: 'number', required: true },
  { name: 'fournisseur_nom', label: 'Fournisseur (nom)', required: true },
  { name: 'ancien_rib', label: 'Ancien RIB' },
  { name: 'nouveau_rib', label: 'Nouveau RIB', required: true },
]

export default function ApprobationsRibPage() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const list = useComptaList(comptaApi.approbationsRib.list, undefined)

  const decider = async (row, action, label) => {
    try {
      await action(row.id)
      toast.success(label)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const rowActions = (row) => {
    if (row.statut !== 'en_attente') return []
    return [
      {
        id: 'approuver', label: 'Approuver', icon: Check,
        onClick: () => decider(
          row, (id) => comptaApi.approbationsRib.approuver(id), 'Demande approuvée.'),
      },
      {
        id: 'refuser', label: 'Refuser', icon: X,
        onClick: () => decider(
          row, (id) => comptaApi.approbationsRib.refuser(id), 'Demande refusée.'),
      },
    ]
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Approbations RIB fournisseur</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialogOpen(true)}>
            <Plus /> Nouvelle demande
          </Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Approbations RIB"
        columns={COLUMNS}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="approbations-rib"
        emptyTitle="Aucune demande"
        emptyDescription="Aucun changement de RIB fournisseur en attente d'approbation."
      />

      {dialogOpen && (
        <CrudDialog
          open
          onClose={() => setDialogOpen(false)}
          title="Nouvelle demande de changement de RIB"
          fields={FIELDS}
          onSubmit={(payload) => comptaApi.approbationsRib.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
