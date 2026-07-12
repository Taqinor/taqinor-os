import { useEffect, useState } from 'react'
import { useIsAdmin } from '../../../hooks/useHasPermission'
import {
  Plus, Unlock, ShieldCheck, TrendingUp, Undo2, Send, CheckCircle2,
  Landmark, ShieldAlert,
} from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Card, EmptyState, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import { stampedFilename } from '../../../utils/downloadBlob'
import { store } from '../../../store'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   FG145–148 / XFAC14 / XACC26 / COMPTA39 — Engagements & clôtures avancées.
   ----------------------------------------------------------------------------
   Onglets : retenues de garantie & cautions bancaires (FG145), contrats à
   l'avancement / WIP (FG146-147), campagnes de commissions (FG148),
   compensations AR/AP (XFAC14), provisions FNP/FAE de fin de période (XACC26),
   et — réservé Admin — la piste d'audit comptable hash-chaînée (COMPTA39).
   Endpoints /compta/retenues-garantie/, /cautions-bancaires/,
   /contrats-avancement/, /travaux-en-cours/, /commission-payout-runs/,
   /compensations/, /provisions-periode/, /pistes-audit/.
   ========================================================================== */

const StatutTag = statusPill({
  constituee: { label: 'Constituée', tone: 'neutral' },
  liberee: { label: 'Libérée', tone: 'success' },
  active: { label: 'Active', tone: 'neutral' },
  mainlevee: { label: 'Mainlevée', tone: 'success' },
  restituee: { label: 'Restituée', tone: 'success' },
  en_cours: { label: 'En cours', tone: 'info' },
  cloture: { label: 'Clôturé', tone: 'success' },
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  valide: { label: 'Validé', tone: 'info' },
  poste: { label: 'Posté', tone: 'success' },
  reprise: { label: 'Repris', tone: 'success' },
})

const money = (v) => formatMAD(v)

