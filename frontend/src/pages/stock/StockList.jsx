import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Upload, Download, Truck, Calculator, Wallet, AlertTriangle,
  Archive, PackageOpen, Pencil, Trash2, RotateCcw, Package, QrCode, ScanLine,
} from 'lucide-react'
import {
  fetchProduits,
  fetchProduitsArchived,
  fetchCategories,
  updateProduit,
  deleteProduit,
  unarchiveProduit,
  forceDeleteArchivedProduit,
} from '../../features/stock/store/stockSlice'
import ProduitForm from './ProduitForm'
import InlineEdit from '../../components/InlineEdit'
import BulkProductBar from './BulkProductBar'
import ExcelImport from '../../components/ExcelImport'
import stockApi from '../../api/stockApi'
import { toggleId, pruneSelection, bulkResultMessage } from '../../features/crm/bulk'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../../features/stock/catalogue'
import { validateTransfert, totalVentile } from '../../features/stock/emplacements'
import { normalizeCode, isValidCode, resolveTarget } from '../../features/stock/labels'
import { toastError, toastSuccess } from '../../lib/toast'
import {
  Button, IconButton, Badge, Checkbox, Input, Spinner, Skeleton,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription,
  AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  EmptyState, DataTable,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

const fmtNum2 = (n) => Number(n || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

// Suggestion de quantité à commander pour un produit en stock bas :
// vise un réassort à 2× le seuil d'alerte, jamais négative.
const suggestionCommande = (p) => {
  const seuil = Number(p.seuil_alerte) || 0
  const stock = Number(p.quantite_stock) || 0
  return Math.max(seuil * 2 - stock, 0)
}

// Petit tableau interne stylé (lecture seule) — utilisé dans les modals.
function MiniTable({ head, children, className = '' }) {
  return (
    <div className={`overflow-hidden rounded-lg border border-border ${className}`}>
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
          <tr>{head.map((h, i) => <th key={i} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

// ── N16 — Inventaire physique : comptage par produit → ajustement de stock ──
function InventaireModal({ produits, onClose, onDone }) {
  const [motif, setMotif] = useState('')
  const [counts, setCounts] = useState({}) // { produitId: '12' }
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const rows = (produits ?? []).filter((p) => !p.is_archived)

  const submit = async () => {
    const lignes = rows
      .filter((p) => counts[p.id] !== undefined && counts[p.id] !== '')
      .map((p) => ({ produit: p.id, quantite_comptee: parseInt(counts[p.id], 10) }))
      .filter((l) => Number.isInteger(l.quantite_comptee) && l.quantite_comptee >= 0)
    if (lignes.length === 0) { setError('Saisissez au moins un comptage.'); return }
    setSaving(true); setError(null)
    try {
      const r = await stockApi.inventaire({ motif, lignes })
      onDone?.(r.data)
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'inventaire.")
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Inventaire physique</DialogTitle>
          <DialogDescription>
            Saisissez la quantité comptée ; seuls les écarts sont ajustés (mouvement
            « Ajustement » audité). Laissez vide pour ne pas toucher un produit.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="inv-motif">Motif (optionnel)</label>
          <Input id="inv-motif" value={motif} onChange={(e) => setMotif(e.target.value)}
                 placeholder="Ex. comptage annuel" />
        </div>

        <div className="max-h-80 overflow-auto">
          <MiniTable head={['Produit', 'SKU', 'Stock actuel', 'Compté']}>
            {rows.map((p) => (
              <tr key={p.id} className="border-t border-border">
                <td className="px-3 py-2">{p.nom}</td>
                <td className="px-3 py-2 font-mono text-xs">{p.sku ?? '—'}</td>
                <td className="px-3 py-2 tabular-nums">{p.quantite_stock}</td>
                <td className="px-3 py-2">
                  <Input type="number" min="0" inputMode="numeric" className="h-9 w-24"
                         value={counts[p.id] ?? ''}
                         placeholder={String(p.quantite_stock)}
                         onChange={(e) => setCounts((c) => ({ ...c, [p.id]: e.target.value }))} />
                </td>
              </tr>
            ))}
          </MiniTable>
        </div>
        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
        )}

        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
          <Button type="button" loading={saving} onClick={submit}>
            {saving ? 'Enregistrement…' : "Valider l'inventaire"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── N18 — Valorisation du stock par emplacement (coût moyen d'achat, INTERNE) ──
function ValorisationModal({ onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  useEffect(() => {
    stockApi.valorisation()
      .then((r) => setData(r.data))
      .catch(() => setError('Échec du chargement de la valorisation.'))
  }, [])
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Valorisation du stock par emplacement</DialogTitle>
          <DialogDescription>
            Valeur au coût moyen d&apos;achat (historique des réceptions, sinon prix
            d&apos;achat catalogue). Donnée interne — jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
        )}
        {!data && !error && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
        )}
        {data && (
          <>
            <MiniTable head={['Emplacement', 'Quantité', 'Valeur']}>
              {data.par_emplacement.map((t) => (
                <tr key={t.emplacement_id} className="border-t border-border">
                  <td className="px-3 py-2">{t.emplacement_nom}{t.is_principal ? ' (principal)' : ''}</td>
                  <td className="px-3 py-2 tabular-nums">{t.quantite}</td>
                  <td className="px-3 py-2 tabular-nums">{fmtNum2(t.valeur)} DH</td>
                </tr>
              ))}
              <tr className="border-t-2 border-border bg-muted/40">
                <td className="px-3 py-2 font-semibold">Total</td>
                <td className="px-3 py-2" />
                <td className="px-3 py-2 font-semibold tabular-nums">{fmtNum2(data.total)} DH</td>
              </tr>
            </MiniTable>
            <div className="max-h-80 overflow-auto">
              <MiniTable head={['Produit', 'Emplacement', 'Qté', 'Coût moyen', 'Valeur']}>
                {data.lignes.map((l, i) => (
                  <tr key={`${l.produit_id}-${l.emplacement_nom}-${i}`} className="border-t border-border">
                    <td className="px-3 py-2">{l.designation}</td>
                    <td className="px-3 py-2">{l.emplacement_nom}</td>
                    <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
                    <td className="px-3 py-2 tabular-nums">{fmtNum2(l.cout_moyen)} DH</td>
                    <td className="px-3 py-2 tabular-nums">{fmtNum2(l.valeur)} DH</td>
                  </tr>
                ))}
              </MiniTable>
            </div>
          </>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── N15 — Transfert de stock entre emplacements (dépôt principal / camionnette) ──
// Le total du produit ne change jamais : un transfert ne fait que déplacer la
// quantité d'un emplacement vers un autre. Gestion d'emplacements inline (admin).
function TransfertModal({ produits, isAdmin, onClose, onDone }) {
  const [emplacements, setEmplacements] = useState([])
  const [produitId, setProduitId] = useState('')
  const [breakdown, setBreakdown] = useState([])
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [quantite, setQuantite] = useState('')
  const [note, setNote] = useState('')
  const [transferts, setTransferts] = useState([])
  const [newEmp, setNewEmp] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const rows = (produits ?? []).filter((p) => !p.is_archived)

  // setState arrive dans les callbacks .then (jamais synchrone dans l'effet).
  const loadEmplacements = () => stockApi.getEmplacements()
    .then((r) => setEmplacements(r.data?.results ?? r.data ?? [])).catch(() => {})
  const loadTransferts = () => stockApi.getTransferts({ ordering: '-date' })
    .then((r) => setTransferts((r.data?.results ?? r.data ?? []).slice(0, 8)))
    .catch(() => {})
  useEffect(() => { loadEmplacements(); loadTransferts() }, [])

  const loadBreakdown = (pid) => {
    if (!pid) { setBreakdown([]); return Promise.resolve() }
    return stockApi.getProduitEmplacements(pid)
      .then((r) => setBreakdown(r.data ?? [])).catch(() => {})
  }
  const onPickProduit = (pid) => { setProduitId(pid); setError(null); loadBreakdown(pid) }

  const submit = async () => {
    const msg = validateTransfert({ breakdown, source, destination, quantite })
    if (!produitId) { setError('Choisissez un produit.'); return }
    if (msg) { setError(msg); return }
    setSaving(true); setError(null)
    try {
      await stockApi.createTransfert({
        produit: produitId, source, destination,
        quantite: parseInt(quantite, 10), note,
      })
      await loadBreakdown(produitId)
      await loadTransferts()
      setQuantite(''); setNote('')
      onDone?.()
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Échec du transfert.')
    } finally { setSaving(false) }
  }

  const addEmplacement = async () => {
    const nom = newEmp.trim()
    if (!nom) return
    try {
      await stockApi.saveEmplacement(null, { nom })
      setNewEmp('')
      await loadEmplacements()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'ajout d'emplacement.")
    }
  }
  const removeEmplacement = async (id) => {
    try { await stockApi.deleteEmplacement(id); await loadEmplacements() }
    catch (err) { setError(err.response?.data?.detail ?? 'Suppression impossible.') }
  }

  const empOptions = emplacements.filter((e) => !e.archived)

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Transférer du stock entre emplacements</DialogTitle>
          <DialogDescription>
            Déplacez une quantité d&apos;un emplacement à un autre (ex. dépôt principal →
            camionnette). Le stock total du produit ne change pas — seule la
            répartition change.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="tr-produit">Produit</label>
          <Select value={produitId || '__none'} onValueChange={(v) => onPickProduit(v === '__none' ? '' : v)}>
            <SelectTrigger id="tr-produit"><SelectValue placeholder="— Choisir un produit —" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none">— Choisir un produit —</SelectItem>
              {rows.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.nom}{p.sku ? ` (${p.sku})` : ''} — stock {p.quantite_stock}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {produitId && (
          <MiniTable head={['Emplacement', 'Quantité']}>
            {breakdown.map((b) => (
              <tr key={b.emplacement_id} className="border-t border-border">
                <td className="px-3 py-2">{b.emplacement_nom}{b.is_principal ? ' (principal)' : ''}</td>
                <td className="px-3 py-2 tabular-nums">{b.quantite}</td>
              </tr>
            ))}
            <tr className="border-t-2 border-border bg-muted/40">
              <td className="px-3 py-2 font-semibold">Total</td>
              <td className="px-3 py-2 font-semibold tabular-nums">{totalVentile(breakdown)}</td>
            </tr>
          </MiniTable>
        )}

        <div className="flex flex-wrap gap-2">
          <div className="min-w-40 flex-1 flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="tr-src">De</label>
            <Select value={source || '__none'} onValueChange={(v) => setSource(v === '__none' ? '' : v)}>
              <SelectTrigger id="tr-src"><SelectValue placeholder="— Source —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Source —</SelectItem>
                {empOptions.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="min-w-40 flex-1 flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="tr-dst">Vers</label>
            <Select value={destination || '__none'} onValueChange={(v) => setDestination(v === '__none' ? '' : v)}>
              <SelectTrigger id="tr-dst"><SelectValue placeholder="— Destination —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Destination —</SelectItem>
                {empOptions.map((e) => <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="w-28 flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="tr-qte">Quantité</label>
            <Input id="tr-qte" type="number" min="1" inputMode="numeric" value={quantite}
                   onChange={(e) => setQuantite(e.target.value)} />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="tr-note">Note (optionnel)</label>
          <Input id="tr-note" value={note} onChange={(e) => setNote(e.target.value)}
                 placeholder="Ex. chargement chantier Casablanca" />
        </div>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
        )}

        <div className="flex justify-end">
          <Button type="button" loading={saving} onClick={submit}>
            {saving ? 'Transfert…' : 'Transférer'}
          </Button>
        </div>

        {transferts.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <h4 className="text-sm font-semibold">Derniers transferts</h4>
            <div className="max-h-44 overflow-auto">
              <MiniTable head={['Produit', 'De → Vers', 'Qté']}>
                {transferts.map((t) => (
                  <tr key={t.id} className="border-t border-border">
                    <td className="px-3 py-2">{t.produit_nom}</td>
                    <td className="px-3 py-2">{t.source_nom} → {t.destination_nom}</td>
                    <td className="px-3 py-2 tabular-nums">{t.quantite}</td>
                  </tr>
                ))}
              </MiniTable>
            </div>
          </div>
        )}

        {isAdmin && (
          <details className="rounded-lg border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium">Gérer les emplacements</summary>
            <div className="mt-2 flex gap-2">
              <Input value={newEmp} onChange={(e) => setNewEmp(e.target.value)}
                     placeholder="Nouvel emplacement (ex. Camionnette 2)" />
              <Button type="button" variant="outline" onClick={addEmplacement}>Ajouter</Button>
            </div>
            <ul className="mt-2 flex flex-col">
              {emplacements.map((e) => (
                <li key={e.id} className="flex items-center justify-between py-1 text-sm">
                  <span>{e.nom}{e.is_principal ? ' (principal)' : ''}</span>
                  {!e.is_principal && (
                    <Button type="button" variant="ghost" size="sm" onClick={() => removeEmplacement(e.id)}>
                      Supprimer
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}
      </DialogContent>
    </Dialog>
  )
}

// ── Ligne article du catalogue (hoistée : identité stable entre rendus) ─────
function CatalogueRow({ p, canWrite, canDelete, onEdit, onDelete, categories, onInlineSave, selected, onToggleSelect }) {
  const spec = keySpec(p)
  const ttc = prixTtc(p)
  const catOptions = [{ value: '', label: '— Catégorie —' }]
    .concat((categories ?? []).map((c) => ({ value: c.id, label: c.nom })))
  return (
    <div className={`flex flex-wrap items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors sm:flex-nowrap ${p.is_low_stock ? 'border-destructive/40 bg-destructive/5' : 'border-border bg-card hover:bg-muted/40'}`}>
      {onToggleSelect && (
        <Checkbox checked={selected} onCheckedChange={() => onToggleSelect(p.id)}
                  aria-label={`Sélectionner ${p.nom}`} />
      )}
      <div className="min-w-0 flex-1">
        <div className="truncate font-medium text-foreground">{p.nom}</div>
        <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
          {p.sku
            ? <span className="font-mono">{p.sku}</span>
            : <Badge tone="warning">SKU manquant</Badge>}
          {parseFloat(p.prix_achat) > 0 && (
            <span>· achat {parseFloat(p.prix_achat).toFixed(2)} DH HT</span>
          )}
          {onInlineSave && (
            <span>
              {' · '}
              <InlineEdit
                value={p.categorie?.id ?? ''}
                options={catOptions}
                display={p.categorie?.nom ?? null}
                placeholder="catégorie"
                onSave={(v) => onInlineSave(p, 'categorie_id', v)}
              />
            </span>
          )}
        </div>
      </div>
      <div className="shrink-0">{spec && <Badge tone="primary">{spec}</Badge>}</div>
      <div className="shrink-0 text-right">
        {sansPrix(p) && !onInlineSave
          ? <Badge tone="warning">prix à renseigner</Badge>
          : (
            <>
              <div className="font-semibold tabular-nums">
                {ttc.toLocaleString('fr-MA')} DH <span className="text-xs font-normal text-muted-foreground">TTC</span>
              </div>
              <div className="text-xs text-muted-foreground">
                {onInlineSave ? (
                  <InlineEdit
                    value={p.prix_vente}
                    type="number"
                    display={`${parseFloat(p.prix_vente || 0).toFixed(2)} HT`}
                    placeholder="prix HT"
                    onSave={(v) => onInlineSave(p, 'prix_vente', v)}
                  />
                ) : `${parseFloat(p.prix_vente).toFixed(2)} HT`}
                {' · TVA '}{parseFloat(p.tva ?? 20)}%
              </div>
            </>
          )}
      </div>
      <div className="shrink-0 text-right">
        <span className={`text-sm ${p.is_low_stock ? 'text-destructive' : ''}`}>
          {onInlineSave ? (
            <InlineEdit
              value={p.quantite_stock}
              type="number"
              display={<strong>{p.quantite_stock}</strong>}
              onSave={(v) => onInlineSave(p, 'quantite_stock', v)}
            />
          ) : <strong>{p.quantite_stock}</strong>}
          {' '}en stock
        </span>
        {p.quantite_reservee > 0 && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            {p.quantite_reservee} réservé · {p.quantite_disponible} dispo
          </div>
        )}
        {p.is_low_stock && (
          <div className="mt-0.5 flex flex-col items-end gap-0.5">
            <Badge tone="danger">
              <AlertTriangle className="size-3" />{' seuil '}
              {onInlineSave ? (
                <InlineEdit
                  value={p.seuil_alerte}
                  type="number"
                  display={String(p.seuil_alerte)}
                  onSave={(v) => onInlineSave(p, 'seuil_alerte', v)}
                />
              ) : p.seuil_alerte}
            </Badge>
            {suggestionCommande(p) > 0 && (
              <span className="text-xs text-muted-foreground">commander ~{suggestionCommande(p)}</span>
            )}
          </div>
        )}
        {!p.is_low_stock && onInlineSave && (
          <div className="mt-0.5 text-xs text-muted-foreground">
            seuil{' '}
            <InlineEdit
              value={p.seuil_alerte}
              type="number"
              display={String(p.seuil_alerte)}
              onSave={(v) => onInlineSave(p, 'seuil_alerte', v)}
            />
          </div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-0.5">
        {canWrite && (
          <IconButton label="Éditer" variant="ghost" size="icon" className="size-8" onClick={() => onEdit(p)}>
            <Pencil />
          </IconButton>
        )}
        {canDelete && (
          <IconButton label="Supprimer" variant="ghost" size="icon" className="size-8" onClick={() => onDelete(p)}>
            <Trash2 className="text-destructive" />
          </IconButton>
        )}
      </div>
    </div>
  )
}

// ── Confirmation suppression définitive (AlertDialog + saisie de confirmation) ──
function ForceDeleteModal({ produit, onCancel, onConfirm, loading }) {
  const [typed, setTyped] = useState('')
  const expected = produit.sku || produit.nom
  const isValid  = typed.trim() === expected.trim()

  const fmtDate = (iso) => {
    if (!iso) return '—'
    return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
  }

  return (
    <AlertDialog open onOpenChange={(o) => { if (!o) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">Suppression définitive</AlertDialogTitle>
          <AlertDialogDescription>
            Cette action supprimera le produit et tout son historique de mouvements.
            Elle est <strong>irréversible</strong>.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed">
          <div><span className="inline-block min-w-32 text-muted-foreground">Produit</span><strong>{produit.nom}</strong></div>
          <div><span className="inline-block min-w-32 text-muted-foreground">SKU / Référence</span><code className="rounded bg-muted px-1.5 py-0.5">{produit.sku || '—'}</code></div>
          <div><span className="inline-block min-w-32 text-muted-foreground">Créé le</span>{fmtDate(produit.date_creation)}</div>
          {produit.nb_mouvements != null && (
            <div>
              <span className="inline-block min-w-32 text-muted-foreground">Mouvements</span>
              {produit.nb_mouvements} mouvement{produit.nb_mouvements !== 1 ? 's' : ''}
              {produit.premiere_date_mouvement && (
                <span className="text-muted-foreground"> ({fmtDate(produit.premiere_date_mouvement)} → {fmtDate(produit.derniere_date_mouvement)})</span>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="fd-confirm">
            Tapez <code className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">{expected}</code> pour confirmer
          </label>
          <Input id="fd-confirm" value={typed} onChange={e => setTyped(e.target.value)}
                 placeholder={`Saisir : ${expected}`} autoFocus />
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Annuler</AlertDialogCancel>
          <AlertDialogAction
            disabled={!isValid || loading}
            onClick={(e) => { e.preventDefault(); onConfirm(produit) }}
          >
            {loading ? 'Suppression…' : 'Supprimer définitivement'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ── Page principale ────────────────────────────────────────────────────────
export default function StockList() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { produits, produitsArchived, categories, loading, error } = useSelector(s => s.stock)
  const role = useSelector(s => s.auth.role)
  const permissions = useSelector(s => s.auth.permissions)
  // Rôle fin (ex. « Commerciale » lecture seule) : les permissions priment ;
  // comptes hérités sans rôle fin : comportement historique par rôle.
  const canWrite = permissions.length
    ? permissions.includes('stock_modifier')
    : (role === 'responsable' || role === 'admin')
  const canDelete = role === 'admin'

  const [search, setSearch]           = useState('')
  const [showForm, setShowForm]       = useState(false)
  const [editProduit, setEditProduit] = useState(null)
  const [filterLow, setFilterLow]     = useState(false)
  const [filterNoPrice, setFilterNoPrice] = useState(false)  // produits sans prix de vente
  const [filterNoSku, setFilterNoSku]     = useState(false)  // produits sans SKU
  const [filterMarque, setFilterMarque]   = useState('')     // '' = toutes les marques
  const [activeCat, setActiveCat]     = useState('')   // '' = tout le catalogue
  const [showArchived, setShowArchived]   = useState(false)
  const [archiveNotif, setArchiveNotif]   = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [deleting, setDeleting]           = useState(false)
  // Multi-sélection + édition en masse (T8).
  const [selected, setSelected]   = useState(() => new Set())
  const [marquesList, setMarques] = useState([])
  const [bulkBusy, setBulkBusy]   = useState(false)
  const [bulkMsg, setBulkMsg]     = useState(null)
  const [showImport, setShowImport] = useState(false)
  const [showInventaire, setShowInventaire] = useState(false)
  const [invMsg, setInvMsg] = useState(null)
  const [showTransfert, setShowTransfert] = useState(false)
  const [showValorisation, setShowValorisation] = useState(false)
  // N20 — étiquettes QR/code-barres + champ de scan (résolution serveur).
  const [labelsBusy, setLabelsBusy]   = useState(false)
  const [scanOpen, setScanOpen]       = useState(false)
  const [scanCode, setScanCode]       = useState('')
  const [scanBusy, setScanBusy]       = useState(false)

  useEffect(() => {
    dispatch(fetchProduits()); dispatch(fetchCategories())
    stockApi.getMarques().then(r => setMarques(r.data.results ?? r.data)).catch(() => {})
  }, [dispatch])

  // Sélection effective (élague les produits disparus après refetch/filtre).
  const visibleSelected = useMemo(
    () => pruneSelection(selected, (produits ?? []).map(p => p.id)),
    [selected, produits],
  )
  const onToggleSelect = (id) => setSelected(s => toggleId(s, id))
  const clearSelection = () => setSelected(new Set())

  const runBulk = async (action, params = {}) => {
    if (!visibleSelected.size) return
    setBulkBusy(true)
    try {
      const { data } = await stockApi.bulkProduits({ ids: [...visibleSelected], action, ...params })
      setBulkMsg(bulkResultMessage(data))
      dispatch(fetchProduits())
    } catch (e) {
      setBulkMsg(e?.response?.data?.detail ?? "L'action en masse a échoué.")
    } finally { setBulkBusy(false) }
  }
  const exportSelection = async () => {
    if (!visibleSelected.size) return
    setBulkBusy(true)
    try {
      const res = await stockApi.exportProduitsXlsx([...visibleSelected])
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = 'produits.xlsx'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { setBulkMsg('Export indisponible.') } finally { setBulkBusy(false) }
  }
  // N20 — Imprime des étiquettes QR pour la sélection (PDF ; jamais de prix
  // d'achat — l'étiquette ne porte que nom + SKU + jeton PRODUIT:<id>).
  const printLabels = async () => {
    if (!visibleSelected.size) return
    setLabelsBusy(true)
    try {
      const res = await stockApi.etiquettesProduits([...visibleSelected])
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60000)
    } catch { toastError('Génération des étiquettes indisponible.') }
    finally { setLabelsBusy(false) }
  }
  // N20 — Résout un code scanné/saisi (PRODUIT:<id> / SYSTEME:<id>) et navigue
  // vers la fiche correspondante (lecture seule côté serveur).
  const runScan = async () => {
    const code = normalizeCode(scanCode)
    if (!isValidCode(code)) {
      toastError('Code illisible. Attendu : PRODUIT:<id> ou SYSTEME:<id>.')
      return
    }
    setScanBusy(true)
    try {
      const { data } = await stockApi.resolveCode(code)
      const target = resolveTarget(data)
      if (!target) { toastError('Code introuvable.'); return }
      setScanOpen(false); setScanCode('')
      if (target.route === '/stock') {
        // Reste sur le catalogue : on filtre sur le produit résolu.
        setSearch(target.search); setActiveCat(''); setFilterLow(false)
        toastSuccess(`Produit trouvé : ${data.label}`)
      } else {
        toastSuccess(`Système trouvé : ${data.label}`)
        navigate(target.route)
      }
    } catch (e) {
      const msg = e?.response?.status === 404
        ? 'Aucun enregistrement pour ce code.'
        : 'Résolution indisponible.'
      toastError(msg)
    } finally { setScanBusy(false) }
  }
  useEffect(() => {
    if (!bulkMsg) return undefined
    const t = setTimeout(() => setBulkMsg(null), 8000)
    return () => clearTimeout(t)
  }, [bulkMsg])

  // Édition en place (T4) : PATCH d'UN seul champ produit (prix de vente,
  // quantité, catégorie). Validation serveur ; renvoie la promesse pour
  // qu'InlineEdit restaure la valeur si l'enregistrement échoue.
  const onInlineSave = (p, field, value) =>
    dispatch(updateProduit({ id: p.id, data: { [field]: value } })).unwrap()

  useEffect(() => {
    if (showArchived) dispatch(fetchProduitsArchived())
  }, [showArchived, dispatch])

  // Catalogue hiérarchisé : la recherche traverse TOUT (nom, SKU, marque,
  // catégorie, spec) ; sans recherche, le rail filtre par catégorie.
  const actifs = useMemo(() => produits.filter(p => !p.is_archived), [produits])
  const searching = search.trim().length > 0
  const filtered = useMemo(() => {
    let list = filterLow ? actifs.filter(p => p.is_low_stock) : actifs
    if (filterNoPrice) list = list.filter(p => sansPrix(p))
    if (filterNoSku) list = list.filter(p => !(p.sku ?? '').trim())
    if (filterMarque) list = list.filter(p => ((p.marque || '').trim() || 'Génériques') === filterMarque)
    list = searchCatalogue(list, search)
    return list
  }, [actifs, search, filterLow, filterNoPrice, filterNoSku, filterMarque])

  // Compteurs des filtres rail (sur le catalogue actif complet).
  const noPriceCount = useMemo(() => actifs.filter(p => sansPrix(p)).length, [actifs])
  const noSkuCount = useMemo(() => actifs.filter(p => !(p.sku ?? '').trim()).length, [actifs])
  // Liste des marques présentes (pour le filtre par marque).
  const marquesPresentes = useMemo(() => {
    const set = new Set(actifs.map(p => (p.marque || '').trim() || 'Génériques'))
    return [...set].sort((a, b) => a.localeCompare(b))
  }, [actifs])
  // Valeur de vente HT du catalogue affiché (somme prix_vente × quantité).
  const valeurVenteFiltree = useMemo(
    () => filtered.reduce((sum, p) => sum + (parseFloat(p.prix_vente) || 0) * (Number(p.quantite_stock) || 0), 0),
    [filtered],
  )
  // Export Excel de la liste filtrée courante (T9) — défini après `filtered`.
  const exportFiltered = async () => {
    const ids = filtered.map(p => p.id)
    if (!ids.length) return
    try {
      const res = await stockApi.exportProduitsXlsx(ids)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = 'produits.xlsx'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { /* ignore */ }
  }
  const allGroups = useMemo(() => groupCatalogue(actifs), [actifs])
  const groups = useMemo(() => {
    const g = groupCatalogue(filtered)
    if (searching || !activeCat) return g
    return g.filter(c => c.nom === activeCat)
  }, [filtered, searching, activeCat])

  const lowCount = useMemo(
    () => produits.filter(p => p.is_low_stock && !p.is_archived).length,
    [produits]
  )

  const openNew   = () => { setEditProduit(null); setShowForm(true) }
  const openEdit  = p  => { setEditProduit(p);    setShowForm(true) }
  const closeForm = () => { setShowForm(false);   setEditProduit(null) }
  const onSaved   = () => {
    dispatch(fetchProduits())
    if (showArchived) dispatch(fetchProduitsArchived())
  }

  const handleDelete = async (p) => {
    if (!window.confirm(`Supprimer le produit « ${p.nom} » ?`)) return
    try {
      const result = await dispatch(deleteProduit(p.id)).unwrap()
      if (result.archived) {
        setArchiveNotif(result.detail)
        setTimeout(() => setArchiveNotif(null), 6000)
      }
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la suppression.')
    }
  }

  const handleUnarchive = async (p) => {
    if (!window.confirm(`Désarchiver le produit « ${p.nom} » ?`)) return
    try {
      await dispatch(unarchiveProduit(p.id)).unwrap()
      dispatch(fetchProduitsArchived())
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors du désarchivage.')
    }
  }

  const handleForceDelete = async (p) => {
    setDeleting(true)
    try {
      await dispatch(forceDeleteArchivedProduit(p.id)).unwrap()
      setConfirmDelete(null)
    } catch (err) {
      alert(err?.detail ?? 'Erreur lors de la suppression définitive.')
    } finally {
      setDeleting(false)
    }
  }

  // ── Colonnes du tableau des produits archivés (DataTable) ──
  const archivedColumns = useMemo(() => [
    { id: 'sku', header: 'SKU', width: 120,
      accessor: (p) => p.sku ?? '—',
      cell: (v) => <span className="font-mono text-xs line-through">{v}</span> },
    { id: 'nom', header: 'Nom', minWidth: 160,
      cell: (v) => <span className="line-through">{v}</span> },
    { id: 'categorie', header: 'Catégorie', minWidth: 120, searchable: false,
      accessor: (p) => p.categorie?.nom ?? '—' },
    { id: 'fournisseur', header: 'Fournisseur', minWidth: 120, searchable: false,
      accessor: (p) => p.fournisseur?.nom ?? '—' },
    { id: 'quantite_stock', header: 'Stock', align: 'right', width: 80, searchable: false },
    { id: 'nb_mouvements', header: 'Mouvements', align: 'right', width: 110, searchable: false,
      accessor: (p) => p.nb_mouvements ?? null,
      cell: (v, p) => (v != null
        ? <span title={p.premiere_date_mouvement
            ? `${new Date(p.premiere_date_mouvement).toLocaleDateString('fr-FR')} → ${new Date(p.derniere_date_mouvement).toLocaleDateString('fr-FR')}`
            : ''}>{v}</span>
        : '—') },
    { id: 'prix_vente', header: 'Prix vente HT', align: 'right', width: 120, searchable: false,
      accessor: (p) => p.prix_vente,
      cell: (v) => `${parseFloat(v).toFixed(2)} DH` },
  ], [])

  const archivedRowActions = (p) => [
    { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => openEdit(p) },
    { id: 'unarchive', label: 'Désarchiver', icon: RotateCcw, onClick: () => handleUnarchive(p) },
    { id: 'delete', label: 'Supprimer', icon: Trash2, destructive: true, onClick: () => setConfirmDelete(p) },
  ]

  // Squelette de chargement de premier rendu (avant données).
  if (loading && actifs.length === 0) {
    return (
      <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
        <Skeleton className="h-8 w-56" />
        <div className="flex flex-col gap-2">
          {Array.from({ length: 6 }).map((u, i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <EmptyState icon={AlertTriangle} title="Erreur de chargement"
                    description={`Erreur : ${JSON.stringify(error)}`} className="border-destructive/40" />
      </div>
    )
  }

  const actifsCount = produits.filter(p => !p.is_archived).length

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      {confirmDelete && (
        <ForceDeleteModal
          produit={confirmDelete}
          loading={deleting}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={handleForceDelete}
        />
      )}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xl font-semibold tracking-tight">Produits en stock</h2>
          {actifsCount > 0 && <Badge tone="primary">{actifsCount}</Badge>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {lowCount > 0 && (
            <Button
              variant={filterLow ? 'destructive' : 'outline'} size="sm"
              onClick={() => setFilterLow(v => !v)}
              title="Filtrer les produits en rupture ou sous le seuil d'alerte"
            >
              <AlertTriangle /> Stock bas ({lowCount})
            </Button>
          )}
          {role === 'admin' && (
            <Button variant={showArchived ? 'secondary' : 'outline'} size="sm"
                    onClick={() => setShowArchived(v => !v)}>
              <Archive /> {showArchived ? 'Masquer archivés' : `Archivés${produitsArchived.length > 0 ? ` (${produitsArchived.length})` : ''}`}
            </Button>
          )}
          {role === 'admin' && (
            <Button variant="outline" size="sm" onClick={() => setShowInventaire(true)}
                    title="Inventaire physique : saisir un comptage et ajuster le stock">
              <Calculator /> Inventaire
            </Button>
          )}
          {role === 'admin' && (
            <Button variant="outline" size="sm" onClick={() => setShowValorisation(true)}
                    title="Valorisation du stock par emplacement (coût moyen, interne)">
              <Wallet /> Valorisation
            </Button>
          )}
          {canWrite && (
            <Button variant="outline" size="sm" onClick={() => setShowTransfert(true)}
                    title="Transférer du stock entre emplacements (dépôt / camionnette)">
              <Truck /> Transférer
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setScanOpen(v => !v)}
                  title="Scanner un code QR / code-barres et ouvrir la fiche">
            <ScanLine /> Scanner
          </Button>
          <Button variant="outline" size="sm" onClick={exportFiltered}>
            <Download /> Exporter Excel
          </Button>
          {canWrite && (
            <Button variant="outline" size="sm" onClick={() => setShowImport(true)}>
              <Upload /> Importer
            </Button>
          )}
          {canWrite && (
            <Button onClick={openNew}>
              <Plus /> Nouveau produit
            </Button>
          )}
        </div>
      </header>

      {scanOpen && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-muted/40 px-4 py-3">
          <QrCode className="size-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Scanner / saisir un code</span>
          <Input
            autoFocus className="h-9 w-64 font-mono"
            placeholder="PRODUIT:123 ou SYSTEME:45"
            value={scanCode}
            onChange={(e) => setScanCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); runScan() } }}
          />
          <Button size="sm" loading={scanBusy} disabled={!scanCode.trim()} onClick={runScan}>
            Ouvrir la fiche
          </Button>
          <Button size="sm" variant="ghost"
                  onClick={() => { setScanOpen(false); setScanCode('') }}>
            Fermer
          </Button>
        </div>
      )}

      {showImport && (
        <ExcelImport target="products" onClose={() => setShowImport(false)}
                     onDone={() => dispatch(fetchProduits())} />
      )}

      {showInventaire && (
        <InventaireModal produits={filtered} onClose={() => setShowInventaire(false)}
                         onDone={(res) => {
                           dispatch(fetchProduits())
                           if (res) {
                             setInvMsg(`Inventaire enregistré : ${res.ajustes} ajustement(s), ${res.inchanges} inchangé(s).`)
                             setTimeout(() => setInvMsg(null), 8000)
                           }
                         }} />
      )}

      {invMsg && (
        <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          {invMsg}
        </div>
      )}

      {showTransfert && (
        <TransfertModal produits={produits} isAdmin={role === 'admin'}
                        onClose={() => setShowTransfert(false)}
                        onDone={() => dispatch(fetchProduits())} />
      )}

      {showValorisation && (
        <ValorisationModal onClose={() => setShowValorisation(false)} />
      )}

      {archiveNotif && (
        <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-foreground">
          <Package className="size-4 text-warning" />
          <span>{archiveNotif}</span>
          <Button variant="outline" size="sm" className="ml-auto"
                  onClick={() => { setShowArchived(true); setArchiveNotif(null) }}>
            Voir les archivés
          </Button>
        </div>
      )}

      {canWrite && visibleSelected.size > 0 && (
        <BulkProductBar
          count={visibleSelected.size}
          categories={categories}
          marques={marquesList}
          busy={bulkBusy}
          labelsBusy={labelsBusy}
          onAction={runBulk}
          onExport={exportSelection}
          onPrintLabels={printLabels}
          onClear={clearSelection}
        />
      )}
      {bulkMsg && (
        <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
          {bulkMsg}
        </div>
      )}

      {showForm && (
        <ProduitForm produit={editProduit} onClose={closeForm} onSaved={onSaved} />
      )}

      <div className="flex flex-col gap-4 lg:flex-row">
        <aside className="flex shrink-0 flex-col gap-1 lg:w-60">
          <Input
            type="search" leading={<Package className="size-4" />}
            placeholder="Chercher partout…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <button type="button"
                  className={`mt-1 flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors ${!activeCat && !searching ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/60'}`}
                  onClick={() => { setActiveCat(''); setSearch('') }}>
            <span>Tout le catalogue</span>
            <Badge>{actifs.length}</Badge>
          </button>
          {allGroups.map(c => (
            <button key={c.nom} type="button"
                    className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors ${activeCat === c.nom && !searching ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/60'}`}
                    onClick={() => { setActiveCat(c.nom); setSearch('') }}>
              <span className="truncate">{c.nom}</span>
              <Badge>{c.count}</Badge>
            </button>
          ))}

          {/* Filtres transverses : qualité de catalogue (prix/SKU manquants) + marque. */}
          <div className="mt-3 flex flex-col gap-1 border-t border-border pt-3">
            <span className="px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Filtres</span>
            {noPriceCount > 0 && (
              <button type="button"
                      className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors ${filterNoPrice ? 'bg-warning/15 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/60'}`}
                      onClick={() => setFilterNoPrice(v => !v)}>
                <span>Sans prix (à renseigner)</span>
                <Badge tone="warning">{noPriceCount}</Badge>
              </button>
            )}
            {noSkuCount > 0 && (
              <button type="button"
                      className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors ${filterNoSku ? 'bg-warning/15 font-medium text-foreground' : 'text-muted-foreground hover:bg-muted/60'}`}
                      onClick={() => setFilterNoSku(v => !v)}>
                <span>Sans SKU</span>
                <Badge tone="warning">{noSkuCount}</Badge>
              </button>
            )}
            {marquesPresentes.length > 1 && (
              <div className="px-1 pt-1">
                <Select value={filterMarque || '__all'}
                        onValueChange={v => setFilterMarque(v === '__all' ? '' : v)}>
                  <SelectTrigger className="h-9"><SelectValue placeholder="Toutes les marques" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">Toutes les marques</SelectItem>
                    {marquesPresentes.map(m => <SelectItem key={m} value={m}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          {searching && (
            <p className="mb-3 text-sm text-muted-foreground">
              {filtered.length} résultat{filtered.length !== 1 ? 's' : ''} pour
              « {search} » dans tout le catalogue
            </p>
          )}
          <div className="flex flex-col gap-6">
            {groups.map(c => (
              <section key={c.nom} className="flex flex-col gap-2">
                <h3 className="flex items-center gap-2 font-display text-base font-semibold tracking-tight">
                  {c.nom} <Badge>{c.count}</Badge>
                </h3>
                {c.brands.map(b => (
                  <div key={b.marque} className="flex flex-col gap-1.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{b.marque}</span>
                      <span className="h-px flex-1 bg-border" />
                      <span className="text-xs text-muted-foreground">{b.items.length} article{b.items.length !== 1 ? 's' : ''}</span>
                    </div>
                    {b.items.map(p => (
                      <CatalogueRow key={p.id} p={p} canWrite={canWrite} canDelete={canDelete}
                                    onEdit={openEdit} onDelete={handleDelete}
                                    categories={categories}
                                    onInlineSave={canWrite ? onInlineSave : null}
                                    selected={visibleSelected.has(p.id)}
                                    onToggleSelect={canWrite ? onToggleSelect : null} />
                    ))}
                  </div>
                ))}
              </section>
            ))}
          </div>
          {/* Valeur de vente HT du catalogue affiché (recalculée au filtre/recherche). */}
          {filtered.length > 0 && (
            <div className="mt-4 flex justify-end border-t border-border pt-3 text-sm text-muted-foreground">
              Valeur vente du catalogue affiché :{' '}
              <strong className="ml-1 text-foreground tabular-nums">{fmtNum2(valeurVenteFiltree)} DH HT</strong>
            </div>
          )}
          {filtered.length === 0 && !loading && (
            actifs.length === 0 ? (
              // Catalogue réellement vide : encart d'amorçage.
              <EmptyState
                icon={PackageOpen}
                title="Aucun produit"
                description="Créez votre premier produit pour démarrer le catalogue."
                action={canWrite
                  ? <Button size="sm" onClick={openNew}><Plus /> Nouveau produit</Button>
                  : undefined}
              />
            ) : (
              // Vide après filtre/recherche : on propose d'effacer les filtres.
              <EmptyState
                icon={PackageOpen}
                title={filterLow ? 'Aucun produit en stock bas' : 'Aucun résultat'}
                description={filterLow
                  ? 'Tous les produits sont au-dessus de leur seuil d’alerte.'
                  : search
                    ? `Aucun résultat pour « ${search} » avec ces filtres`
                    : 'Aucun produit ne correspond aux filtres actifs.'}
                action={(
                  <Button size="sm" variant="outline" onClick={() => {
                    setSearch(''); setFilterLow(false); setFilterNoPrice(false)
                    setFilterNoSku(false); setFilterMarque(''); setActiveCat('')
                  }}>Effacer les filtres</Button>
                )}
              />
            )
          )}
        </main>
      </div>

      {showArchived && (
        <div className="mt-6 flex flex-col gap-2">
          <h3 className="flex items-center gap-2 font-display text-base font-semibold tracking-tight text-muted-foreground">
            Produits archivés
            {produitsArchived.length > 0 && <Badge tone="warning">{produitsArchived.length}</Badge>}
          </h3>
          {produitsArchived.length === 0 ? (
            <EmptyState icon={Archive} title="Aucun produit archivé"
                        description="Les produits supprimés avec historique apparaissent ici." />
          ) : (
            <div className="opacity-80">
              <DataTable
                data={produitsArchived}
                columns={archivedColumns}
                getRowId={(p) => p.id}
                rowActions={archivedRowActions}
                searchPlaceholder="Rechercher un produit archivé…"
                globalColumns={['sku', 'nom']}
                emptyTitle="Aucun produit archivé"
                emptyDescription="Les produits supprimés avec historique apparaissent ici."
                aria-label="Produits archivés"
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
