import { useState } from 'react'
import { Plus, Scale, CalendarPlus, CheckCircle2 } from 'lucide-react'
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
   PACT34 — Reconnaissance du revenu (IFRS 15).
   ----------------------------------------------------------------------------
   NTFIN46-48 : un contrat de revenu répartit son prix de transaction entre ses
   obligations de performance (matériel livré, maintenance…) au prorata du
   prix de vente spécifique de chacune, puis chaque obligation reconnaît son
   revenu selon un échéancier (à une date ou linéaire dans le temps) — utile
   pour les contrats pluriannuels (maintenance solaire, monitoring) où le
   revenu s'étale plutôt que de se reconnaître à la facturation. Endpoints
   /compta/contrats-revenu/, /obligations-performance/,
   /echeances-reconnaissance/.
   ========================================================================== */

function AjouterObligationForm({ contratId, onAdded }) {
  const [libelle, setLibelle] = useState('')
  const [prix, setPrix] = useState('')
  const [methode, setMethode] = useState('a_une_date')
  const [dureeMois, setDureeMois] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!libelle || !prix) return
    setSaving(true)
    try {
      await comptaApi.obligationsPerformance.create({
        contrat: contratId, libelle, prix_vente_specifique: Number(prix) || 0,
        methode_reconnaissance: methode,
        duree_mois: methode === 'dans_le_temps' ? (Number(dureeMois) || undefined) : undefined,
        date_debut: dateDebut || undefined,
      })
      toast.success('Obligation de performance ajoutée.')
      setLibelle(''); setPrix(''); setDureeMois(''); setDateDebut('')
      onAdded?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Ajout impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-wrap items-end gap-2 border-t pt-3">
      <div className="flex flex-1 min-w-40 flex-col gap-1">
        <Label htmlFor="op-libelle">Libellé</Label>
        <Input id="op-libelle" value={libelle} onChange={(e) => setLibelle(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="op-prix">Prix de vente spécifique</Label>
        <Input id="op-prix" type="number" step="any" value={prix} onChange={(e) => setPrix(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="op-methode">Méthode</Label>
        <select id="op-methode" className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
          value={methode} onChange={(e) => setMethode(e.target.value)}>
          <option value="a_une_date">À une date</option>
          <option value="dans_le_temps">Dans le temps (linéaire)</option>
        </select>
      </div>
      {methode === 'dans_le_temps' && (
        <div className="flex flex-col gap-1">
          <Label htmlFor="op-duree">Durée (mois)</Label>
          <Input id="op-duree" type="number" value={dureeMois} onChange={(e) => setDureeMois(e.target.value)} />
        </div>
      )}
      <div className="flex flex-col gap-1">
        <Label htmlFor="op-debut">Début</Label>
        <Input id="op-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
      </div>
      <Button type="submit" disabled={saving}>{saving ? 'Ajout…' : 'Ajouter'}</Button>
    </form>
  )
}

function ObligationRow({ obligation, onChanged }) {
  const [echeances, setEcheances] = useState(obligation.echeances || [])

  const genererEcheancier = async () => {
    try {
      // NTFIN48 — la vue renvoie la LISTE des échéances directement (pas une
      // enveloppe {echeances:...}) : EcheancierReconnaissanceSerializer(many=True).
      const res = await comptaApi.obligationsPerformance.genererEcheancier(obligation.id, {})
      setEcheances(Array.isArray(res.data) ? res.data : [])
      toast.success('Échéancier généré.')
      onChanged?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Génération impossible.'))
    }
  }

  const reconnaitre = async (echeanceId) => {
    try {
      await comptaApi.echeancesReconnaissance.reconnaitre(echeanceId)
      toast.success('Revenu reconnu — écriture postée.')
      onChanged?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Reconnaissance impossible.'))
    }
  }

  return (
    <div className="rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-medium">{obligation.libelle}</p>
          <p className="text-xs text-muted-foreground">
            {obligation.methode_display || obligation.methode_reconnaissance} — Prix alloué : {formatMAD(obligation.prix_alloue)} —
            {' '}Reconnu : {formatMAD(obligation.montant_reconnu)}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={genererEcheancier}>
          <CalendarPlus className="size-4" /> Générer l’échéancier
        </Button>
      </div>
      {echeances.length > 0 && (
        <div className="mt-2">
          <ComptaTable
            aria-label={`Échéances — ${obligation.libelle}`}
            rows={echeances}
            getRowKey={(e) => e.id}
            columns={[
              { key: 'date', label: 'Date', cell: (e) => formatDate(e.date) },
              { key: 'montant', label: 'À reconnaître', align: 'right', numeric: true,
                sortValue: (e) => Number(e.montant_a_reconnaitre) || 0,
                cell: (e) => formatMAD(e.montant_a_reconnaitre) },
              { key: 'statut', label: 'Statut', cell: (e) => (e.statut === 'reconnu' ? 'Reconnu' : 'Planifié') },
              { key: 'action', label: '', cell: (e) => (e.statut !== 'reconnu' ? (
                <Button size="sm" variant="ghost" onClick={() => reconnaitre(e.id)}>
                  <CheckCircle2 className="size-4" /> Reconnaître
                </Button>
              ) : null) },
            ]}
          />
        </div>
      )}
    </div>
  )
}

function ContratDialog({ contrat, onClose, onChanged }) {
  const [detail, setDetail] = useState(contrat)
  const [allouant, setAllouant] = useState(false)

  const refresh = async () => {
    const res = await comptaApi.contratsRevenu.get(contrat.id)
    setDetail(res.data)
    onChanged?.()
  }

  const allouer = async () => {
    setAllouant(true)
    try {
      await comptaApi.contratsRevenu.allouer(contrat.id)
      toast.success('Prix de transaction alloué aux obligations.')
      await refresh()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Allocation impossible.'))
    } finally {
      setAllouant(false)
    }
  }

  const obligations = detail.obligations || []
  const sommeAllouee = obligations.reduce((s, o) => s + (Number(o.prix_alloue) || 0), 0)
  const total = Number(detail.montant_transaction) || 0
  const equilibre = obligations.length > 0 && Math.abs(sommeAllouee - total) < 0.01

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{detail.reference || 'Contrat'} — {detail.client_nom}</DialogTitle>
        </DialogHeader>

        <div className="flex items-center justify-between rounded-md border border-border p-3">
          <div className="text-sm">
            <p>Prix de transaction : <strong>{formatMAD(total)}</strong></p>
            <p className={equilibre ? 'text-success' : 'text-muted-foreground'}>
              Σ prix alloué aux obligations : <strong>{formatMAD(sommeAllouee)}</strong>
              {' '}<span>{equilibre ? '(équilibré)' : '(à allouer)'}</span>
            </p>
          </div>
          <Button onClick={allouer} disabled={allouant}>
            <Scale className="size-4" /> {allouant ? 'Allocation…' : 'Allouer le prix'}
          </Button>
        </div>

        {obligations.length === 0 ? (
          <EmptyState title="Aucune obligation" description="Ajoutez une obligation de performance ci-dessous." />
        ) : (
          <div className="flex flex-col gap-2">
            {obligations.map((o) => (
              <ObligationRow key={o.id} obligation={o} onChanged={refresh} />
            ))}
          </div>
        )}

        <AjouterObligationForm contratId={contrat.id} onAdded={refresh} />

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function RevenuIfrs15Page() {
  const [dialog, setDialog] = useState(null)
  const [detailDe, setDetailDe] = useState(null)
  const list = useComptaList(comptaApi.contratsRevenu.list, undefined)

  const columns = [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference || '—',
      cell: (v) => <span className="font-mono text-xs">{v}</span> },
    { id: 'client', header: 'Client', accessor: (r) => r.client_nom || '—' },
    { id: 'montant', header: 'Prix de transaction', accessor: (r) => Number(r.montant_transaction) || 0,
      align: 'right', numeric: true, searchable: false, cell: (v) => formatMAD(v) },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut_display || r.statut },
    { id: 'obligations', header: 'Obligations', accessor: (r) => (r.obligations || []).length, width: 100 },
  ]

  const fields = [
    { name: 'reference', label: 'Référence' },
    { name: 'libelle', label: 'Libellé' },
    { name: 'client_nom', label: 'Client' },
    { name: 'source_devis_ref', label: "Devis d'origine" },
    { name: 'montant_transaction', label: 'Prix de transaction', type: 'number', required: true },
    { name: 'devise', label: 'Devise' },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Reconnaissance du revenu (IFRS 15)</h2>
        <div className="page-header-actions">
          <Button onClick={() => setDialog({ row: null })}><Plus /> Nouveau contrat de revenu</Button>
        </div>
      </div>

      <ListShell
        hideHeader
        title="Contrats de revenu"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => setDetailDe(row)}
        exportName="contrats-revenu"
        emptyTitle="Aucun contrat"
        emptyDescription="Aucun contrat de revenu IFRS 15 pour l'instant."
      />

      {dialog && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title="Nouveau contrat de revenu"
          fields={fields}
          initial={dialog.row}
          onSubmit={(payload) => comptaApi.contratsRevenu.create(payload)}
          onSaved={list.reload}
        />
      )}

      {detailDe && (
        <ContratDialog contrat={detailDe} onClose={() => setDetailDe(null)} onChanged={list.reload} />
      )}
    </div>
  )
}