// ── FG145 — Retenues de garantie ──
function RetenuesGarantiePanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.retenuesGarantie.list, undefined)

  const liberer = async (row) => {
    try {
      await comptaApi.retenuesGarantie.liberer(row.id, {})
      toast.success('Retenue de garantie libérée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Libération impossible.'))
    }
  }

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'marche', header: 'Marché', accessor: (r) => r.marche_ref || '—' },
    { id: 'tiers', header: 'Maître d’ouvrage', accessor: (r) => r.tiers_nom || '—' },
    { id: 'montant', header: 'Montant retenu', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'levee', header: 'Levée prévue', accessor: (r) => r.date_levee_prevue, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ]

  const rowActions = (row) => (row.statut !== 'liberee'
    ? [{ id: 'liberer', label: 'Libérer', icon: Unlock, onClick: () => liberer(row) }]
    : [])

  const fields = [
    { name: 'date_constitution', label: 'Date constitution', type: 'date', required: true },
    { name: 'base', label: 'Base', type: 'number', required: true },
    { name: 'taux', label: 'Taux (%)', type: 'number' },
    { name: 'marche_ref', label: 'Marché' },
    { name: 'tiers_nom', label: 'Maître d’ouvrage' },
    { name: 'date_levee_prevue', label: 'Levée prévue', type: 'date' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle RG</Button>
      </div>
      <ListShell
        title="Retenues de garantie"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="retenues-garantie"
        emptyTitle="Aucune retenue"
        emptyDescription="Aucune retenue de garantie enregistrée."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle retenue de garantie"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.retenuesGarantie.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── FG145 — Cautions bancaires ──
function CautionsBancairesPanel() {
  const [dialog, setDialog] = useState(null)
  const list = useComptaList(comptaApi.cautionsBancaires.list, undefined)

  const mainlevee = async (row) => {
    try {
      await comptaApi.cautionsBancaires.mainlevee(row.id, {})
      toast.success('Caution levée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Mainlevée impossible.'))
    }
  }

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'type', header: 'Type', accessor: (r) => r.type_caution_display || r.type_caution || '—' },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'echeance', header: 'Échéance', accessor: (r) => r.date_echeance, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ]

  const rowActions = (row) => (row.statut === 'active'
    ? [{ id: 'mainlevee', label: 'Mainlevée', icon: ShieldCheck, onClick: () => mainlevee(row) }]
    : [])

  const fields = [
    { name: 'type_caution', label: 'Type' },
    { name: 'date_emission', label: 'Date émission', type: 'date', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'banque', label: 'Banque' },
    { name: 'marche_ref', label: 'Marché' },
    { name: 'date_echeance', label: 'Échéance', type: 'date' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialog({ row: null })}><Plus /> Nouvelle caution</Button>
      </div>
      <ListShell
        title="Cautions bancaires"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName="cautions-bancaires"
        emptyTitle="Aucune caution"
        emptyDescription="Aucune caution bancaire enregistrée."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouvelle caution bancaire"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.cautionsBancaires.create(payload)}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── FG146/147 — Contrats à l'avancement & travaux en cours ──
function AvancementPanel() {
  const [sub, setSub] = useState('contrats')
  const [dialog, setDialog] = useState(null)
  const fetcher = sub === 'contrats' ? comptaApi.contratsAvancement.list : comptaApi.travauxEnCours.list
  const list = useComptaList(fetcher, undefined)

  const columns = sub === 'contrats' ? [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || r.chantier_ref || '—' },
    { id: 'revenu_total', header: 'Revenu total', accessor: (r) => Number(r.revenu_total) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'revenu_reconnu', header: 'Revenu reconnu', accessor: (r) => Number(r.revenu_reconnu) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ] : [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'nature', header: 'Nature', accessor: (r) => r.nature_display || r.nature || '—' },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'arrete', header: 'Date arrêté', accessor: (r) => r.date_arrete, searchable: false,
      cell: (v) => formatDate(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ]

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

  const rowActions = (row) => {
    if (sub === 'contrats' && row.statut !== 'cloture') {
      return [{ id: 'constater', label: 'Constater avancement', icon: TrendingUp,
        onClick: () => {
          const pct = window.prompt('Pourcentage d’avancement constaté (%)')
          if (pct == null) return
          act(() => comptaApi.contratsAvancement.constater(row.id, {
            date_arrete: new Date().toISOString().slice(0, 10), pourcentage: pct,
          }), 'Avancement constaté.')
        } }]
    }
    if (sub === 'travaux' && !row.date_reprise) {
      return [{ id: 'reprendre', label: 'Reprendre (extourner)', icon: Undo2,
        onClick: () => act(() => comptaApi.travauxEnCours.reprendre(row.id, {}), 'Régularisation reprise.') }]
    }
    return []
  }

  const contratFields = [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'revenu_total', label: 'Revenu total', type: 'number', required: true },
    { name: 'cout_total_estime', label: 'Coût total estimé', type: 'number' },
    { name: 'chantier_ref', label: 'Chantier' },
    { name: 'date_debut', label: 'Date début', type: 'date' },
  ]
  const travauxFields = [
    { name: 'nature', label: 'Nature', options: [
      { value: 'pca', label: 'Produits constatés d’avance' },
      { value: 'fnp', label: 'Factures non parvenues' },
    ] },
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'montant', label: 'Montant', type: 'number', required: true },
    { name: 'date_arrete', label: 'Date arrêté', type: 'date', required: true },
    { name: 'chantier_ref', label: 'Chantier' },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Segmented
          options={[{ value: 'contrats', label: 'Contrats à l’avancement' }, { value: 'travaux', label: 'Travaux en cours (WIP)' }]}
          value={sub} onChange={setSub}
        />
        <Button size="sm" onClick={() => setDialog({ row: null })}>
          <Plus /> Nouveau {sub === 'contrats' ? 'contrat' : 'poste WIP'}
        </Button>
      </div>
      <ListShell
        title={sub === 'contrats' ? 'Contrats à l’avancement' : 'Travaux en cours'}
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        rowActions={rowActions}
        exportName={sub}
        emptyTitle="Aucun élément"
        emptyDescription="Rien à afficher."
      />
      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={sub === 'contrats' ? 'Nouveau contrat à l’avancement' : 'Nouveau poste WIP'}
          fields={sub === 'contrats' ? contratFields : travauxFields}
          initial={dialog.row}
          onSubmit={(payload) => (sub === 'contrats'
            ? comptaApi.contratsAvancement.create(payload)
            : comptaApi.travauxEnCours.create(payload))}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

// ── FG148 — Campagnes de versement des commissions ──
function CommissionPayoutPanel() {
  const list = useComptaList(comptaApi.commissionPayoutRuns.list, undefined)

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

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || r.periode || '—' },
    { id: 'total', header: 'Total', accessor: (r) => Number(r.total) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ]

  const rowActions = (row) => {
    const acts = []
    if (row.statut === 'brouillon') {
      acts.push({ id: 'valider', label: 'Valider', icon: CheckCircle2,
        onClick: () => act(() => comptaApi.commissionPayoutRuns.valider(row.id), 'Campagne validée.') })
    }
    if (row.statut === 'valide') {
      acts.push({ id: 'poster', label: 'Poster', icon: Landmark,
        onClick: () => act(() => comptaApi.commissionPayoutRuns.poster(row.id), 'Campagne postée.') })
    }
    return acts
  }

  return (
    <ListShell
      title="Campagnes de versement des commissions"
      columns={columns}
      rows={list.rows}
      loading={list.loading}
      error={list.error}
      rowActions={rowActions}
      exportName="commission-payout-runs"
      emptyTitle="Aucune campagne"
      emptyDescription="Aucune campagne de versement de commissions."
    />
  )
}

