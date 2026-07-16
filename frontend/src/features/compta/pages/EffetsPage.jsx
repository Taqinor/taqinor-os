import { useMemo, useState } from 'react'
import { useTabParam } from '../components/useTabParam'
import {
  Plus, CheckCircle2, XCircle, Send, TrendingDown, Landmark, Download,
} from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   FG127/128/129/133/134 — Effets à recevoir/payer, bordereaux de remise,
   campagnes de règlement fournisseurs.
   ----------------------------------------------------------------------------
   Onglets : effets (chèques/traites, encaisser/payer/rejeter/escompter/
   endosser), bordereaux de remise en banque (regroupement + poster), campagnes
   de règlement (payment runs : proposer/figer/poster/fichier-virement).
   Endpoints /compta/effets/, /bordereaux/, /payment-runs/.
   ========================================================================== */

const TABS = [
  { value: 'effets', label: 'Effets à recevoir/payer' },
  { value: 'bordereaux', label: 'Bordereaux de remise' },
  { value: 'paymentRuns', label: 'Campagnes de règlement' },
]

const StatutEffet = statusPill({
  portefeuille: { label: 'Portefeuille', tone: 'neutral' },
  remis: { label: 'Remis', tone: 'info' },
  encaisse: { label: 'Encaissé', tone: 'success' },
  paye: { label: 'Payé', tone: 'success' },
  impaye: { label: 'Impayé', tone: 'danger' },
  escompte: { label: 'Escompté', tone: 'info' },
  endosse: { label: 'Endossé', tone: 'info' },
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  proposee: { label: 'Proposée', tone: 'info' },
  postee: { label: 'Postée', tone: 'success' },
})

const money = (v) => formatMAD(v)

export default function EffetsPage() {
  const [tab, setTab] = useTabParam('effets')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)

  const fetcher = useMemo(() => ({
    effets: comptaApi.effets.list,
    bordereaux: comptaApi.bordereaux.list,
    paymentRuns: comptaApi.paymentRuns.list,
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

  const download = async (fn, filename) => {
    try {
      const res = await fn()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, filename)
    } catch {
      toast.error('Téléchargement indisponible.')
    }
  }

  const columns = useMemo(() => {
    switch (tab) {
      case 'effets':
        return [
          { id: 'numero', header: 'N°', accessor: (r) => r.numero || '—',
            cell: (v) => <span className="font-mono text-xs">{v}</span> },
          { id: 'sens', header: 'Sens', accessor: (r) => (r.sens === 'recevoir' ? 'À recevoir' : 'À payer'),
            searchable: false },
          { id: 'tireur', header: 'Tireur/Banque', accessor: (r) => r.tireur || r.banque || '—' },
          { id: 'echeance', header: 'Échéance', accessor: (r) => r.date_echeance, searchable: false,
            cell: (v) => formatDate(v) },
          { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutEffet status={v} /> },
        ]
      case 'bordereaux':
        return [
          { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
            cell: (v) => <span className="font-mono text-xs">{v}</span> },
          { id: 'date', header: 'Date remise', accessor: (r) => r.date_remise, searchable: false,
            cell: (v) => formatDate(v) },
          { id: 'nb', header: 'Nb effets', accessor: (r) => (r.effets || []).length, searchable: false },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutEffet status={v} /> },
        ]
      case 'paymentRuns':
        return [
          { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
            cell: (v) => <span className="font-mono text-xs">{v}</span> },
          { id: 'date', header: 'Date paiement', accessor: (r) => r.date_paiement, searchable: false,
            cell: (v) => formatDate(v) },
          { id: 'mode', header: 'Mode', accessor: (r) => r.mode_paiement_display || r.mode_paiement || '—' },
          { id: 'total', header: 'Total', accessor: (r) => Number(r.total) || 0,
            align: 'right', numeric: true, searchable: false, cell: money },
          { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
            cell: (v) => <StatutEffet status={v} /> },
        ]
      default:
        return []
    }
  }, [tab])

  const rowActions = (row) => {
    if (tab === 'effets') {
      const acts = []
      if (row.statut === 'portefeuille' && row.sens === 'recevoir') {
        acts.push({ id: 'encaisser', label: 'Encaisser', icon: CheckCircle2,
          onClick: () => act(() => comptaApi.effets.encaisser(row.id, {}), 'Effet encaissé.') })
        acts.push({ id: 'escompter', label: 'Escompter', icon: TrendingDown,
          onClick: () => toast.error('Escompte : choisissez le compte de trésorerie depuis le détail.') })
      }
      if (row.statut === 'portefeuille' && row.sens === 'payer') {
        acts.push({ id: 'payer', label: 'Payer', icon: Send,
          onClick: () => act(() => comptaApi.effets.payer(row.id, {}), 'Effet payé.') })
      }
      if (['remis', 'portefeuille'].includes(row.statut)) {
        acts.push({ id: 'rejeter', label: 'Rejeter (impayé)', icon: XCircle,
          onClick: () => act(() => comptaApi.effets.rejeter(row.id, {}), 'Effet rejeté.') })
      }
      return acts
    }
    if (tab === 'bordereaux' && row.statut !== 'postee') {
      return [{ id: 'poster', label: 'Poster', icon: Landmark,
        onClick: () => act(() => comptaApi.bordereaux.poster(row.id), 'Bordereau posté.') }]
    }
    if (tab === 'paymentRuns') {
      const acts = []
      if (row.statut === 'brouillon') {
        acts.push({ id: 'proposer', label: 'Proposer les lignes', icon: Send,
          onClick: () => act(() => comptaApi.paymentRuns.proposer(row.id, {}), 'Lignes proposées.') })
        acts.push({ id: 'figer', label: 'Figer', icon: CheckCircle2,
          onClick: () => act(() => comptaApi.paymentRuns.figer(row.id), 'Campagne figée.') })
      }
      if (row.statut === 'proposee') {
        acts.push({ id: 'poster', label: 'Poster', icon: Landmark,
          onClick: () => act(() => comptaApi.paymentRuns.poster(row.id), 'Campagne postée.') })
      }
      acts.push({ id: 'virement', label: 'Fichier virement', icon: Download,
        onClick: () => download(() => comptaApi.paymentRuns.fichierVirement(row.id),
          `virements_${row.reference || row.id}.csv`) })
      return acts
    }
    return []
  }

  const createFields = {
    effets: [
      { name: 'sens', label: 'Sens', options: [
        { value: 'recevoir', label: 'À recevoir' }, { value: 'payer', label: 'À payer' }] },
      { name: 'numero', label: 'Numéro' },
      { name: 'tireur', label: 'Tireur' },
      { name: 'banque', label: 'Banque' },
      { name: 'date_emission', label: "Date d'émission", type: 'date' },
      { name: 'date_echeance', label: "Date d'échéance", type: 'date', required: true },
      { name: 'montant', label: 'Montant', type: 'number', required: true },
    ],
  }

  const canCreate = tab === 'effets'
  const submit = (payload) => comptaApi.effets.create(payload)

  return (
    <div className="page">
      <div className="page-header">
        <h2>Effets & règlements fournisseurs</h2>
        {canCreate && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> Nouvel effet
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet effets" />
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
          title="Nouvel effet"
          fields={createFields.effets}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}
