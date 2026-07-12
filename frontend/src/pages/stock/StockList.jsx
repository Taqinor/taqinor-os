import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  Plus, Upload, Download, Truck, Calculator, Wallet, AlertTriangle,
  Archive, PackageOpen, Pencil, Trash2, RotateCcw, Package, QrCode, ScanLine,
  History, LineChart,
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
import ProduitDetail from './ProduitDetail'
import { CatalogueTable } from './CatalogueTable'
import PilotageStock from './PilotageStock'
import BulkProductBar from './BulkProductBar'
import ExcelImport from '../../components/ExcelImport'
import stockApi from '../../api/stockApi'
import api from '../../api/axios'
import { formatNumber, formatMAD } from '../../lib/format'
import { toggleId, pruneSelection, bulkResultMessage } from '../../features/crm/bulk'
import {
  groupCatalogue, searchCatalogue, sansPrix,
} from '../../features/stock/catalogue'
import { validateTransfert, totalVentile, quantiteEmplacement, produitDansEmplacement } from '../../features/stock/emplacements'
import { normalizeCode, isValidCode, resolveTarget } from '../../features/stock/labels'
import BarcodeScanner from '../../features/pwa/BarcodeScanner'
import { toastError, toastSuccess, toastWithUndo } from '../../lib/toast'
import { openPdfInGesture } from '../../utils/pdfBlob'
import { useCanCreateProduit, useHasPermission, useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import {
  Button, IconButton, Badge, Checkbox, Input, Spinner, Skeleton,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription,
  AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
  EmptyState, DataTable, Progress,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../ui'
import { MoreHorizontal } from 'lucide-react'
import { useSavedViews } from '../../hooks/useSavedViews'

const SL_SAVED_VIEWS_KEY = 'taqinor.stock.produits.savedViews'

const fmtNum2 = (n) => formatNumber(n, { decimals: 2 })

// Suggestion de quantité à commander pour un produit en stock bas :
// vise un réassort à 2× le seuil d'alerte, jamais négative.
const suggestionCommande = (p) => {
  const seuil = Number(p.seuil_alerte) || 0
  const stock = Number(p.quantite_stock) || 0
  return Math.max(seuil * 2 - stock, 0)
}

// Petit tableau interne stylé (lecture seule) — utilisé dans les modals.
// overflow-x-auto : défile horizontalement sur mobile sans casser la mise en page.
function MiniTable({ head, children, className = '' }) {
  return (
    <div className={`overflow-x-auto rounded-lg border border-border ${className}`}>
      <table className="w-full min-w-[28rem] text-sm">
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
  const [recherche, setRecherche] = useState('')
  const allRows = (produits ?? []).filter((p) => !p.is_archived)
  // Recherche interne (grand catalogue) sur nom/SKU.
  const rows = recherche.trim()
    ? searchCatalogue(allRows, recherche)
    : allRows

  const submit = async () => {
    // On collecte sur TOUT le catalogue (les comptages saisis avant un filtre
    // de recherche ne doivent pas être perdus).
    const lignes = allRows
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

        <Input type="search" leading={<Package className="size-4" />}
               placeholder="Filtrer les produits à compter…"
               value={recherche} onChange={(e) => setRecherche(e.target.value)} />

        <div className="max-h-80 overflow-auto">
          <MiniTable head={['Produit', 'SKU', 'Stock actuel', 'Compté', 'Écart']}>
            {rows.map((p) => {
              const saisie = counts[p.id]
              const compte = saisie === undefined || saisie === '' ? null : parseInt(saisie, 10)
              const delta = compte === null || Number.isNaN(compte) ? null : compte - p.quantite_stock
              return (
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
                  <td className="px-3 py-2 tabular-nums">
                    {delta === null
                      ? <span className="text-muted-foreground">—</span>
                      : (
                        <span className={delta > 0 ? 'text-success' : delta < 0 ? 'text-destructive' : 'text-muted-foreground'}>
                          {delta > 0 ? '+' : ''}{delta}
                        </span>
                      )}
                  </td>
                </tr>
              )
            })}
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
  const [exporting, setExporting] = useState(false)
  useEffect(() => {
    stockApi.valorisation()
      .then((r) => setData(r.data))
      .catch(() => setError('Échec du chargement de la valorisation.'))
  }, [])
  const isEmpty = data && (!data.lignes || data.lignes.length === 0)
  const sourceLabel = (s) => (s === 'achats' ? 'Achats reçus' : s === 'catalogue' ? 'Prix catalogue' : '—')
  // Export Excel (admin/INTERNE — coûts jamais client-facing).
  const exportXlsx = async () => {
    setExporting(true)
    try {
      const res = await api.get('/stock/valorisation-xlsx/', { responseType: 'blob' })
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url; a.download = 'valorisation.xlsx'
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch { setError('Export indisponible.') } finally { setExporting(false) }
  }
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
        {isEmpty && (
          <EmptyState icon={Wallet} title="Aucun stock à valoriser"
                      description="Aucune quantité en stock à valoriser pour le moment." />
        )}
        {data && !isEmpty && (
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
              <MiniTable head={['Produit', 'Emplacement', 'Qté', 'Coût moyen', 'Source', 'Valeur']}>
                {data.lignes.map((l, i) => (
                  <tr key={`${l.produit_id}-${l.emplacement_nom}-${i}`} className="border-t border-border">
                    <td className="px-3 py-2">{l.designation}</td>
                    <td className="px-3 py-2">{l.emplacement_nom}</td>
                    <td className="px-3 py-2 tabular-nums">{l.quantite}</td>
                    <td className="px-3 py-2 tabular-nums">{fmtNum2(l.cout_moyen)} DH</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{sourceLabel(l.source)}</td>
                    <td className="px-3 py-2 tabular-nums">{fmtNum2(l.valeur)} DH</td>
                  </tr>
                ))}
              </MiniTable>
            </div>
          </>
        )}

        <DialogFooter>
          {data && !isEmpty && (
            <Button type="button" variant="outline" loading={exporting} onClick={exportXlsx}>
              <Download /> Exporter Excel
            </Button>
          )}
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
  // WR4 / FG62 — suggestions de réappro par emplacement (admin).
  const [suggestions, setSuggestions] = useState([])
  const rows = (produits ?? []).filter((p) => !p.is_archived)

  // setState arrive dans les callbacks .then (jamais synchrone dans l'effet).
  const loadEmplacements = () => stockApi.getEmplacements()
    .then((r) => setEmplacements(r.data?.results ?? r.data ?? [])).catch(() => {})
  const loadTransferts = () => stockApi.getTransferts({ ordering: '-date' })
    .then((r) => setTransferts((r.data?.results ?? r.data ?? []).slice(0, 8)))
    .catch(() => {})
  const loadSuggestions = () => {
    if (!isAdmin) return
    stockApi.suggestionsReapproEmplacement()
      .then((r) => setSuggestions(r.data ?? [])).catch(() => {})
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadEmplacements(); loadTransferts(); loadSuggestions() }, [])

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
    catch (err) { setError(messageSuppressionEmplacement(err)) }
  }

  const empOptions = emplacements.filter((e) => !e.archived)
  // Quantité disponible à la source (plafonne et guide la saisie — N15).
  const dispoSource = quantiteEmplacement(breakdown, source)

  // Améliore le message FR si une suppression d'emplacement échoue (409).
  const messageSuppressionEmplacement = (err) => {
    const detail = err.response?.data?.detail
    if (err.response?.status === 409 || /stock|transf/i.test(detail || '')) {
      return detail || 'Cet emplacement détient du stock — transférez-le d\'abord.'
    }
    return detail || 'Suppression impossible.'
  }

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
            <Input id="tr-qte" type="number" min="1" max={dispoSource || undefined} inputMode="numeric"
                   value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            {source && (
              <span className="text-xs text-muted-foreground">dispo : {dispoSource}</span>
            )}
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

        {isAdmin && suggestions.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <h4 className="text-sm font-semibold">Réapprovisionnement par emplacement</h4>
            <p className="text-xs text-muted-foreground">
              Emplacements sous leur seuil minimal — transfert suggéré depuis le dépôt principal.
            </p>
            <div className="max-h-48 overflow-auto">
              <MiniTable head={['Produit', 'Emplacement', 'Qté', 'Seuil min', 'À transférer', 'Depuis']}>
                {suggestions.map((s, i) => (
                  <tr key={`${s.produit_id}-${s.emplacement_id}-${i}`} className="border-t border-border">
                    <td className="px-3 py-2">{s.produit_nom}</td>
                    <td className="px-3 py-2">{s.emplacement_nom}</td>
                    <td className="px-3 py-2 tabular-nums">{s.quantite_actuelle}</td>
                    <td className="px-3 py-2 tabular-nums">{s.seuil_min}</td>
                    <td className="px-3 py-2 font-semibold tabular-nums">{s.qte_suggere_transfert}</td>
                    <td className="px-3 py-2">{s.source_nom ?? <span className="text-muted-foreground">—</span>}</td>
                  </tr>
                ))}
              </MiniTable>
            </div>
          </div>
        )}

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
  // ARC47 — gating via le hook partagé (plus de lecture directe de state.auth
  // pour un droit). Rôle fin (ex. « Commerciale » lecture seule) : les
  // permissions priment ; comptes hérités sans rôle fin : repli par palier.
  // Les deux hooks sont appelés inconditionnellement (règle des hooks) ;
  // `hasFinePermissions` (présence de codes ERP, PAS un droit) choisit ensuite
  // la branche — sémantique identique à l'ancien ternaire.
  const hasFinePermissions = useSelector(s => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole
  const canDelete = useIsAdmin()
  // QG5 — la CRÉATION de produit est restreinte à Directeur + Commercial
  // responsable (UX miroir de la garde backend QG4) ; canWrite reste pour la
  // modification/l'import, séparés de la création.
  const canCreateProduit = useCanCreateProduit()

  const [search, setSearch]           = useState('')
  const [showForm, setShowForm]       = useState(false)
  const [editProduit, setEditProduit] = useState(null)
  // ZPUR10/ZSTK3 — fiche produit (quantité en commande + prévisionnel).
  const [detailProduit, setDetailProduit] = useState(null)
  const [filterLow, setFilterLow]     = useState(false)
  const [filterNoPrice, setFilterNoPrice] = useState(false)  // produits sans prix de vente
  const [filterNoSku, setFilterNoSku]     = useState(false)  // produits sans SKU
  const [filterMarque, setFilterMarque]   = useState('')     // '' = toutes les marques
  const [filterEmplacement, setFilterEmplacement] = useState('') // '' = tous les emplacements
  const [emplacementsList, setEmplacementsList]   = useState([])
  const [activeCat, setActiveCat]     = useState('')   // '' = tout le catalogue
  const [showArchived, setShowArchived]   = useState(false)
  // Vues enregistrées (FG11).
  const { savedViews: stockSavedViews, saveView: saveStockView, deleteView: deleteStockView } = useSavedViews(SL_SAVED_VIEWS_KEY)
  const saveCurrentStockView = () => {
    const name = window.prompt('Nom de la vue enregistrée :')
    saveStockView(name, { search, activeCat, filterMarque, filterEmplacement, filterLow, filterNoPrice, filterNoSku })
  }
  const applyStockView = (v) => {
    const s = v.state || {}
    if (s.search !== undefined) setSearch(s.search)
    if (s.activeCat !== undefined) setActiveCat(s.activeCat)
    if (s.filterMarque !== undefined) setFilterMarque(s.filterMarque)
    if (s.filterEmplacement !== undefined) setFilterEmplacement(s.filterEmplacement)
    if (s.filterLow !== undefined) setFilterLow(s.filterLow)
    if (s.filterNoPrice !== undefined) setFilterNoPrice(s.filterNoPrice)
    if (s.filterNoSku !== undefined) setFilterNoSku(s.filterNoSku)
  }
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
  // VX33 — panneau « Pilotage stock » (analytics + auto-BCF) : la tour de
  // contrôle du stock, ouverte PAR DÉFAUT (le bouton reste pour la masquer).
  const [showPilotage, setShowPilotage] = useState(true)
  // N20 — étiquettes QR/code-barres + champ de scan (résolution serveur).
  const [labelsBusy, setLabelsBusy]   = useState(false)
  const [scanOpen, setScanOpen]       = useState(false)
  const [scanCode, setScanCode]       = useState('')
  const [scanBusy, setScanBusy]       = useState(false)
  const [camOpen, setCamOpen]         = useState(false) // FG384 — scan caméra

  useEffect(() => {
    dispatch(fetchProduits()); dispatch(fetchCategories())
    stockApi.getMarques().then(r => setMarques(r.data?.results ?? r.data ?? [])).catch(() => {})
    stockApi.getEmplacements()
      .then(r => setEmplacementsList((r.data?.results ?? r.data ?? []).filter(e => !e.archived)))
      .catch(() => {})
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
  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const printLabels = async () => {
    if (!visibleSelected.size) return
    const pending = openPdfInGesture()
    setLabelsBusy(true)
    try {
      const res = await stockApi.etiquettesProduits([...visibleSelected])
      const blob = new Blob([res.data], { type: 'application/pdf' })
      if (!pending.deliver(blob, 'etiquettes.pdf')) {
        toastError('Ouverture bloquée par le navigateur.')
      }
    } catch { toastError('Génération des étiquettes indisponible.') }
    finally { setLabelsBusy(false) }
  }
  // N20 — Résout un code scanné/saisi (PRODUIT:<id> / SYSTEME:<id>) et navigue
  // vers la fiche correspondante (lecture seule côté serveur).
  const runScan = async (rawCode) => {
    const code = normalizeCode(typeof rawCode === 'string' ? rawCode : scanCode)
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
  // FG384 — un code détecté par la caméra remplit le champ, ferme la caméra et
  // lance la résolution existante (lecture seule côté serveur).
  const onCameraDetected = (value) => {
    const code = normalizeCode(value)
    setScanCode(code)
    setCamOpen(false)
    if (isValidCode(code)) runScan(code)
    else toastError('Code lu, mais illisible. Attendu : PRODUIT:<id> ou SYSTEME:<id>.')
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
    if (filterEmplacement) list = list.filter(p => produitDansEmplacement(p, filterEmplacement))
    list = searchCatalogue(list, search)
    return list
  }, [actifs, search, filterLow, filterNoPrice, filterNoSku, filterMarque, filterEmplacement])

  // Compteurs des filtres rail (sur le catalogue actif complet).
  const noPriceCount = useMemo(() => actifs.filter(p => sansPrix(p)).length, [actifs])
  const noSkuCount = useMemo(() => actifs.filter(p => !(p.sku ?? '').trim()).length, [actifs])
  // VX33 — jauge « santé catalogue » : % de produits actifs avec prix / SKU
  // renseignés (dérivé des mêmes compteurs, aucun nouvel appel réseau).
  const pctAvecPrix = useMemo(
    () => (actifs.length ? Math.round(((actifs.length - noPriceCount) / actifs.length) * 100) : 100),
    [actifs.length, noPriceCount],
  )
  const pctAvecSku = useMemo(
    () => (actifs.length ? Math.round(((actifs.length - noSkuCount) / actifs.length) * 100) : 100),
    [actifs.length, noSkuCount],
  )
  const toneSante = (pct) => (pct >= 90 ? 'success' : pct >= 60 ? 'warning' : 'danger')
  // Liste des marques présentes (pour le filtre par marque).
  const marquesPresentes = useMemo(() => {
    const set = new Set(actifs.map(p => (p.marque || '').trim() || 'Génériques'))
    return [...set].sort((a, b) => a.localeCompare(b))
  }, [actifs])
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
  // Rail de catégories (catalogue actif complet) — pilote le filtre `activeCat`.
  const allGroups = useMemo(() => groupCatalogue(actifs), [actifs])

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
        // VX95 — archivage (produit avec mouvements) déjà commis serveur :
        // « Annuler » relance l'action inverse (unarchiveProduit). Un vrai
        // delete (204, non archivé) n'est pas réversible ici — pas de toast.
        toastWithUndo({
          message: 'Produit archivé.',
          onUndo: async () => {
            try {
              await dispatch(unarchiveProduit(p.id)).unwrap()
              dispatch(fetchProduitsArchived())
            } catch { toastError('Désarchivage impossible.') }
          },
        })
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
      toastWithUndo({
        message: 'Produit désarchivé.',
        onUndo: async () => {
          try {
            await dispatch(deleteProduit(p.id)).unwrap()
            dispatch(fetchProduitsArchived())
          } catch { toastError('Archivage impossible.') }
        },
      })
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
      cell: (v) => `${formatMAD(v, { withSymbol: false })} DH` },
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
          {/* Actions secondaires : inline sur écran large, repliées en menu « … » sur mobile. */}
          <div className="hidden flex-wrap items-center gap-2 sm:flex">
            <Button variant={showPilotage ? 'secondary' : 'outline'} size="sm"
                    onClick={() => setShowPilotage(v => !v)}
                    title="Pilotage stock : réapprovisionnement, prévisions, rotation, péremptions">
              <LineChart /> Pilotage
            </Button>
            {canDelete && (
              <Button variant={showArchived ? 'secondary' : 'outline'} size="sm"
                      onClick={() => setShowArchived(v => !v)}>
                <Archive /> {showArchived ? 'Masquer archivés' : `Archivés${produitsArchived.length > 0 ? ` (${produitsArchived.length})` : ''}`}
              </Button>
            )}
            {canDelete && (
              <Button variant="outline" size="sm" onClick={() => setShowInventaire(true)}
                      title="Inventaire physique : saisir un comptage et ajuster le stock">
                <Calculator /> Inventaire
              </Button>
            )}
            {canDelete && (
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
          </div>

          {/* Menu compact « … » — uniquement sur mobile. */}
          <div className="sm:hidden">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" aria-label="Plus d'actions">
                  <MoreHorizontal /> Actions
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setShowPilotage(v => !v)}>
                  <LineChart /> Pilotage
                </DropdownMenuItem>
                {canDelete && (
                  <DropdownMenuItem onSelect={() => setShowArchived(v => !v)}>
                    <Archive /> {showArchived ? 'Masquer archivés' : 'Archivés'}
                  </DropdownMenuItem>
                )}
                {canDelete && (
                  <DropdownMenuItem onSelect={() => setShowInventaire(true)}>
                    <Calculator /> Inventaire
                  </DropdownMenuItem>
                )}
                {canDelete && (
                  <DropdownMenuItem onSelect={() => setShowValorisation(true)}>
                    <Wallet /> Valorisation
                  </DropdownMenuItem>
                )}
                {canWrite && (
                  <DropdownMenuItem onSelect={() => setShowTransfert(true)}>
                    <Truck /> Transférer
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem onSelect={() => setScanOpen(v => !v)}>
                  <ScanLine /> Scanner
                </DropdownMenuItem>
                <DropdownMenuItem onSelect={exportFiltered}>
                  <Download /> Exporter Excel
                </DropdownMenuItem>
                {canWrite && (
                  <DropdownMenuItem onSelect={() => setShowImport(true)}>
                    <Upload /> Importer
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>

          {canCreateProduit && (
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
          <Button size="sm" loading={scanBusy} disabled={!scanCode.trim()} onClick={() => runScan()}>
            Ouvrir la fiche
          </Button>
          <Button size="sm" variant="outline"
                  onClick={() => setCamOpen(v => !v)}
                  title="Scanner un code avec la caméra">
            <ScanLine /> {camOpen ? 'Fermer la caméra' : 'Caméra'}
          </Button>
          <Button size="sm" variant="ghost"
                  onClick={() => { setScanOpen(false); setScanCode(''); setCamOpen(false) }}>
            Fermer
          </Button>
          {camOpen && (
            <div className="mt-2 w-full max-w-sm">
              <BarcodeScanner
                onDetected={onCameraDetected}
                onClose={() => setCamOpen(false)}
              />
            </div>
          )}
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

      {showPilotage && (
        <PilotageStock onBcfGenere={() => dispatch(fetchProduits())} />
      )}

      {showTransfert && (
        <TransfertModal produits={produits} isAdmin={canDelete}
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
      {detailProduit && (
        <ProduitDetail produit={detailProduit} onClose={() => setDetailProduit(null)} />
      )}

      <div className="flex flex-col gap-4 lg:flex-row">
        <aside className="flex shrink-0 flex-col gap-1 lg:w-60">
          <Input
            type="search" leading={<Package className="size-4" />}
            placeholder="Chercher partout…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <div className="lp-saved-views mt-1">
            <button type="button" className="lp-saved-view-apply text-xs" onClick={saveCurrentStockView}>
              ⭐ Enregistrer cette vue
            </button>
            {stockSavedViews.map((v) => (
              <span key={v.name} className="lp-saved-view-chip">
                <button type="button" className="lp-saved-view-apply"
                        onClick={() => applyStockView(v)} title="Appliquer cette vue">
                  {v.name}
                </button>
                <button type="button" className="lp-saved-view-del"
                        onClick={() => deleteStockView(v.name)}
                        aria-label={`Supprimer la vue ${v.name}`}>
                  ✕
                </button>
              </span>
            ))}
          </div>

          {/* VX33 — mini-jauge « santé catalogue », au-dessus du rail de
              catégories : % de produits actifs avec prix / SKU renseignés. */}
          {actifs.length > 0 && (
            <div className="mt-1 flex flex-col gap-2 rounded-md border border-border p-2.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Santé catalogue
              </span>
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Prix renseigné</span>
                  <span className="font-medium tabular-nums text-foreground">{pctAvecPrix}%</span>
                </div>
                <Progress value={pctAvecPrix} tone={toneSante(pctAvecPrix)} aria-label="Part du catalogue avec un prix renseigné" />
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>SKU renseigné</span>
                  <span className="font-medium tabular-nums text-foreground">{pctAvecSku}%</span>
                </div>
                <Progress value={pctAvecSku} tone={toneSante(pctAvecSku)} aria-label="Part du catalogue avec un SKU renseigné" />
              </div>
            </div>
          )}

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
            {/* N15 — filtre par emplacement : ne montre que le stock détenu dans
                l'emplacement choisi (ex. Camionnette). */}
            {emplacementsList.length > 1 && (
              <div className="px-1 pt-1">
                <Select value={filterEmplacement || '__all'}
                        onValueChange={v => setFilterEmplacement(v === '__all' ? '' : v)}>
                  <SelectTrigger className="h-9"><SelectValue placeholder="Tous les emplacements" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__all">Tous les emplacements</SelectItem>
                    {emplacementsList.map(e => (
                      <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>
                    ))}
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
          {/* J142 — Catalogue unifié sur le moteur DataTable (virtualisation des
              grandes listes, édition de cellule clavier, cartes mobiles, ligne de
              sous-totaux). Le rail de catégories à gauche pilote toujours le filtre. */}
          {filtered.length > 0 && (
            <CatalogueTable
              produits={filtered}
              loading={loading}
              canWrite={canWrite}
              canDelete={canDelete}
              onEdit={openEdit}
              onDelete={handleDelete}
              onHistorique={(prod) => navigate(`/stock/mouvements?produit=${prod.id}`)}
              onDetail={(prod) => setDetailProduit(prod)}
              onReapprovisionner={canWrite ? (prod) => navigate('/stock/bons-commande-fournisseur', {
                state: { prefillBcf: {
                  produit: prod.id,
                  fournisseur: prod.fournisseur?.id ?? null,
                  quantite: suggestionCommande(prod) || 1,
                } },
              }) : null}
              onInlineSave={canWrite ? onInlineSave : null}
              selected={visibleSelected}
              onToggleSelect={canWrite ? onToggleSelect : null}
            />
          )}
          {filtered.length === 0 && !loading && (
            actifs.length === 0 ? (
              // Catalogue réellement vide : encart d'amorçage.
              <EmptyState
                icon={PackageOpen}
                title="Aucun produit"
                description="Créez votre premier produit pour démarrer le catalogue."
                action={canCreateProduit
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
                    setFilterNoSku(false); setFilterMarque(''); setFilterEmplacement(''); setActiveCat('')
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