// ── XFAC14 — Compensations AR/AP (netting) ──
function CompensationsPanel() {
  const list = useComptaList(comptaApi.compensations.list, undefined)

  const valider = async (row) => {
    try {
      await comptaApi.compensations.valider(row.id)
      toast.success('Compensation validée.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Validation impossible.'))
    }
  }

  const columns = [
    { id: 'client', header: 'Client', accessor: (r) => r.client_nom || r.client_id || '—' },
    { id: 'fournisseur', header: 'Fournisseur', accessor: (r) => r.fournisseur_nom || r.fournisseur_id || '—' },
    { id: 'montant', header: 'Montant compensé', accessor: (r) => Number(r.montant_total) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutTag status={v} /> },
  ]

  const rowActions = (row) => (row.statut !== 'valide'
    ? [{ id: 'valider', label: 'Valider', icon: CheckCircle2, onClick: () => valider(row) }]
    : [])

  return (
    <ListShell
      title="Compensations AR/AP"
      columns={columns}
      rows={list.rows}
      loading={list.loading}
      error={list.error}
      rowActions={rowActions}
      exportName="compensations"
      emptyTitle="Aucune compensation"
      emptyDescription="Aucune compensation enregistrée pour un tiers à la fois client et fournisseur."
    />
  )
}

