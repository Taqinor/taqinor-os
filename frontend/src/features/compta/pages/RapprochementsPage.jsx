import { useMemo, useState } from 'react'
import {
  Plus, Pencil, Lock, Unlock, CheckCircle2, Calculator,
} from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Badge, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX9 — Rapprochements, budgets & clôtures.
   ----------------------------------------------------------------------------
   Onglets : rapprochements bancaires, rapprochement 3 voies (bon-à-payer bloqué
   tant qu'il y a un écart), budgets, centres de coûts, provisions, exercices et
   périodes (verrouillage). Endpoints /compta/rapprochements/,
   /rapprochements-3voies/, /budgets/, /centres-cout/, /provisions-creances/,
   /exercices/, /periodes/.
   ========================================================================== */

const TABS = [
  { value: 'bancaires', label: 'Bancaires' },
  { value: 'troisVoies', label: '3 voies' },
  { value: 'budgets', label: 'Budgets' },
  { value: 'centres', label: 'Centres de coûts' },
  { value: 'exercices', label: 'Exercices' },
  { value: 'periodes', label: 'Périodes' },
]

const money = (v) => formatMAD(v)

const StatutRappro = statusPill({
  ouvert: { label: 'Ouvert', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  rapproche: { label: 'Rapproché', tone: 'success' },
  concordant: { label: 'Concordant', tone: 'success' },
  ecart: { label: 'Écart', tone: 'danger' },
  valide: { label: 'Validé', tone: 'success' },
})

const StatutExercice = statusPill({
  ouvert: { label: 'Ouvert', tone: 'success' },
  cloture: { label: 'Clôturé', tone: 'neutral' },
})

export default function RapprochementsPage() {
  const [tab, setTab] = useState('bancaires')
  const [dialog, setDialog] = useState(null)

  const fetcher = useMemo(() => ({
    bancaires: comptaApi.rapprochements.list,
    troisVoies: comptaApi.rapprochements3voies.list,
    budgets: comptaApi.budgets.list,
    centres: comptaApi.centresCout.list,
    exercices: comptaApi.exercices.list,
    periodes: comptaApi.periodes.list,
  }[tab]), [tab])

  const list = useComptaList(fetcher, undefined)

  const act = async (fn, okMsg) => {
    try {
      await fn()
      toast.success(okMsg)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  // ── Colonnes par onglet ──
  const columns = useMemo(() => {
    switch (tab) {
      case 'bancaires':
        return [
          { id: 'compte', header: 'Compte', accessor: (r) => r.compte_libelle || '—' },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'solde', header: 'Solde relevé', accessor: (r) => Number(r.solde_releve) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutRappro status={v} /> },
        ]
      case 'troisVoies':
        return [
          { id: 'bc', header: 'Bon de commande', accessor: (r) => r.bon_commande_reference || '—' },
          { id: 'fourn', header: 'Fournisseur', accessor: (r) => r.fournisseur_nom || '—' },
          { id: 'cmd', header: 'Commandé', accessor: (r) => Number(r.montant_commande) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'facture', header: 'Facturé', accessor: (r) => Number(r.montant_facture) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'ecart', header: 'Écart', accessor: (r) => Number(r.ecart) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'bap', header: 'Bon à payer', accessor: (r) => (r.bon_a_payer ? 'Oui' : 'Non'),
            searchable: false,
            cell: (_v, r) => (r.bon_a_payer
              ? <Badge tone="success">Bon à payer</Badge>
              : <Badge tone="warning">Bloqué (écart)</Badge>) },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutRappro status={v} /> },
        ]
      case 'budgets':
        return [
          { id: 'annee', header: 'Année', accessor: (r) => r.annee, width: 100 },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut, searchable: false },
        ]
      case 'centres':
        return [
          { id: 'code', header: 'Code', accessor: (r) => r.code, width: 120,
            cell: (v) => <span className="font-mono text-xs">{v}</span> },
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'axe', header: 'Axe', accessor: (r) => r.axe_display || r.axe || '—', searchable: false },
        ]
      case 'exercices':
        return [
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutExercice status={v} /> },
        ]
      case 'periodes':
        return [
          { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
          { id: 'type', header: 'Type', accessor: (r) => r.type_periode_display || r.type_periode || '—', searchable: false },
          { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`, searchable: false },
          { id: 'verrou', header: 'Verrou', accessor: (r) => (r.verrouillee ? 'Verrouillée' : 'Ouverte'),
            searchable: false,
            cell: (_v, r) => (r.verrouillee
              ? <Badge tone="neutral">Verrouillée</Badge>
              : <Badge tone="success">Ouverte</Badge>) },
        ]
      default:
        return []
    }
  }, [tab])

  // ── Actions par ligne / onglet ──
  const rowActions = (row) => {
    switch (tab) {
      case 'troisVoies':
        return [
          { id: 'evaluer', label: 'Réévaluer', icon: Calculator,
            onClick: () => act(() => comptaApi.rapprochements3voies.evaluer(row.id), 'Rapprochement réévalué.') },
          // Validation possible UNIQUEMENT si bon à payer (aucun écart) — sinon bloqué.
          ...(row.bon_a_payer ? [{
            id: 'valider', label: 'Valider (bon à payer)', icon: CheckCircle2,
            onClick: () => act(() => comptaApi.rapprochements3voies.valider(row.id, {}), 'Rapprochement validé.'),
          }] : []),
        ]
      case 'exercices':
        return row.statut === 'cloture'
          ? [{ id: 'rouvrir', label: 'Rouvrir', icon: Unlock,
              onClick: () => act(() => comptaApi.exercices.rouvrir(row.id), 'Exercice rouvert.') }]
          : [{ id: 'cloturer', label: 'Clôturer', icon: Lock,
              onClick: () => act(() => comptaApi.exercices.cloturer(row.id), 'Exercice clôturé.') }]
      case 'periodes':
        return row.verrouillee
          ? [{ id: 'rouvrir', label: 'Rouvrir', icon: Unlock,
              onClick: () => act(() => comptaApi.periodes.rouvrir(row.id), 'Période rouverte.') }]
          : [{ id: 'cloturer', label: 'Verrouiller', icon: Lock,
              onClick: () => act(() => comptaApi.periodes.cloturer(row.id), 'Période verrouillée.') }]
      case 'centres':
        return [{ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) }]
      default:
        return []
    }
  }

  // Onglets avec création simple (centres de coûts).
  const canCreate = tab === 'centres'
  const submit = (payload) => (dialog?.row
    ? comptaApi.centresCout.update(dialog.row.id, payload)
    : comptaApi.centresCout.create(payload))

  return (
    <div className="page">
      <div className="page-header">
        <h2>Rapprochements & clôtures</h2>
        {canCreate && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> Nouveau centre de coût
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet rapprochements" />
      </div>

      <ListShell
        title={TABS.find((t) => t.value === tab).label}
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName={tab}
        emptyTitle="Aucun élément"
        emptyDescription="Rien à afficher pour cet onglet."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? 'Modifier le centre de coût' : 'Nouveau centre de coût'}
          fields={[
            { name: 'code', label: 'Code', required: true },
            { name: 'libelle', label: 'Libellé', required: true },
          ]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
