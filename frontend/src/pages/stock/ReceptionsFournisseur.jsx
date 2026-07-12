import { useEffect, useMemo, useState } from 'react'
import { PackageCheck, Plus, ReceiptText, Tags } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { openPdfInGesture } from '../../utils/pdfBlob'
import {
  Button, StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// G5 — Réceptions fournisseur (goods-in / entrée de marchandises).
// La confirmation d'une réception incrémente le stock (MouvementStock ENTREE)
// pour les quantités reçues et avance le statut du bon de commande fournisseur.
// Usage INTERNE : aucun prix client-facing n'apparaît ici.

const REC_STATUTS = {
  brouillon: 'Brouillon',
  confirme: 'Confirmé',
  annule: 'Annulé',
}
const statutLabel = (s) => REC_STATUTS[s] || s || ''

// Traduit une erreur serveur DRF en phrase FR lisible (jamais de JSON brut).
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

const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// Quantité restante à recevoir d'une ligne de BCF (jamais négative).
const resteLigne = (l) => Math.max((Number(l.quantite) || 0) - (Number(l.quantite_recue) || 0), 0)

// ── Modal : nouvelle réception depuis un BCF non entièrement reçu ────────────
function NouvelleReception({ bonsRecevables, onClose, onSaved }) {
  const [bonId, setBonId] = useState('')
  const [bon, setBon] = useState(null)
  const [dateReception, setDateReception] = useState('')
  const [note, setNote] = useState('')
  const [saisies, setSaisies] = useState({})   // { ligneCmdId: quantité }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Charge le détail (lignes à jour) du BCF choisi.
  useEffect(() => {
    // Réinitialise l'aperçu quand aucun BCF n'est choisi (reset volontaire).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!bonId) { setBon(null); setSaisies({}); return }
    let active = true
    stockApi.getBonCommandeFournisseur(bonId)
      .then((r) => { if (active) { setBon(r.data); setSaisies({}) } })
      .catch(() => { if (active) setBon(null) })
    return () => { active = false }
  }, [bonId])

  const lignes = bon?.lignes ?? []

  const toutRecevoir = () => {
    const next = {}
    for (const l of lignes) {
      const reste = resteLigne(l)
      if (reste > 0) next[l.id] = String(reste)
    }
    setSaisies(next)
  }

  const submit = async (confirmer) => {
    setError(null)
    const payloadLignes = lignes
      .map((l) => {
        const reste = resteLigne(l)
        const qte = Math.min(Math.floor(Number(saisies[l.id])), reste)
        return Number.isFinite(qte) && qte > 0
          ? { ligne_commande: l.id, quantite: qte }
          : null
      })
      .filter(Boolean)
    if (!bonId) { setError('Choisissez un bon de commande.'); return }
    if (payloadLignes.length === 0) {
      setError('Saisissez au moins une quantité à réceptionner.'); return
    }
    setBusy(true)
    try {
      const r = await stockApi.createReceptionFournisseur({
        bon_commande: Number(bonId),
        date_reception: dateReception || null,
        note: note || null,
        lignes: payloadLignes,
      })
      if (confirmer) await stockApi.confirmerReceptionFournisseur(r.data.id)
      onSaved?.(confirmer
        ? 'Réception confirmée — le stock a été incrémenté.'
        : 'Réception enregistrée en brouillon.')
      onClose()
    } catch (err) {
      setError(frError(err, "L'enregistrement de la réception a échoué."))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle réception fournisseur</DialogTitle>
          <DialogDescription>
            Saisissez les quantités effectivement reçues. À la confirmation,
            le stock est incrémenté et le bon de commande avance vers reçu /
            partiellement reçu. Donnée interne.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="rec-bon">Bon de commande</label>
            <Select value={bonId ? String(bonId) : '__none'}
                    onValueChange={(v) => setBonId(v === '__none' ? '' : v)}>
              <SelectTrigger id="rec-bon"><SelectValue placeholder="— Choisir un bon de commande —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Choisir un bon de commande —</SelectItem>
                {bonsRecevables.map((b) => (
                  <SelectItem key={b.id} value={String(b.id)}>
                    {b.reference}{b.fournisseur_nom ? ` · ${b.fournisseur_nom}` : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="rec-date">Date de réception</label>
            <Input id="rec-date" type="date" value={dateReception}
                   onChange={(e) => setDateReception(e.target.value)} />
          </div>
        </div>

        {bon && (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold">Lignes à réceptionner</span>
              <Button type="button" variant="outline" size="sm" onClick={toutRecevoir}>
                Tout recevoir
              </Button>
            </div>
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full min-w-[34rem] text-sm">
                <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold">Article</th>
                    <th className="px-3 py-2 text-left font-semibold">Commandé</th>
                    <th className="px-3 py-2 text-left font-semibold">Déjà reçu</th>
                    <th className="px-3 py-2 text-left font-semibold">Reste</th>
                    <th className="px-3 py-2 text-left font-semibold">À recevoir</th>
                  </tr>
                </thead>
                <tbody>
                  {lignes.map((l) => {
                    const reste = resteLigne(l)
                    return (
                      <tr key={l.id} className="border-t border-border">
                        <td className="px-3 py-2">
                          {l.produit_nom}{l.produit_sku ? ` (${l.produit_sku})` : ''}
                        </td>
                        <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
                        <td className="px-3 py-2 tabular-nums">{l.quantite_recue ?? 0}</td>
                        <td className="px-3 py-2 tabular-nums">{reste}</td>
                        <td className="px-3 py-2">
                          {reste > 0 ? (
                            <Input type="number" min="0" max={reste} inputMode="numeric" className="h-9 w-24"
                                   placeholder={`/${reste}`}
                                   value={saisies[l.id] ?? ''}
                                   onChange={(e) => setSaisies((s) => ({ ...s, [l.id]: e.target.value }))} />
                          ) : <span className="text-xs text-muted-foreground">soldée</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="rec-note">Note</label>
          <Textarea id="rec-note" rows={2} value={note}
                    onChange={(e) => setNote(e.target.value)} />
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter className="flex-wrap">
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" variant="outline" loading={busy} onClick={() => submit(false)}>
            {busy ? '…' : 'Enregistrer en brouillon'}
          </Button>
          <Button type="button" variant="success" loading={busy} onClick={() => submit(true)}>
            {busy ? '…' : 'Confirmer la réception'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal : consultation d'une réception + confirmation d'un brouillon ───────
// Export nommé : testé directement (WR4 — « facturer cette réception »).
export function ReceptionDetail({ reception, onClose, onSaved }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [factureInfo, setFactureInfo] = useState(null)
  const [labelsBusy, setLabelsBusy] = useState(false)
  const lignes = reception?.lignes ?? []
  const isBrouillon = reception?.statut === 'brouillon'
  const isConfirme = reception?.statut === 'confirme'

  const confirmer = async () => {
    setBusy(true); setError(null)
    try {
      await stockApi.confirmerReceptionFournisseur(reception.id)
      onSaved?.('Réception confirmée — le stock a été incrémenté.')
      onClose()
    } catch (err) {
      setError(frError(err, 'La confirmation a échoué.'))
    } finally { setBusy(false) }
  }

  const annuler = async () => {
    if (!window.confirm('Annuler cette réception ?')) return
    setBusy(true); setError(null)
    try {
      await stockApi.annulerReceptionFournisseur(reception.id)
      onSaved?.('Réception annulée.')
      onClose()
    } catch (err) {
      setError(frError(err, "L'annulation a échoué."))
    } finally { setBusy(false) }
  }

  // WR4 / FG56 — « facturer cette réception » : crée une facture fournisseur
  // à partir de la réception confirmée (montants dérivés des lignes du BCF).
  const facturer = async () => {
    setBusy(true); setError(null); setFactureInfo(null)
    try {
      const r = await stockApi.facturerReception(reception.id)
      const ff = r.data ?? {}
      setFactureInfo(`Facture fournisseur ${ff.reference ?? ''} créée (${
        formatMAD(ff.montant_ttc ?? 0)} TTC).`)
      onSaved?.()
    } catch (err) {
      setError(frError(err, 'La facturation de la réception a échoué.'))
    } finally { setBusy(false) }
  }

  // ZSTK6 — planche d'étiquettes lot/série imprimable : une étiquette par
  // numéro de série reçu + une par lot renseigné sur cette réception.
  const aSerieOuLot = lignes.some(
    (l) => (l.numeros_serie ?? []).length > 0 || l.numero_lot)
  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const imprimerEtiquettes = async () => {
    const pending = openPdfInGesture()
    setLabelsBusy(true); setError(null)
    try {
      const res = await stockApi.receptionEtiquettes(reception.id)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      if (!pending.deliver(blob, `etiquettes-reception-${reception.id}.pdf`)) {
        setError('Ouverture bloquée par le navigateur.')
      }
    } catch (err) {
      setError(frError(err, "L'impression des étiquettes a échoué."))
    } finally { setLabelsBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            Réception — {reception.reference}
            <StatusPill status={reception.statut} label={statutLabel(reception.statut)} />
          </DialogTitle>
          <DialogDescription>
            BCF {reception.bon_commande_reference ?? '—'}
            {reception.fournisseur_nom ? ` · ${reception.fournisseur_nom}` : ''}
            {' · '}{fmtDateFR(reception.date_reception || reception.date_creation)}
          </DialogDescription>
        </DialogHeader>

        {reception.note && (
          <p className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
            <span className="font-medium">Note : </span>{reception.note}
          </p>
        )}

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[24rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Produit</th>
                <th className="px-3 py-2 text-left font-semibold">Quantité reçue</th>
              </tr>
            </thead>
            <tbody>
              {lignes.length === 0 && (
                <tr><td colSpan={2} className="px-3 py-3 text-muted-foreground">Aucune ligne.</td></tr>
              )}
              {lignes.map((l) => (
                <tr key={l.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    {l.produit_nom}{l.produit_sku ? ` (${l.produit_sku})` : ''}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {factureInfo && (
          <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
            {factureInfo}
          </div>
        )}

        <DialogFooter className="flex-wrap">
          {isBrouillon && (
            <Button type="button" variant="destructive" loading={busy} onClick={annuler}>
              Annuler la réception
            </Button>
          )}
          {isConfirme && (
            <Button type="button" variant="outline" loading={busy} onClick={facturer}
                    title="Créer une facture fournisseur à partir de cette réception (interne)">
              <ReceiptText /> Facturer cette réception
            </Button>
          )}
          {/* ZSTK6 — étiquettes lot/série imprimables (uniquement si des
              numéros de série/lot ont été saisis sur cette réception). */}
          {aSerieOuLot && (
            <Button type="button" variant="outline" loading={labelsBusy} onClick={imprimerEtiquettes}
                    title="Imprimer les étiquettes lot/série de cette réception">
              <Tags /> Étiquettes lot/série
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          {isBrouillon && (
            <Button type="button" variant="success" loading={busy} onClick={confirmer}>
              {busy ? '…' : 'Confirmer (incrémente le stock)'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default function ReceptionsFournisseur() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  const [bons, setBons] = useState([])
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)

  const reload = () => {
    stockApi.getReceptionsFournisseur({ ordering: '-date_creation' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des réceptions impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getBonsCommandeFournisseur({ page_size: 1000 })
      .then((r) => setBons(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  // Bons recevables : envoyés et pas encore entièrement reçus.
  const bonsRecevables = useMemo(
    () => bons.filter((b) => b.statut === 'envoye' && !b.est_entierement_recu),
    [bons])

  const openReception = async (r) => {
    try {
      const resp = await stockApi.getReceptionFournisseur(r.id)
      setSelected(resp.data)
    } catch { setSelected(r) }
  }

  const onSaved = (msg) => { reload(); if (msg) setInfo(msg) }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', minWidth: 140,
      accessor: (r) => r.reference ?? '' },
    { id: 'bon_commande_reference', header: 'BCF', width: 140,
      accessor: (r) => r.bon_commande_reference ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 160,
      accessor: (r) => r.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'statut', header: 'Statut', width: 120, searchable: false,
      accessor: (r) => r.statut,
      cell: (v) => <StatusPill status={v} label={statutLabel(v)} /> },
    { id: 'date', header: 'Date', width: 120, searchable: false,
      accessor: (r) => r.date_reception || r.date_creation,
      cell: (v) => fmtDateFR(v) },
    { id: 'total_recu', header: 'Articles reçus', align: 'right', width: 120, searchable: false,
      accessor: (r) => r.total_recu ?? 0 },
  ], [])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-2">
          <PackageCheck className="size-5 text-muted-foreground" aria-hidden="true" />
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight">Réceptions fournisseur</h1>
            <p className="text-sm text-muted-foreground">{items.length} réception(s)</p>
          </div>
        </div>
        <Button onClick={() => setCreating(true)} disabled={bonsRecevables.length === 0}
                title={bonsRecevables.length === 0
                  ? 'Aucun bon de commande envoyé à réceptionner'
                  : undefined}>
          <Plus /> Nouvelle réception
        </Button>
      </header>

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
        getRowId={(r) => r.id}
        searchPlaceholder="Rechercher (référence, BCF, fournisseur)…"
        globalColumns={['reference', 'bon_commande_reference', 'fournisseur_nom']}
        onRowClick={openReception}
        emptyTitle="Aucune réception fournisseur"
        emptyDescription="Créez-en une depuis un bon de commande fournisseur envoyé."
        emptyAction={bonsRecevables.length > 0
          ? <Button size="sm" onClick={() => setCreating(true)}><Plus className="size-4" /> Nouvelle réception</Button>
          : undefined}
        aria-label="Réceptions fournisseur"
      />

      {creating && (
        <NouvelleReception bonsRecevables={bonsRecevables}
                           onClose={() => setCreating(false)} onSaved={onSaved} />
      )}
      {selected && (
        <ReceptionDetail reception={selected}
                         onClose={() => setSelected(null)} onSaved={onSaved} />
      )}
    </div>
  )
}