// ── XACC26 — Provisions FNP/FAE de fin de période ──
function ProvisionsPeriodePanel() {
  const [rapport, setRapport] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    comptaApi.provisionsPeriode.rapport()
      .then((res) => setRapport(res.data))
      .catch(() => toast.error('Rapport de provisions indisponible.'))
      .finally(() => setLoading(false))
  }, [])

  const exportCsv = async () => {
    try {
      const res = await comptaApi.provisionsPeriode.exportCsv()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      // VX81 — nom d'export horodaté (au lieu d'un nom nu figé).
      const societe = store.getState().parametres?.profile?.nom
      comptaApi.downloadBlob(blob, stampedFilename('provisions-fnp-fae', 'csv', societe))
    } catch {
      toast.error('Export indisponible.')
    }
  }

  if (loading) return <p className="py-8 text-center text-sm text-muted-foreground">Chargement…</p>

  const items = rapport?.lignes || []

  return (
    <Card className="p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-display text-base font-semibold">Provisions FNP / FAE</h3>
        <Button variant="outline" size="sm" onClick={exportCsv}>Export CSV</Button>
      </div>
      {!items.length ? (
        <EmptyState title="Aucune provision" description="Aucune provision FNP/FAE sur la période." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-2 py-2">Type</th>
                <th className="px-2 py-2">Libellé</th>
                <th className="px-2 py-2 text-right">Montant</th>
              </tr>
            </thead>
            <tbody>
              {items.map((li, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="px-2 py-1.5">{li.type || li.nature || '—'}</td>
                  <td className="px-2 py-1.5">{li.libelle || '—'}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">{formatMAD(li.montant)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

// ── COMPTA39 — Piste d'audit comptable (admin uniquement) ──
function PisteAuditPanel() {
  const list = useComptaList(comptaApi.pistesAudit.list, undefined)
  const [integrite, setIntegrite] = useState(null)

  const verifier = async () => {
    try {
      const res = await comptaApi.pistesAudit.verifier()
      setIntegrite(res.data)
      toast.success(res.data?.intacte === false ? 'Rupture détectée.' : 'Chaîne intacte.')
    } catch {
      toast.error('Vérification impossible.')
    }
  }

  const columns = [
    { id: 'sequence', header: 'Séquence', accessor: (r) => r.sequence, width: 100 },
    { id: 'ecriture', header: 'Écriture', accessor: (r) => r.ecriture_id || r.ecriture || '—' },
    { id: 'hash', header: 'Hash', accessor: (r) => r.hash || r.empreinte || '—',
      cell: (v) => <span className="font-mono text-xs">{String(v).slice(0, 16)}…</span> },
    { id: 'date', header: 'Date', accessor: (r) => r.date_creation, searchable: false,
      cell: (v) => formatDate(v) },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-base font-semibold">Piste d’audit comptable (hash-chaînée)</h3>
        <Button variant="outline" size="sm" onClick={verifier}>
          <ShieldAlert className="size-4" /> Vérifier l’intégrité
        </Button>
      </div>
      {integrite && (
        <Card className={`p-3 text-sm ${integrite.intacte === false ? 'border-destructive/40 bg-destructive/5' : 'border-success/40 bg-success/5'}`}>
          {integrite.intacte === false
            ? `Rupture détectée : ${integrite.detail || 'voir maillon en cause.'}`
            : 'Chaîne d’audit intacte — aucune altération détectée.'}
        </Card>
      )}
      <ListShell
        title="Maillons scellés"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        exportName="piste-audit"
        emptyTitle="Aucun maillon"
        emptyDescription="Aucune écriture scellée pour le moment."
      />
    </div>
  )
}

const TABS = [
  { value: 'retenuesGarantie', label: 'Retenues de garantie' },
  { value: 'cautionsBancaires', label: 'Cautions bancaires' },
  { value: 'avancement', label: 'Avancement / WIP' },
  { value: 'commissionPayout', label: 'Commissions' },
  { value: 'compensations', label: 'Compensations AR/AP' },
  { value: 'provisionsPeriode', label: 'Provisions FNP/FAE' },
]

export default function EngagementsPage() {
  const [tab, setTab] = useState('retenuesGarantie')
  const isAdmin = useIsAdmin()
  const tabs = isAdmin ? [...TABS, { value: 'pisteAudit', label: 'Piste d’audit' }] : TABS

  return (
    <div className="page">
      <div className="page-header">
        <h2>Engagements & clôtures avancées</h2>
      </div>

      <div className="mb-3">
        <Segmented options={tabs} value={tab} onChange={setTab} aria-label="Onglet engagements" />
      </div>

      {tab === 'retenuesGarantie' && <RetenuesGarantiePanel />}
      {tab === 'cautionsBancaires' && <CautionsBancairesPanel />}
      {tab === 'avancement' && <AvancementPanel />}
      {tab === 'commissionPayout' && <CommissionPayoutPanel />}
      {tab === 'compensations' && <CompensationsPanel />}
      {tab === 'provisionsPeriode' && <ProvisionsPeriodePanel />}
      {tab === 'pisteAudit' && isAdmin && <PisteAuditPanel />}
    </div>
  )
}
