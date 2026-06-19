import { useEffect, useMemo, useState } from 'react'
import { Plus, FileText, Undo2, Package, Trash2 } from 'lucide-react'
import stockApi from '../../api/stockApi'
import ProduitPicker from '../../components/ProduitPicker'
import { downloadBlob } from '../../utils/downloadBlob'
import {
  Button, IconButton, StatusPill, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import {
  BCF_STATUTS,
  bcfStatutLabel,
  totalAchat,
  quantiteRestante,
  buildReceptionPayload,
  avancementReception,
  bcfDateAffichee,
  aLignePrixZero,
  nbEnvoyesNonRecus,
} from '../../features/stock/procurement'

// Page de gestion des bons de commande FOURNISSEUR (achats — N11).
// Le prix d'ACHAT est INTERNE : cette page n'est jamais un document client.

// Traduit une erreur serveur DRF en phrase FR lisible (jamais de JSON brut).
function frBcfError(err, fallback = 'Une erreur est survenue. Réessayez.') {
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

const fmtMad = (v) => {
  const n = Number(v) || 0
  return `${n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MAD`
}
const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

// ── N19 — Modal de retour fournisseur (créé + validé depuis un BCF) ──────────
// La validation décrémente le stock. Lien automatique vers le BCF d'origine.
function RetourModal({ bcf, onClose, onDone }) {
  const [saisies, setSaisies] = useState({})   // { ligneId: { qte, motif } }
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const lignes = bcf?.lignes ?? []

  const setLigne = (id, patch) =>
    setSaisies((s) => ({ ...s, [id]: { ...(s[id] ?? {}), ...patch } }))

  const submit = async () => {
    setError(null)
    const payloadLignes = lignes
      .map((l) => {
        const s = saisies[l.id] ?? {}
        // Plafonne au reçu : on ne retourne jamais plus que ce qui a été reçu.
        const qte = Math.min(Math.floor(Number(s.qte)), Number(l.quantite_recue) || 0)
        return Number.isFinite(qte) && qte > 0
          ? { produit: l.produit, quantite: qte, motif: s.motif || '' }
          : null
      })
      .filter(Boolean)
    if (payloadLignes.length === 0) {
      setError('Saisissez au moins une quantité à retourner.'); return
    }
    setBusy(true)
    try {
      const r = await stockApi.createRetourFournisseur({
        fournisseur: bcf.fournisseur, bon_commande: bcf.id,
        lignes: payloadLignes,
      })
      await stockApi.validerRetourFournisseur(r.data.id)
      onDone?.('Retour fournisseur enregistré — le stock a été décrémenté.')
      onClose()
    } catch (err) {
      setError(frBcfError(err, 'Échec du retour fournisseur.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Retour fournisseur — {bcf.reference}</DialogTitle>
          <DialogDescription>
            Articles défectueux ou erronés. À la validation, le stock est décrémenté.
            Donnée interne (prix d&apos;achat jamais client-facing).
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Produit</th>
                <th className="px-3 py-2 text-left font-semibold">Reçu</th>
                <th className="px-3 py-2 text-left font-semibold">À retourner</th>
                <th className="px-3 py-2 text-left font-semibold">Motif</th>
              </tr>
            </thead>
            <tbody>
              {lignes.map((l) => (
                <tr key={l.id} className="border-t border-border">
                  <td className="px-3 py-2">{l.produit_nom}</td>
                  <td className="px-3 py-2 tabular-nums">{l.quantite_recue}</td>
                  <td className="px-3 py-2">
                    <Input type="number" min="0" max={l.quantite_recue ?? 0} inputMode="numeric" className="h-9 w-24"
                           value={saisies[l.id]?.qte ?? ''}
                           onChange={(e) => setLigne(l.id, { qte: e.target.value })} />
                    {Number(saisies[l.id]?.qte) > (Number(l.quantite_recue) || 0) && (
                      <p className="mt-1 text-xs text-warning">
                        Max {l.quantite_recue ?? 0} (quantité reçue)
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <Input className="h-9"
                           value={saisies[l.id]?.motif ?? ''}
                           placeholder="ex. cassé à la livraison"
                           onChange={(e) => setLigne(l.id, { motif: e.target.value })} />
                  </td>
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

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} onClick={submit}>
            {busy ? 'Enregistrement…' : 'Valider le retour'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal de création / consultation / réception d'un BCF ──
function BcfDetail({ bcf, fournisseurs, produits, onClose, onSaved }) {
  const isNew = !bcf?.id
  const statut = bcf?.statut ?? 'brouillon'
  const editableLignes = isNew || statut === 'brouillon'

  const [fournisseur, setFournisseur] = useState(bcf?.fournisseur ?? '')
  const [dateCommande, setDateCommande] = useState(bcf?.date_commande ?? '')
  const [note, setNote] = useState(bcf?.note ?? '')
  const [lignes, setLignes] = useState(
    (bcf?.lignes ?? []).map((l) => ({ ...l })))
  // Saisies de réception : { [ligneId]: quantité }
  const [receptions, setReceptions] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [showRetour, setShowRetour] = useState(false)
  const [info, setInfo] = useState(null)

  const total = useMemo(() => totalAchat(lignes), [lignes])
  const reception = useMemo(() => avancementReception(bcf?.lignes ?? lignes), [bcf, lignes])

  const setLigne = (idx, patch) =>
    setLignes((ls) => ls.map((l, i) => (i === idx ? { ...l, ...patch } : l)))
  const addLigne = () =>
    setLignes((ls) => [...ls, { produit: '', quantite: 1, prix_achat_unitaire: '' }])
  const removeLigne = (idx) =>
    setLignes((ls) => ls.filter((_, i) => i !== idx))

  const buildPayload = () => ({
    fournisseur: fournisseur || null,
    date_commande: dateCommande || null,
    note: note || null,
    lignes: lignes
      .filter((l) => l.produit)
      .map((l) => ({
        produit: l.produit,
        quantite: Number(l.quantite) || 0,
        prix_achat_unitaire: l.prix_achat_unitaire === '' || l.prix_achat_unitaire == null
          ? 0 : Number(l.prix_achat_unitaire),
      })),
  })

  const save = async () => {
    setError(null)
    const payload = buildPayload()
    if (!payload.fournisseur) { setError('Choisissez un fournisseur.'); return }
    if (payload.lignes.length === 0) { setError('Ajoutez au moins une ligne.'); return }
    setBusy(true)
    try {
      if (isNew) await stockApi.createBonCommandeFournisseur(payload)
      else await stockApi.updateBonCommandeFournisseur(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'enregistrement du bon de commande a échoué."))
    } finally { setBusy(false) }
  }

  const envoyer = async () => {
    // Confirme l'envoi si une ligne a un prix d'achat à 0 (pompes/placeholder).
    if (aLignePrixZero(buildPayload().lignes)
        && !window.confirm('Une ou plusieurs lignes ont un prix d\'achat à 0. Envoyer quand même ?')) {
      return
    }
    setBusy(true); setError(null)
    try {
      // En brouillon, on enregistre d'abord d'éventuelles modifications.
      if (!isNew) await stockApi.updateBonCommandeFournisseur(bcf.id, buildPayload())
      let id = bcf?.id
      if (isNew) {
        const r = await stockApi.createBonCommandeFournisseur(buildPayload())
        id = r.data.id
      }
      await stockApi.envoyerBcf(id)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'envoi au fournisseur a échoué."))
    } finally { setBusy(false) }
  }

  // Tout recevoir : pré-remplit chaque saisie de réception au reste dû.
  const toutRecevoir = () => {
    const next = {}
    for (const l of bcf?.lignes ?? []) {
      const reste = quantiteRestante(l)
      if (reste > 0) next[l.id] = String(reste)
    }
    setReceptions(next)
  }

  const recevoir = async () => {
    const payload = buildReceptionPayload(bcf.lignes, receptions)
    if (payload.length === 0) { setError('Saisissez au moins une quantité à recevoir.'); return }
    setBusy(true); setError(null)
    try {
      await stockApi.recevoirBcf(bcf.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, 'La réception a échoué.'))
    } finally { setBusy(false) }
  }

  const annuler = async () => {
    if (!window.confirm('Annuler ce bon de commande ?')) return
    setBusy(true); setError(null)
    try {
      await stockApi.annulerBcf(bcf.id)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frBcfError(err, "L'annulation a échoué."))
    } finally { setBusy(false) }
  }

  const telechargerPdf = async () => {
    try {
      const r = await stockApi.bcfPdf(bcf.id)
      downloadBlob(r.data, `${bcf.reference ?? 'BCF'}.pdf`)
    } catch { setError('PDF indisponible.') }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {isNew ? 'Nouveau bon de commande fournisseur'
              : `Bon de commande — ${bcf.reference ?? ''}`}
            {!isNew && <StatusPill status={statut} label={bcfStatutLabel(statut)} />}
          </DialogTitle>
          <DialogDescription>
            Document <strong>interne</strong> : les prix d&apos;achat n&apos;apparaissent
            jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-fou">Fournisseur</label>
            <Select value={fournisseur ? String(fournisseur) : '__none'} disabled={!editableLignes}
                    onValueChange={(v) => setFournisseur(v === '__none' ? '' : v)}>
              <SelectTrigger id="bcf-fou"><SelectValue placeholder="— Choisir un fournisseur —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Choisir un fournisseur —</SelectItem>
                {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="bcf-date">Date de commande</label>
            <Input id="bcf-date" type="date" value={dateCommande ?? ''}
                   disabled={!editableLignes}
                   onChange={(e) => setDateCommande(e.target.value)} />
          </div>
        </div>

        {/* ── Lignes ── */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
              <Package className="size-4 text-muted-foreground" /> Lignes
            </span>
            <div className="flex items-center gap-2">
              {!isNew && (statut === 'envoye' || statut === 'recu') && reception.commande > 0 && (
                <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                  {reception.recu}/{reception.commande} reçus
                  <span className="inline-block h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                    <span className="block h-full bg-success"
                          style={{ width: `${Math.round(reception.taux * 100)}%` }} />
                  </span>
                </span>
              )}
              {!isNew && statut === 'envoye' && (
                <Button type="button" variant="outline" size="sm" onClick={toutRecevoir}>
                  Tout recevoir
                </Button>
              )}
              {editableLignes && (
                <Button type="button" variant="outline" size="sm" onClick={addLigne}>
                  <Plus /> Ajouter une ligne
                </Button>
              )}
            </div>
          </div>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold" style={{ minWidth: 220 }}>Article</th>
                  <th className="px-3 py-2 text-left font-semibold">Quantité</th>
                  <th className="px-3 py-2 text-left font-semibold">Prix achat U. (interne)</th>
                  <th className="px-3 py-2 text-left font-semibold">Total HT</th>
                  {!isNew && <th className="px-3 py-2 text-left font-semibold">Reçu</th>}
                  {!isNew && statut === 'envoye' && <th className="px-3 py-2 text-left font-semibold">À recevoir</th>}
                  {editableLignes && <th className="w-10 px-3 py-2" />}
                </tr>
              </thead>
              <tbody>
                {lignes.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-3 text-sm text-muted-foreground">Aucune ligne.</td></tr>
                )}
                {lignes.map((l, idx) => {
                  const lineTotal = (Number(l.quantite) || 0) * (Number(l.prix_achat_unitaire) || 0)
                  const restante = quantiteRestante(l)
                  return (
                    <tr key={l.id ?? `new-${idx}`} className="border-t border-border">
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          <ProduitPicker produits={produits} value={l.produit}
                                         onChange={(v) => setLigne(idx, { produit: v })} />
                        ) : (
                          <span>{l.produit_nom ?? '—'}{l.produit_sku ? ` (${l.produit_sku})` : ''}</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          <Input type="number" step="any" inputMode="decimal" className="h-9 w-24"
                                 value={l.quantite ?? ''}
                                 onChange={(e) => setLigne(idx, { quantite: e.target.value })} />
                        ) : l.quantite}
                      </td>
                      <td className="px-3 py-2">
                        {editableLignes ? (
                          <Input type="number" step="any" inputMode="decimal" className="h-9 w-32"
                                 value={l.prix_achat_unitaire ?? ''}
                                 onChange={(e) => setLigne(idx, { prix_achat_unitaire: e.target.value })} />
                        ) : fmtMad(l.prix_achat_unitaire)}
                      </td>
                      <td className="px-3 py-2 tabular-nums">{fmtMad(lineTotal)}</td>
                      {!isNew && <td className="px-3 py-2 tabular-nums">{l.quantite_recue ?? 0}</td>}
                      {!isNew && statut === 'envoye' && (
                        <td className="px-3 py-2">
                          {restante > 0 ? (
                            <Input type="number" min="0" max={restante} inputMode="numeric" className="h-9 w-24"
                                   placeholder={`/${restante}`}
                                   value={receptions[l.id] ?? ''}
                                   onChange={(e) => setReceptions((r) => ({ ...r, [l.id]: e.target.value }))} />
                          ) : <span className="text-xs text-muted-foreground">soldée</span>}
                        </td>
                      )}
                      {editableLignes && (
                        <td className="px-3 py-2">
                          <IconButton label="Retirer la ligne" variant="ghost" size="icon" className="size-8"
                                      onClick={() => removeLigne(idx)}>
                            <Trash2 className="text-destructive" />
                          </IconButton>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="text-right text-sm font-bold">
            Total achat HT (interne) : {fmtMad(total)}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="bcf-note">Note</label>
          <Textarea id="bcf-note" rows={2} value={note ?? ''}
                    disabled={!editableLignes && statut !== 'envoye'}
                    onChange={(e) => setNote(e.target.value)} />
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

        <DialogFooter className="flex-wrap">
          {!isNew && statut !== 'annule' && (
            <Button type="button" variant="outline" onClick={telechargerPdf}>
              <FileText /> PDF (interne)
            </Button>
          )}
          {!isNew && (statut === 'brouillon' || statut === 'envoye') && (
            <Button type="button" variant="destructive" loading={busy} onClick={annuler}>
              Annuler le BC
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          {editableLignes && (
            <>
              <Button type="button" variant="outline" loading={busy} onClick={save}>
                {busy ? '…' : 'Enregistrer'}
              </Button>
              <Button type="button" loading={busy} onClick={envoyer}>
                {busy ? '…' : 'Envoyer au fournisseur'}
              </Button>
            </>
          )}
          {!isNew && statut === 'envoye' && (
            <Button type="button" variant="success" loading={busy} onClick={recevoir}>
              {busy ? '…' : 'Recevoir les quantités'}
            </Button>
          )}
          {!isNew && (statut === 'recu' || statut === 'envoye') && (
            <Button type="button" variant="outline" onClick={() => setShowRetour(true)}
                    title="Retourner des articles défectueux/erronés (décrémente le stock)">
              <Undo2 /> Retour fournisseur
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
      {showRetour && (
        <RetourModal bcf={bcf} onClose={() => setShowRetour(false)}
                     onDone={(msg) => { onSaved?.(); if (msg) setInfo(msg) }} />
      )}
    </Dialog>
  )
}

export default function BonsCommandeFournisseur() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [fournisseurs, setFournisseurs] = useState([])
  const [produits, setProduits] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')
  const [selected, setSelected] = useState(null) // bcf object or {} for new

  // setState arrive dans les callbacks asynchrones (jamais synchrone dans
  // l'effet) : l'état initial loading=true couvre le premier chargement.
  const reload = () => {
    stockApi.getBonsCommandeFournisseur()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getFournisseurs().then((r) => setFournisseurs(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getProduits({ page_size: 1000 }).then((r) => setProduits(r.data?.results ?? r.data ?? [])).catch(() => {})
  }, [])

  // Le filtre statut reste local (Select dédié) ; la recherche texte
  // (référence / fournisseur) est gérée par le DataTable via globalColumns.
  const rows = useMemo(() => (
    statutFiltre ? items.filter((b) => b.statut === statutFiltre) : items
  ), [items, statutFiltre])
  // BCF envoyés en attente de réception (raccourci de filtrage en un clic).
  const attenteReception = useMemo(() => nbEnvoyesNonRecus(items), [items])

  // Ouvre le détail en rechargeant la version complète (lignes à jour).
  const openBcf = async (b) => {
    try {
      const r = await stockApi.getBonCommandeFournisseur(b.id)
      setSelected(r.data)
    } catch { setSelected(b) }
  }

  const columns = useMemo(() => [
    { id: 'reference', header: 'Référence', minWidth: 140,
      accessor: (b) => b.reference ?? '' },
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 160,
      accessor: (b) => b.fournisseur_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'statut', header: 'Statut', width: 130, searchable: false,
      accessor: (b) => b.statut,
      cell: (v) => <StatusPill status={v} label={bcfStatutLabel(v)} /> },
    { id: 'date_commande', header: 'Date', width: 120, searchable: false,
      accessor: (b) => bcfDateAffichee(b),
      cell: (v) => fmtDateFR(v) },
    { id: 'lignes', header: 'Lignes', align: 'right', width: 90, searchable: false,
      accessor: (b) => (b.lignes ?? []).length },
    { id: 'total_achat', header: 'Total achat HT (interne)', align: 'right', minWidth: 170, searchable: false,
      accessor: (b) => b.total_achat,
      cell: (v) => fmtMad(v) },
  ], [])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Bons de commande fournisseur</h1>
          <p className="text-sm text-muted-foreground">{rows.length} bon(s) de commande</p>
        </div>
        <Button onClick={() => setSelected({})}>
          <Plus /> Nouveau bon de commande
        </Button>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <div className="w-48 sm:w-56">
          <Select value={statutFiltre || '__all'} onValueChange={(v) => setStatutFiltre(v === '__all' ? '' : v)}>
            <SelectTrigger><SelectValue placeholder="Tous les statuts" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all">Tous les statuts</SelectItem>
              {Object.entries(BCF_STATUTS).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {attenteReception > 0 && (
          <Button variant={statutFiltre === 'envoye' ? 'secondary' : 'outline'} size="sm"
                  onClick={() => setStatutFiltre(statutFiltre === 'envoye' ? '' : 'envoye')}
                  title="Bons de commande envoyés en attente de réception">
            En attente de réception ({attenteReception})
          </Button>
        )}
        {statutFiltre && (
          <Button variant="ghost" size="sm" onClick={() => setStatutFiltre('')}>
            Réinitialiser
          </Button>
        )}
      </div>

      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        getRowId={(b) => b.id}
        searchPlaceholder="Rechercher (référence, fournisseur)…"
        globalColumns={['reference', 'fournisseur_nom']}
        onRowClick={openBcf}
        emptyTitle="Aucun bon de commande fournisseur"
        emptyDescription="Créez-en un avec « Nouveau bon de commande » ou depuis le besoin matériel d'un chantier."
        aria-label="Bons de commande fournisseur"
      />

      {selected && (
        <BcfDetail bcf={selected} fournisseurs={fournisseurs} produits={produits}
                   onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
