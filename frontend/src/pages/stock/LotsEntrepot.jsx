import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { PackageMinus, Search } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Button, DataTable, Spinner, Badge, Input, Checkbox,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

/* WIR109 — XSTK6 : registre de lots en entrepôt (FEFO — péremption la plus
   proche d'abord). LECTURE SEULE côté modèle (alimenté à la confirmation
   d'une réception) : cet écran expose la consultation + les deux actions
   serveur déjà testées — `sortir` (décrémente un lot, garde périmé
   contournable avec motif tracé) et `fefo` (suggestion de sortie). */

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function fmtDate(v) {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString('fr-FR') } catch { return '—' }
}

// ── Dialog « Sortir » — décrémente un lot, gère le refus « lot périmé ». ────
function SortirLotDialog({ lot, onClose, onDone }) {
  const [quantite, setQuantite] = useState('')
  const [forcer, setForcer] = useState(false)
  const [motif, setMotif] = useState('')
  const [error, setError] = useState(null)
  const [perimeBloque, setPerimeBloque] = useState(false)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    const q = Number(quantite)
    if (!q || q <= 0) { setError('La quantité doit être positive.'); return }
    setSaving(true)
    setError(null)
    try {
      await stockApi.sortirLotEntrepot(lot.id, {
        quantite: q, forcer, motif: motif.trim() || undefined,
      })
      onDone?.()
      onClose()
    } catch (err) {
      const msg = frErr(err, 'La sortie a échoué.')
      // Garde XSTK6 : lot périmé refusé sauf motif tracé (forcer=true).
      if (/périm/i.test(msg)) setPerimeBloque(true)
      setError(msg)
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Sortir du lot {lot.numero_lot}</DialogTitle>
          <DialogDescription>
            Restant : {lot.quantite_restante} · {lot.produit_nom}
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Quantité" required htmlFor="lot-qte">
            <Input id="lot-qte" type="number" step="any" value={quantite}
                   onChange={(e) => setQuantite(e.target.value)} />
          </FormField>
          {perimeBloque && (
            <>
              <FormField htmlFor="lot-forcer" fullWidth>
                <label className="flex items-center gap-2 text-sm" htmlFor="lot-forcer">
                  <Checkbox id="lot-forcer" checked={forcer}
                            onCheckedChange={(v) => setForcer(!!v)} />
                  Forcer la sortie (lot périmé) — motif tracé requis
                </label>
              </FormField>
              <FormField label="Motif" htmlFor="lot-motif" fullWidth>
                <Textarea id="lot-motif" rows={2} value={motif}
                          onChange={(e) => setMotif(e.target.value)} />
              </FormField>
            </>
          )}
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Sortie…' : 'Sortir'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

// ── Outil « Suggestion FEFO » — lecture seule. ──────────────────────────────
function OutilFefo({ produits }) {
  const [produitId, setProduitId] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [plan, setPlan] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const suggerer = async () => {
    if (!produitId) { setError('Choisissez un produit.'); return }
    setLoading(true)
    setError(null)
    try {
      const r = await stockApi.getLotFefo(produitId, Number(quantite) || 1)
      setPlan(r.data ?? [])
    } catch (err) {
      setError(frErr(err, 'Suggestion indisponible.'))
    } finally { setLoading(false) }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <Search className="size-4" aria-hidden="true" /> Suggestion FEFO
      </h2>
      <p className="text-xs text-muted-foreground">
        Péremption la plus proche d&apos;abord — lecture seule, ne sort rien.
      </p>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[14rem] flex-1">
          <Select value={produitId} onValueChange={setProduitId}>
            <SelectTrigger><SelectValue placeholder="Choisir un produit…" /></SelectTrigger>
            <SelectContent>
              {produits.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Input className="w-24" type="number" step="1" min="1" value={quantite}
               onChange={(e) => setQuantite(e.target.value)} aria-label="Quantité" />
        <Button type="button" onClick={suggerer} loading={loading}>Suggérer</Button>
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {plan && (
        plan.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun lot disponible.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {plan.map((p) => (
              <li key={p.lot_id} className="flex items-center justify-between rounded-md border border-border bg-card p-2 text-sm">
                <span>{p.numero_lot} · péremption {fmtDate(p.date_peremption)}</span>
                <span className="tabular-nums text-muted-foreground">{p.quantite}</span>
              </li>
            ))}
          </ul>
        )
      )}
    </div>
  )
}

export default function LotsEntrepot() {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [produits, setProduits] = useState([])
  const [avecStock, setAvecStock] = useState(true)
  const [sortant, setSortant] = useState(null)

  const reload = () => {
    setLoading(true)
    stockApi.getLotsEntrepot(avecStock ? { avec_stock: 'true' } : {})
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des lots impossible.'))
      .finally(() => setLoading(false))
  }

  // Différé d'un microtask : `reload` pose `loading` de façon synchrone
  // (react-hooks/set-state-in-effect). Comportement inchangé.
  useEffect(() => { Promise.resolve().then(reload) }, [avecStock]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    stockApi.getProduits({ ordering: 'nom' })
      .then((r) => setProduits(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const columns = useMemo(() => [
    { id: 'numero_lot', header: 'N° de lot', minWidth: 130, accessor: (l) => l.numero_lot ?? '' },
    { id: 'produit_nom', header: 'Produit', minWidth: 160, accessor: (l) => l.produit_nom ?? '' },
    { id: 'date_peremption', header: 'Péremption', width: 140, searchable: false,
      accessor: (l) => l.date_peremption ?? '',
      cell: (_v, l) => (
        l.date_peremption
          ? <Badge tone={l.est_perime ? 'danger' : 'muted'}>{fmtDate(l.date_peremption)}</Badge>
          : <span className="text-muted-foreground">—</span>
      ) },
    { id: 'emplacement_nom', header: 'Emplacement', minWidth: 120, searchable: false,
      accessor: (l) => l.emplacement_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'quantite_restante', header: 'Restant', align: 'right', width: 90, searchable: false,
      accessor: (l) => l.quantite_restante ?? 0 },
    { id: 'quantite_recue', header: 'Reçu', align: 'right', width: 80, searchable: false,
      accessor: (l) => l.quantite_recue ?? 0 },
    { id: 'reference_reception', header: 'Réception', minWidth: 110, searchable: false,
      accessor: (l) => l.reference_reception ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'actions', header: '', width: 100, searchable: false, sortable: false,
      cell: (_v, l) => (
        canWrite && l.quantite_restante > 0 ? (
          <Button size="sm" variant="outline" onClick={() => setSortant(l)}>
            <PackageMinus className="size-4" /> Sortir
          </Button>
        ) : null
      ) },
  // canWrite stable au sein d'une session.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [canWrite])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header>
        <h1 className="font-display text-xl font-semibold tracking-tight">Lots en entrepôt (FEFO)</h1>
        <p className="text-sm text-muted-foreground">
          Traçabilité par lot (batteries, produits d&apos;étanchéité…) — péremption la plus proche d&apos;abord.
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <OutilFefo produits={produits} />

      <label className="flex w-fit items-center gap-2 text-sm">
        <Checkbox checked={avecStock} onCheckedChange={(v) => setAvecStock(!!v)} />
        Uniquement les lots avec du stock restant
      </label>

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(l) => l.id}
        searchPlaceholder="Rechercher (n° de lot, produit)…"
        globalColumns={['numero_lot', 'produit_nom']}
        emptyTitle="Aucun lot"
        emptyDescription="Les lots apparaissent à la confirmation d'une réception avec numéro de lot."
        aria-label="Lots en entrepôt"
      />

      {sortant && (
        <SortirLotDialog lot={sortant} onClose={() => setSortant(null)} onDone={reload} />
      )}
    </div>
  )
}
