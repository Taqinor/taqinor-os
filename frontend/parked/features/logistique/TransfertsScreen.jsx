import { useCallback, useEffect, useState } from 'react'
import { ArrowLeftRight, PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Spinner, EmptyState } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import { DEMANDE_TRANSFERT_STATUTS, actionsDisponiblesTransfert } from './logistique'

/* ============================================================================
   XSTK2 — Demandes de transfert (`/logistique/transferts`, FG325).
   ----------------------------------------------------------------------------
   Workflow demande → approbation → exécution entre emplacements de stock.
   `executer` déclenche RÉELLEMENT le mouvement de stock côté serveur (409 si
   source insuffisante — affiché tel quel, jamais masqué). Aucun prix d'achat
   affiché : seulement produit/quantité/emplacements.
   ========================================================================== */

export default function TransfertsScreen() {
  const [demandes, setDemandes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [showCreate, setShowCreate] = useState(false)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    installationsApi.getDemandesTransfert()
      .then((r) => {
        if (cancelled) return
        setDemandes(r.data?.results ?? r.data ?? [])
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const withBusy = async (id, fn) => {
    setBusyId(id)
    try { await fn(); await load() }
    catch (err) { setError(err?.response?.data?.detail || 'Action impossible.') }
    finally { setBusyId(null) }
  }

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Demandes de transfert"
        subtitle="Transfert inter-emplacements : demande, approbation, exécution."
        actions={(
          <Button size="sm" onClick={() => setShowCreate(true)}>
            <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle demande
          </Button>
        )}
      />

      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>}
      {error && !loading && <EmptyState title="Impossible de charger les demandes" description={error} />}

      {!loading && !error && (
        <div className="flex flex-col gap-3">
          {demandes.length === 0 && (
            <EmptyState
              icon={ArrowLeftRight}
              title="Aucune demande de transfert"
              description="Créez une demande pour déplacer du stock entre emplacements."
            />
          )}
          {demandes.map((d) => (
            <DemandeCard
              key={d.id}
              demande={d}
              busy={busyId === d.id}
              onApprouver={() => withBusy(d.id, () => installationsApi.approuverDemandeTransfert(d.id))}
              onRefuser={() => withBusy(d.id, () => installationsApi.refuserDemandeTransfert(d.id))}
              onExecuter={() => withBusy(d.id, () => installationsApi.executerDemandeTransfert(d.id))}
            />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateDemandeDialog
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load() }}
        />
      )}
    </div>
  )
}

function DemandeCard({ demande, busy, onApprouver, onRefuser, onExecuter }) {
  const actions = actionsDisponiblesTransfert(demande.statut)
  const tone = demande.statut === 'execute' ? 'success'
    : demande.statut === 'refuse' ? 'danger'
    : demande.statut === 'approuve' ? 'info' : 'warning'

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-medium">{demande.reference}</span>
        <Badge tone={tone}>{DEMANDE_TRANSFERT_STATUTS[demande.statut] || demande.statut}</Badge>
        <span className="ml-auto text-sm">
          {demande.produit_nom || '—'} · {demande.quantite}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">
        {demande.source_nom || '—'} → {demande.destination_nom || '—'}
      </p>
      {demande.motif_refus && (
        <p className="text-xs text-destructive">Motif du refus : {demande.motif_refus}</p>
      )}
      <div className="flex items-center gap-2">
        {actions.includes('approuver') && (
          <Button size="sm" disabled={busy} onClick={onApprouver}>Approuver</Button>
        )}
        {actions.includes('refuser') && (
          <Button size="sm" variant="outline" disabled={busy} onClick={onRefuser}>Refuser</Button>
        )}
        {actions.includes('executer') && (
          <Button size="sm" disabled={busy} onClick={onExecuter}>Exécuter</Button>
        )}
      </div>
    </div>
  )
}

function CreateDemandeDialog({ onClose, onCreated }) {
  const [produits, setProduits] = useState([])
  const [emplacements, setEmplacements] = useState([])
  const [produit, setProduit] = useState('')
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [quantite, setQuantite] = useState('')
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    Promise.all([
      stockApi.getProduits({ page_size: 200 }),
      stockApi.getEmplacements(),
    ]).then(([p, e]) => {
      if (!alive) return
      setProduits(p.data?.results ?? p.data ?? [])
      setEmplacements(e.data?.results ?? e.data ?? [])
    }).catch(() => { if (alive) { setProduits([]); setEmplacements([]) } })
    return () => { alive = false }
  }, [])

  const create = async () => {
    if (!produit || !source || !destination || !quantite) {
      setError('Produit, source, destination et quantité sont requis.')
      return
    }
    if (source === destination) {
      setError('La source et la destination doivent être différentes.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await installationsApi.createDemandeTransfert({
        produit, source, destination,
        quantite: Math.round(Number(quantite)) || 0,
        motif: motif || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }

  return (
    // VX182 — shell fait-main remplacé par ResponsiveDialog (Escape + focus-
    // trap + bottom-sheet mobile) ; en-tête/pied conservés à l'identique.
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle demande de transfert</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
        <div className="modal-body flex flex-col gap-3">
          <label className="form-label" htmlFor="tr-produit">Produit</label>
          <select id="tr-produit" className="form-control" value={produit} onChange={(e) => setProduit(e.target.value)} autoFocus>
            <option value="">— Choisir —</option>
            {produits.map((p) => <option key={p.id} value={p.id}>{p.nom || p.sku}</option>)}
          </select>

          <label className="form-label" htmlFor="tr-source">Emplacement source</label>
          <select id="tr-source" className="form-control" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">— Choisir —</option>
            {emplacements.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
          </select>

          <label className="form-label" htmlFor="tr-dest">Emplacement destination</label>
          <select id="tr-dest" className="form-control" value={destination} onChange={(e) => setDestination(e.target.value)}>
            <option value="">— Choisir —</option>
            {emplacements.map((e) => <option key={e.id} value={e.id}>{e.nom}</option>)}
          </select>

          <label className="form-label" htmlFor="tr-qte">Quantité</label>
          <input
            id="tr-qte"
            type="number"
            noValidate
            step="any"
            className="form-control"
            value={quantite}
            onChange={(e) => setQuantite(e.target.value)}
          />

          <label className="form-label" htmlFor="tr-motif">Motif (optionnel)</label>
          <textarea
            id="tr-motif"
            className="form-control"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            rows={2}
          />

          {error && <p className="form-error" role="alert">{error}</p>}
        </div>
        <div className="modal-footer">
          <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={busy} disabled={busy} onClick={create}>
            {busy ? 'Création…' : 'Créer la demande'}
          </Button>
        </div>
    </ResponsiveDialog>
  )
}
