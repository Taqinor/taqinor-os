import { useEffect, useMemo, useState } from 'react'
import { ReceiptText, Plus, FileText, Building2 } from 'lucide-react'
import stockApi from '../../api/stockApi'
import comptaApi from '../../api/comptaApi'
import { formatMAD } from '../../lib/format'
import {
  Button, StatusPill, DataTable, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { ouvrirPdfBlob, estBlobPdf, messageErreurBlob } from '../../utils/pdfBlob'

// G5 — Factures fournisseur / comptes à payer (AP).
// Le solde dû = TTC − Σ paiements ; le statut de règlement est recalculé à
// chaque paiement côté serveur. Usage INTERNE (montants d'achat jamais
// client-facing) — ce module n'a aucun rendu destiné au client.

const FF_STATUTS = {
  a_payer: 'À payer',
  partiellement_payee: 'Partiellement payée',
  payee: 'Payée',
}
const statutLabel = (s) => FF_STATUTS[s] || s || ''

const MODES = {
  virement: 'Virement',
  cheque: 'Chèque',
  especes: 'Espèces',
  carte: 'Carte',
  effet: 'Effet / traite',
  autre: 'Autre',
}

function frError(err, fallback = 'Une erreur est survenue. Réessayez.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  if (Array.isArray(data.non_field_errors) && data.non_field_errors[0]) return data.non_field_errors[0]
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

const fmtMad = (v) => formatMAD(v)
const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// ── Modal : création d'une facture fournisseur ──────────────────────────────
function NouvelleFacture({ fournisseurs, bons, onClose, onSaved }) {
  const [fournisseur, setFournisseur] = useState('')
  const [bonCommande, setBonCommande] = useState('')
  const [refFournisseur, setRefFournisseur] = useState('')
  const [dateFacture, setDateFacture] = useState('')
  const [dateEcheance, setDateEcheance] = useState('')
  const [montantHt, setMontantHt] = useState('')
  const [montantTva, setMontantTva] = useState('')
  const [montantTtc, setMontantTtc] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Aide : TTC = HT + TVA quand l'utilisateur n'a pas saisi de TTC à la main.
  const onHt = (v) => {
    setMontantHt(v)
    const ttc = (Number(v) || 0) + (Number(montantTva) || 0)
    if (ttc > 0) setMontantTtc(String(ttc))
  }
  const onTva = (v) => {
    setMontantTva(v)
    const ttc = (Number(montantHt) || 0) + (Number(v) || 0)
    if (ttc > 0) setMontantTtc(String(ttc))
  }

  const submit = async () => {
    setError(null)
    if (!fournisseur) { setError('Choisissez un fournisseur.'); return }
    if (!(Number(montantTtc) > 0)) { setError('Saisissez un montant TTC positif.'); return }
    setBusy(true)
    try {
      await stockApi.createFactureFournisseur({
        fournisseur: Number(fournisseur),
        bon_commande: bonCommande ? Number(bonCommande) : null,
        ref_fournisseur: refFournisseur || null,
        date_facture: dateFacture || null,
        date_echeance: dateEcheance || null,
        montant_ht: Number(montantHt) || 0,
        montant_tva: Number(montantTva) || 0,
        montant_ttc: Number(montantTtc) || 0,
        note: note || null,
      })
      onSaved?.('Facture fournisseur enregistrée.')
      onClose()
    } catch (err) {
      setError(frError(err, "L'enregistrement de la facture a échoué."))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle facture fournisseur</DialogTitle>
          <DialogDescription>
            Document d&apos;achat reçu d&apos;un fournisseur. Donnée interne :
            les montants d&apos;achat n&apos;apparaissent jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-fou">Fournisseur</label>
            <Select value={fournisseur ? String(fournisseur) : '__none'}
                    onValueChange={(v) => setFournisseur(v === '__none' ? '' : v)}>
              <SelectTrigger id="ff-fou"><SelectValue placeholder="— Choisir —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Choisir un fournisseur —</SelectItem>
                {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-bon">Bon de commande (optionnel)</label>
            <Select value={bonCommande ? String(bonCommande) : '__none'}
                    onValueChange={(v) => setBonCommande(v === '__none' ? '' : v)}>
              <SelectTrigger id="ff-bon"><SelectValue placeholder="— Aucun —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Aucun —</SelectItem>
                {bons.map((b) => (
                  <SelectItem key={b.id} value={String(b.id)}>{b.reference}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-ref">N° facture fournisseur</label>
            <Input id="ff-ref" value={refFournisseur}
                   onChange={(e) => setRefFournisseur(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-datef">Date de facture</label>
            <Input id="ff-datef" type="date" value={dateFacture}
                   onChange={(e) => setDateFacture(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-datee">Date d&apos;échéance</label>
            <Input id="ff-datee" type="date" value={dateEcheance}
                   onChange={(e) => setDateEcheance(e.target.value)} />
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-ht">Montant HT</label>
            <Input id="ff-ht" type="number" step="any" inputMode="decimal"
                   value={montantHt} onChange={(e) => onHt(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-tva">TVA</label>
            <Input id="ff-tva" type="number" step="any" inputMode="decimal"
                   value={montantTva} onChange={(e) => onTva(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="ff-ttc">Montant TTC</label>
            <Input id="ff-ttc" type="number" step="any" inputMode="decimal"
                   value={montantTtc} onChange={(e) => setMontantTtc(e.target.value)} />
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="ff-note">Note</label>
          <Textarea id="ff-note" rows={2} value={note}
                    onChange={(e) => setNote(e.target.value)} />
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} onClick={submit}>
            {busy ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal : détail d'une facture + saisie de paiements ──────────────────────
// Export nommé : testé directement (WR4 — PDF facture fournisseur).
export function FactureDetail({ facture: factureProp, onClose, onSaved }) {
  const [facture, setFacture] = useState(factureProp)
  const [montant, setMontant] = useState('')
  const [datePaiement, setDatePaiement] = useState('')
  const [mode, setMode] = useState('virement')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const paiements = facture?.paiements ?? []
  const solde = Number(facture?.solde_du) || 0

  const reglerSolde = () => setMontant(solde > 0 ? String(solde) : '')

  const ajouter = async () => {
    setError(null)
    if (!(Number(montant) > 0)) { setError('Saisissez un montant positif.'); return }
    setBusy(true)
    try {
      const r = await stockApi.ajouterPaiementFournisseur(facture.id, {
        montant: Number(montant),
        date_paiement: datePaiement || null,
        mode,
      })
      setFacture(r.data)
      setMontant('')
      onSaved?.()
    } catch (err) {
      setError(frError(err, "L'enregistrement du paiement a échoué."))
    } finally { setBusy(false) }
  }

  // XACC33 — Capitalise une ligne de la facture en immobilisation (bouton
  // « Immobiliser »). Pas d'écran de lignes ici : on demande le ligne_id
  // ponctuellement (module interne), puis on route via /compta/.
  const [immobilising, setImmobilising] = useState(false)
  const immobiliser = async () => {
    const ligneId = window.prompt(
      'ID de la ligne de facture à immobiliser (voir le détail de la facture) :')
    if (!ligneId) return
    setImmobilising(true)
    try {
      await comptaApi.immobilisations.depuisFactureFournisseur({
        facture_id: facture.id, ligne_id: Number(ligneId),
      })
      toast.success('Immobilisation créée depuis la ligne de facture.')
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Immobilisation impossible.'))
    } finally {
      setImmobilising(false)
    }
  }

  // WR4 / FG55 — PDF de la facture fournisseur (INTERNE) : ouvre dans un
  // nouvel onglet (repli téléchargement), erreur serveur lue depuis le blob.
  const telechargerPdf = async () => {
    setError(null)
    try {
      const r = await stockApi.factureFournisseurPdf(facture.id)
      if (!estBlobPdf(r.data)) {
        setError('Le serveur n\'a pas renvoyé de PDF (réponse inattendue).')
        return
      }
      ouvrirPdfBlob(r.data, `${facture.reference ?? 'facture-fournisseur'}.pdf`)
    } catch (err) {
      setError(await messageErreurBlob(err, {
        fallback: 'La génération du PDF a échoué. Réessayez.',
      }))
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            Facture — {facture.reference}
            <StatusPill status={facture.statut} label={statutLabel(facture.statut)} />
          </DialogTitle>
          <DialogDescription>
            {facture.fournisseur_nom ?? '—'}
            {facture.ref_fournisseur ? ` · N° ${facture.ref_fournisseur}` : ''}
            {facture.bon_commande_reference ? ` · BCF ${facture.bon_commande_reference}` : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 rounded-lg border border-border bg-muted/30 p-3 text-sm sm:grid-cols-3">
          <div><span className="text-muted-foreground">Total TTC</span><div className="font-semibold tabular-nums">{fmtMad(facture.montant_ttc)}</div></div>
          <div><span className="text-muted-foreground">Déjà payé</span><div className="font-semibold tabular-nums">{fmtMad(facture.total_paye)}</div></div>
          <div><span className="text-muted-foreground">Solde dû</span><div className="font-bold tabular-nums text-warning">{fmtMad(facture.solde_du)}</div></div>
          <div className="sm:col-span-3 text-xs text-muted-foreground">
            Échéance : {fmtDateFR(facture.date_echeance)}
            {facture.date_facture ? ` · Facture du ${fmtDateFR(facture.date_facture)}` : ''}
          </div>
        </div>

        {/* Paiements existants */}
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Paiements</span>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[24rem] text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold">Date</th>
                  <th className="px-3 py-2 text-left font-semibold">Mode</th>
                  <th className="px-3 py-2 text-right font-semibold">Montant</th>
                </tr>
              </thead>
              <tbody>
                {paiements.length === 0 && (
                  <tr><td colSpan={3} className="px-3 py-3 text-muted-foreground">Aucun paiement.</td></tr>
                )}
                {paiements.map((p) => (
                  <tr key={p.id} className="border-t border-border">
                    <td className="px-3 py-2">{fmtDateFR(p.date_paiement || p.date_creation)}</td>
                    <td className="px-3 py-2">{MODES[p.mode] || p.mode}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{fmtMad(p.montant)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Saisie d'un nouveau paiement (si solde restant) */}
        {solde > 0 && (
          <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
            <span className="text-sm font-semibold">Enregistrer un paiement</span>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium" htmlFor="pay-montant">Montant</label>
                <Input id="pay-montant" type="number" step="any" inputMode="decimal" className="h-9"
                       value={montant} onChange={(e) => setMontant(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium" htmlFor="pay-date">Date</label>
                <Input id="pay-date" type="date" className="h-9"
                       value={datePaiement} onChange={(e) => setDatePaiement(e.target.value)} />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium" htmlFor="pay-mode">Mode</label>
                <Select value={mode} onValueChange={setMode}>
                  <SelectTrigger id="pay-mode" className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(MODES).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="outline" size="sm" onClick={reglerSolde}>
                Régler le solde ({fmtMad(solde)})
              </Button>
              <Button type="button" size="sm" loading={busy} onClick={ajouter}>
                {busy ? '…' : 'Ajouter le paiement'}
              </Button>
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter className="flex-wrap">
          <Button type="button" variant="outline" loading={immobilising} onClick={immobiliser}>
            <Building2 /> Immobiliser
          </Button>
          <Button type="button" variant="outline" onClick={telechargerPdf}>
            <FileText /> PDF (interne)
          </Button>
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function FacturesFournisseur() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [fournisseurs, setFournisseurs] = useState([])
  const [bons, setBons] = useState([])
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)
  // Filtre « comptes à payer » : n'affiche que les factures non soldées.
  const [aPayerSeul, setAPayerSeul] = useState(false)
  const [totalDu, setTotalDu] = useState(null)

  const reload = () => {
    setLoading(true)
    const fetch = aPayerSeul
      ? stockApi.getComptesAPayer().then((r) => {
          setTotalDu(r.data?.total_du ?? null)
          return r.data?.results ?? []
        })
      : stockApi.getFacturesFournisseur({ ordering: '-date_creation' })
          .then((r) => { setTotalDu(null); return r.data?.results ?? r.data ?? [] })
    fetch
      .then((rows) => setItems(rows))
      .catch(() => setError('Chargement des factures impossible.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { reload() }, [aPayerSeul])

  useEffect(() => {
    stockApi.getFournisseurs({ page_size: 1000 })
      .then((r) => setFournisseurs(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getBonsCommandeFournisseur({ page_size: 1000 })
      .then((r) => setBons(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  const openFacture = async (f) => {
    try {
      const resp = await stockApi.getFactureFournisseur(f.id)
      setSelected(resp.data)
    } catch { setSelected(f) }
  }

  const onSaved = (msg) => { reload(); if (msg) setInfo(msg) }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', minWidth: 130,
      accessor: (f) => f.reference ?? '' },
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 150,
      accessor: (f) => f.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'ref_fournisseur', header: 'N° fournisseur', width: 130,
      accessor: (f) => f.ref_fournisseur ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'date_echeance', header: 'Échéance', width: 110, searchable: false,
      accessor: (f) => f.date_echeance,
      cell: (v) => fmtDateFR(v) },
    { id: 'statut', header: 'Statut', width: 150, searchable: false,
      accessor: (f) => f.statut,
      cell: (v) => <StatusPill status={v} label={statutLabel(v)} /> },
    { id: 'montant_ttc', header: 'Total TTC', align: 'right', width: 130, searchable: false,
      accessor: (f) => f.montant_ttc,
      cell: (v) => fmtMad(v) },
    { id: 'solde_du', header: 'Solde dû', align: 'right', width: 130, searchable: false,
      accessor: (f) => f.solde_du,
      cell: (v) => <span className={Number(v) > 0 ? 'font-semibold text-warning' : ''}>{fmtMad(v)}</span> },
  ], [])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <ReceiptText className="size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight">Factures fournisseur</h1>
            <p className="text-sm text-muted-foreground">
              {items.length} facture(s)
              {aPayerSeul && totalDu != null && ` · ${fmtMad(totalDu)} à payer`}
            </p>
          </div>
        </div>
        <Button onClick={() => setCreating(true)}>
          <Plus /> Nouvelle facture
        </Button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant={aPayerSeul ? 'secondary' : 'outline'} size="sm"
                onClick={() => setAPayerSeul((v) => !v)}
                title="N'afficher que les factures non soldées">
          Comptes à payer{aPayerSeul ? ' (actif)' : ''}
        </Button>
        {aPayerSeul && (
          <Button variant="ghost" size="sm" onClick={() => setAPayerSeul(false)}>
            Toutes les factures
          </Button>
        )}
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {info && (
        <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
          {info}
        </div>
      )}

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(f) => f.id}
        searchPlaceholder="Rechercher (référence, fournisseur)…"
        globalColumns={['reference', 'fournisseur_nom', 'ref_fournisseur']}
        onRowClick={openFacture}
        emptyTitle={aPayerSeul ? 'Aucune facture à payer' : 'Aucune facture fournisseur'}
        emptyDescription="Enregistrez une facture reçue d'un fournisseur avec « Nouvelle facture »."
        emptyAction={<Button size="sm" onClick={() => setCreating(true)}><Plus className="size-4" /> Nouvelle facture</Button>}
        aria-label="Factures fournisseur"
      />

      {creating && (
        <NouvelleFacture fournisseurs={fournisseurs} bons={bons}
                         onClose={() => setCreating(false)} onSaved={onSaved} />
      )}
      {selected && (
        <FactureDetail facture={selected}
                       onClose={() => setSelected(null)} onSaved={onSaved} />
      )}
    </div>
  )
}
