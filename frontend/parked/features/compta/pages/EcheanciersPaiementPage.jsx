import { useState } from 'react'
import { Plus, CircleDollarSign } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import {
  Button, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Input, Label, toast,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   PACT41 — Échéanciers de paiement en tranches.
   ----------------------------------------------------------------------------
   FG220 : découpe une facture en tranches datées avec suivi des versements —
   indispensable pour les gros chantiers payés en plusieurs fois (type
   Tayssir). `montant_regle`/`reste_a_payer` sont calculés côté serveur
   (EcheancierPaiementSerializer) : le solde restant doit se mettre à jour
   VISIBLEMENT dès qu'une tranche est réglée — jamais un chiffre figé côté
   client. Endpoints /compta/echeanciers-paiement/, /compta/tranches-paiement/.
   ========================================================================== */

function TranchesDialog({ echeancier, onClose, onChanged }) {
  const [detail, setDetail] = useState(echeancier)
  const [numero, setNumero] = useState('')
  const [montant, setMontant] = useState('')
  const [dateEcheance, setDateEcheance] = useState('')
  const [saving, setSaving] = useState(false)

  const refresh = async () => {
    const res = await comptaApi.echeanciersPaiement.get(echeancier.id)
    setDetail(res.data)
    onChanged?.()
  }

  const ajouterTranche = async (e) => {
    e.preventDefault()
    if (!numero || !montant || !dateEcheance) return
    setSaving(true)
    try {
      await comptaApi.tranchesPaiement.create({
        echeancier: echeancier.id, numero: Number(numero), montant: Number(montant) || 0,
        date_echeance: dateEcheance,
      })
      setNumero(''); setMontant(''); setDateEcheance('')
      toast.success('Tranche ajoutée.')
      await refresh()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ajout impossible.'))
    } finally {
      setSaving(false)
    }
  }

  const regler = async (tranche) => {
    const saisie = window.prompt('Montant réglé :', String(tranche.montant))
    if (saisie == null) return
    try {
      await comptaApi.tranchesPaiement.regler(tranche.id, { montant: Number(saisie) || 0 })
      toast.success('Tranche réglée — solde restant mis à jour.')
      await refresh()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Règlement impossible.'))
    }
  }

  const tranches = detail.tranches || []

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Tranches — {detail.facture_reference || `Facture #${detail.facture_id}`}</DialogTitle>
        </DialogHeader>

        <div className="rounded-md border border-border p-3 text-sm">
          <p>Montant total : <strong>{formatMAD(detail.montant_total)}</strong></p>
          <p>Réglé : <strong>{formatMAD(detail.montant_regle)}</strong></p>
          <p>Reste à payer : <strong>{formatMAD(detail.reste_a_payer)}</strong></p>
        </div>

        {tranches.length === 0 ? (
          <EmptyState title="Aucune tranche" description="Ajoutez une première tranche ci-dessous." />
        ) : (
          <ComptaTable
            aria-label="Tranches de paiement"
            rows={tranches}
            getRowKey={(t) => t.id}
            columns={[
              { key: 'numero', label: 'N°', cell: (t) => t.numero },
              { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                sortValue: (t) => Number(t.montant) || 0, cell: (t) => formatMAD(t.montant) },
              { key: 'echeance', label: 'Échéance', cell: (t) => formatDate(t.date_echeance) },
              { key: 'paye', label: 'Réglée', cell: (t) => (t.paye ? `Oui (${formatDate(t.date_reglement)})` : 'Non') },
              { key: 'action', label: '', cell: (t) => (!t.paye ? (
                <Button size="sm" variant="ghost" onClick={() => regler(t)}>
                  <CircleDollarSign className="size-4" /> Régler
                </Button>
              ) : null) },
            ]}
          />
        )}

        <form onSubmit={ajouterTranche} noValidate className="flex flex-wrap items-end gap-2 border-t pt-3">
          <div className="flex flex-col gap-1">
            <Label htmlFor="tp-numero">N°</Label>
            <Input id="tp-numero" type="number" value={numero} onChange={(e) => setNumero(e.target.value)} className="w-20" />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="tp-montant">Montant</Label>
            <Input id="tp-montant" type="number" step="any" value={montant} onChange={(e) => setMontant(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="tp-echeance">Échéance</Label>
            <Input id="tp-echeance" type="date" value={dateEcheance} onChange={(e) => setDateEcheance(e.target.value)} />
          </div>
          <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter la tranche'}</Button>
        </form>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function EcheanciersPaiementPage() {
  const [dialog, setDialog] = useState(false)
  const [detailDe, setDetailDe] = useState(null)
  const list = useComptaList(comptaApi.echeanciersPaiement.list, undefined)

  const columns = [
    { id: 'facture', header: 'Facture', accessor: (r) => r.facture_reference || `#${r.facture_id}`,
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'montant_total', header: 'Montant total', accessor: (r) => Number(r.montant_total) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'montant_regle', header: 'Réglé', accessor: (r) => Number(r.montant_regle) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'reste', header: 'Reste à payer', accessor: (r) => Number(r.reste_a_payer) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'tranches', header: 'Tranches', accessor: (r) => (r.tranches || []).length, width: 90 },
  ]

  const fields = [
    { name: 'facture_id', label: 'Facture (id)', type: 'number', required: true },
    { name: 'montant_total', label: 'Montant total', type: 'number', required: true },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Échéanciers de paiement</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog(true)}><Plus /> Nouvel échéancier</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Échéanciers"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetailDe(row)}
        exportName="echeanciers-paiement"
        emptyTitle="Aucun échéancier"
        emptyDescription="Aucune facture découpée en tranches pour l'instant."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(false)}
          title="Nouvel échéancier de paiement"
          fields={fields}
          onSubmit={(payload) => comptaApi.echeanciersPaiement.create(payload)}
          onSaved={list.reload}
        />
      )}

      {detailDe && (
        <TranchesDialog echeancier={detailDe} onClose={() => setDetailDe(null)} onChanged={list.reload} />
      )}
    </div>
  )
}
