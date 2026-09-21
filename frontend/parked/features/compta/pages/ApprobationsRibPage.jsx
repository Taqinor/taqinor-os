import { useState } from 'react'
import { Plus, Check, X, ShieldCheck } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Input, Label, toast } from '../../../ui'
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

/* AUDV02 / XACC24 (DRAFT165-46) — vérificateur de RIB (clé mod-97).
   `services.diagnostic_rib` — le diagnostic PARTAGÉ stock/rh/compta —
   n'avait aucune surface HTTP : la file acceptait un nouveau RIB à clé
   fausse, et l'erreur ne se voyait qu'au rejet du virement par la banque,
   des semaines plus tard. WARNING pur : ça DIT, ça ne bloque rien. */
function VerificateurRib() {
  const [rib, setRib] = useState('')
  const [resultat, setResultat] = useState(null)
  const [busy, setBusy] = useState(false)

  const verifier = async () => {
    if (!rib.trim() || busy) return
    setBusy(true)
    try {
      const res = await comptaApi.approbationsRib.diagnosticRib(rib.trim())
      setResultat(res.data)
    } catch {
      toast.error('Vérification impossible.')
      setResultat(null)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mb-3 flex flex-wrap items-end gap-2 rounded-lg border p-3">
      <div className="flex flex-col gap-1">
        <Label htmlFor="verif-rib">Vérifier un RIB avant de le soumettre</Label>
        <Input
          id="verif-rib" value={rib} className="font-mono"
          onChange={(e) => { setRib(e.target.value); setResultat(null) }}
        />
      </div>
      <Button variant="outline" onClick={verifier} disabled={!rib.trim() || busy}>
        <ShieldCheck className="size-4" /> Vérifier
      </Button>
      {resultat && (
        <span className={resultat.valide
          ? 'text-sm text-emerald-600'
          : 'text-sm text-destructive'}>
          {resultat.valide
            ? 'Clé de contrôle valide.'
            : (resultat.erreurs || []).join(' ') || 'RIB invalide.'}
        </span>
      )}
    </div>
  )
}

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

      <VerificateurRib />

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
