import { useState } from 'react'
import { Plus, CheckCircle2, XCircle } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, toast } from '../../../ui'
import { formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT42 — Approbation des configurations non standard.
   ----------------------------------------------------------------------------
   FG213 : fait partir en validation toute composition de devis qui sort des
   règles (ex. kWc/onduleur incohérents), traçable (demandeur, décideur,
   motif). Aujourd'hui une composition non standard ne PEUT PAS être
   formellement approuvée — cet écran ouvre les deux seules actions
   (approuver/refuser) déjà prêtes côté serveur. Une demande refusée garde
   son motif ET son commentaire de décision visibles dans l'historique.
   Endpoint /compta/approbations-config/.
   ========================================================================== */

const StatutTag = statusPill({
  en_attente: { label: 'En attente', tone: 'warning' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
})

export default function ApprobationsConfigPage() {
  const [dialog, setDialog] = useState(false)
  const list = useComptaList(comptaApi.approbationsConfig.list, undefined)

  const decider = async (row, approuver) => {
    const commentaire = window.prompt(
      approuver ? 'Commentaire (optionnel) :' : 'Motif du refus (optionnel) :', '')
    if (commentaire === null) return
    try {
      const fn = approuver ? comptaApi.approbationsConfig.approuver : comptaApi.approbationsConfig.refuser
      await fn(row.id, { commentaire })
      toast.success(approuver ? 'Demande approuvée.' : 'Demande refusée — motif conservé dans l’historique.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Décision impossible.'))
    }
  }

  const columns = [
    { id: 'devis', header: 'Devis', accessor: (r) => r.devis_reference || `#${r.devis_id}`,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'motif', header: 'Motif', accessor: (r) => r.motif },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
    { id: 'demandeur', header: 'Demandeur', accessor: (r) => r.demandeur_nom || '—' },
    { id: 'decideur', header: 'Décideur', accessor: (r) => r.decideur_nom || '—' },
    { id: 'commentaire', header: 'Commentaire de décision', accessor: (r) => r.commentaire_decision || '—' },
    { id: 'date_decision', header: 'Décidée le', accessor: (r) => r.date_decision, searchable: false,
      cell: (v) => (v ? formatDate(v) : '—') },
  ]

  const rowActions = (row) => (row.statut === 'en_attente'
    ? [
      { id: 'approuver', label: 'Approuver', icon: CheckCircle2, onClick: () => decider(row, true) },
      { id: 'refuser', label: 'Refuser', icon: XCircle, onClick: () => decider(row, false) },
    ]
    : [])

  const fields = [
    { name: 'devis_id', label: 'Devis (id)', type: 'number' },
    { name: 'devis_reference', label: 'Référence devis' },
    { name: 'motif', label: 'Motif de la non-conformité', required: true },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Approbations de configurations non standard</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog(true)}><Plus /> Nouvelle demande</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Demandes d'approbation"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="approbations-config"
        emptyTitle="Aucune demande"
        emptyDescription="Aucune composition non standard en attente de décision."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Nouvelle demande d'approbation"
          fields={fields}
          onSubmit={(payload) => comptaApi.approbationsConfig.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
