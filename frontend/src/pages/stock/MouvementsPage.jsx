import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import { Plus, ArrowDownUp, X, Download, LayoutGrid, List } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import {
  fetchMouvements,
  fetchProduits,
  createMouvement,
} from '../../features/stock/store/stockSlice'
import {
  Button, Badge, Segmented, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField, FormActions,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'

// ZSTK7 — options du regroupement pivot (« Vue groupée »).
const AGREGATION_GROUP_BY = [
  { value: 'produit', label: 'Par produit' },
  { value: 'type', label: 'Par type' },
  { value: 'mois', label: 'Par mois' },
  { value: 'emplacement', label: 'Par emplacement' },
]

// Tonalité du badge par type de mouvement (taxonomie de couleurs commune).
const TYPE_META = {
  entree:     { label: 'Entrée',     tone: 'success' },
  sortie:     { label: 'Sortie',     tone: 'danger' },
  ajustement: { label: 'Ajustement', tone: 'warning' },
  transfert:  { label: 'Transfert',  tone: 'info' },
}

const TABS = [
  { value: 'tous',       label: 'Tous' },
  { value: 'entree',     label: 'Entrées' },
  { value: 'sortie',     label: 'Sorties' },
  { value: 'ajustement', label: 'Ajustements' },
  { value: 'transfert',  label: 'Transferts' },
]

export default function MouvementsPage() {
  const dispatch = useDispatch()
  const { mouvements, produits, loading, error } = useSelector(s => s.stock)
  // ARC47 — gating via le hook partagé. Rôle fin : la permission stock_mouvement
  // décide ; comptes hérités : repli par palier. `hasFinePermissions` (présence
  // de codes ERP, PAS un droit) choisit la branche ; hooks inconditionnels.
  const hasFinePermissions = useSelector(s => (s.auth.permissions || []).length > 0)
  // VX81 — nom d'export horodaté, société incluse quand connue.
  const societe = useSelector(s => s.parametres?.profile?.nom)
  const canPostViaPerm = useHasPermission('stock_mouvement')
  const canPostViaRole = useIsAdminOrResponsable()
  const canPostMouvement = hasFinePermissions ? canPostViaPerm : canPostViaRole

  const [activeTab, setActiveTab] = useState('tous')
  // Pré-filtre par produit (lien « historique » depuis le catalogue) + saisie
  // pré-remplie (?nouveau=1) : un seul aller-retour depuis la fiche produit.
  const [searchParams, setSearchParams] = useSearchParams()
  const produitParam = searchParams.get('produit')
  // Ouvre le formulaire d'emblée si on arrive avec ?nouveau=1 (état initial).
  const [showForm, setShowForm] = useState(
    () => searchParams.get('nouveau') === '1' && canPostMouvement,
  )

  // Transferts entre emplacements : source de données distincte (TransfertStock,
  // ce ne sont PAS des MouvementStock) — chargée à l'ouverture de l'onglet.
  const [transferts, setTransferts] = useState([])
  const [transfertsLoading, setTransfertsLoading] = useState(false)

  // ZSTK7 — « Vue groupée / pivot » : quantités entrées/sorties/nettes
  // agrégées par produit/type/mois/emplacement (mouvements/agregation/).
  const [vuePivot, setVuePivot] = useState(false)
  const [pivotGroupBy, setPivotGroupBy] = useState('produit')
  const [pivotRows, setPivotRows] = useState([])
  const [pivotLoading, setPivotLoading] = useState(false)
  const [pivotError, setPivotError] = useState(null)
  const [pivotExportBusy, setPivotExportBusy] = useState(false)

  useEffect(() => {
    if (!vuePivot) return undefined
    let cancelled = false
    const load = () => Promise.resolve()
      .then(() => { if (!cancelled) { setPivotLoading(true); setPivotError(null) } })
      .then(() => stockApi.mouvementsAgregation({ group_by: pivotGroupBy }))
      .then((r) => { if (!cancelled) setPivotRows(r.data ?? []) })
      .catch(() => { if (!cancelled) setPivotError('Agrégation indisponible. Réessayez.') })
      .finally(() => { if (!cancelled) setPivotLoading(false) })
    load()
    return () => { cancelled = true }
  }, [vuePivot, pivotGroupBy])

  const exportPivotXlsx = async () => {
    setPivotExportBusy(true)
    try {
      const res = await stockApi.mouvementsAgregationXlsx({ group_by: pivotGroupBy })
      downloadBlob(res.data, stampedFilename('mouvements-agregation', 'xlsx', societe))
    } catch {
      setPivotError('Export indisponible. Réessayez.')
    } finally { setPivotExportBusy(false) }
  }

  useEffect(() => {
    dispatch(fetchMouvements())
    if (!produits.length) dispatch(fetchProduits())
  }, [dispatch, produits.length])

  useEffect(() => {
    if (activeTab !== 'transfert') return undefined
    let cancelled = false
    const load = async () => {
      setTransfertsLoading(true)
      try {
        const r = await stockApi.getTransferts({ ordering: '-date' })
        if (!cancelled) setTransferts(r.data?.results ?? r.data ?? [])
      } catch {
        if (!cancelled) setTransferts([])
      } finally {
        if (!cancelled) setTransfertsLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [activeTab])

  const produitFiltre = useMemo(
    () => produits.find(p => String(p.id) === String(produitParam)) ?? null,
    [produits, produitParam],
  )
  const clearProduitFiltre = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('produit')
    setSearchParams(next, { replace: true })
  }

  // WR4 / FG60 — export Excel de la liste (filtrée) des mouvements. On envoie
  // les mêmes filtres que la vue (type + produit) que le backend applique.
  const [exportBusy, setExportBusy] = useState(false)
  const [exportError, setExportError] = useState(null)
  const exportXlsx = async () => {
    setExportBusy(true); setExportError(null)
    try {
      const params = {}
      if (activeTab !== 'tous') params.type_mouvement = activeTab
      if (produitParam) params.produit = produitParam
      const res = await stockApi.exportMouvementsXlsx(params)
      downloadBlob(res.data, stampedFilename('mouvements-stock', 'xlsx', societe))
    } catch {
      setExportError('Export indisponible. Réessayez.')
    } finally { setExportBusy(false) }
  }

  const filtered = useMemo(() => {
    let list = activeTab === 'tous'
      ? mouvements
      : mouvements.filter(m => m.type_mouvement === activeTab)
    if (produitParam) list = list.filter(m => String(m.produit) === String(produitParam))
    return list
  }, [mouvements, activeTab, produitParam])

  const counts = useMemo(() => ({
    tous:       mouvements.length,
    entree:     mouvements.filter(m => m.type_mouvement === 'entree').length,
    sortie:     mouvements.filter(m => m.type_mouvement === 'sortie').length,
    ajustement: mouvements.filter(m => m.type_mouvement === 'ajustement').length,
    transfert:  mouvements.filter(m => m.type_mouvement === 'transfert').length,
  }), [mouvements])

  const tabOptions = TABS.map(t => ({
    ...t,
    label: counts[t.value] > 0 ? `${t.label} (${counts[t.value]})` : t.label,
  }))

  // Colonnes DataTable (la recherche globale balaie produit / référence / note).
  const columns = useMemo(() => [
    {
      id: 'date', header: 'Date', width: 150, searchable: false,
      accessor: (m) => m.date,
      cell: (v) => (
        <span className="whitespace-nowrap">
          {new Date(v).toLocaleDateString('fr-FR')}{' '}
          <span className="text-xs text-muted-foreground">
            {new Date(v).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </span>
      ),
    },
    {
      id: 'produit_nom', header: 'Produit', minWidth: 160,
      accessor: (m) => m.produit_nom ?? String(m.produit ?? ''),
    },
    {
      id: 'type', header: 'Type', width: 130, searchable: false,
      accessor: (m) => m.type_mouvement,
      cell: (v) => {
        const meta = TYPE_META[v] ?? TYPE_META.entree
        return <Badge tone={meta.tone}>{meta.label}</Badge>
      },
    },
    {
      id: 'quantite_avant', header: 'Avant', align: 'right', width: 90, searchable: false,
      cell: (v) => <span className="text-muted-foreground">{v}</span>,
    },
    {
      id: 'mouvement', header: 'Mouvement', align: 'right', width: 110, searchable: false,
      accessor: (m) => m.quantite_apres - m.quantite_avant,
      cell: (delta) => (
        <span className={delta >= 0 ? 'text-success' : 'text-destructive'}>
          {delta >= 0 ? '+' : ''}{delta}
        </span>
      ),
    },
    {
      id: 'quantite_apres', header: 'Après', align: 'right', width: 90, searchable: false,
      cell: (v) => <strong>{v}</strong>,
    },
    {
      id: 'reference', header: 'Référence', width: 140,
      accessor: (m) => m.reference ?? '',
      cell: (v) => (v ? <span className="font-mono text-xs">{v}</span> : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'note', header: 'Note', minWidth: 140,
      accessor: (m) => m.note ?? '',
      cell: (v) => (v ? <span className="line-clamp-2">{v}</span> : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'created_by_username', header: 'Par', width: 120,
      accessor: (m) => m.created_by_username ?? '',
      cell: (v) => <span className="text-muted-foreground">{v || '—'}</span>,
    },
  ], [])

  // Colonnes de l'onglet Transferts (entre emplacements — source → destination).
  const transfertColumns = useMemo(() => [
    {
      id: 'date', header: 'Date', width: 150, searchable: false,
      accessor: (t) => t.date,
      cell: (v) => (
        <span className="whitespace-nowrap">
          {new Date(v).toLocaleDateString('fr-FR')}{' '}
          <span className="text-xs text-muted-foreground">
            {new Date(v).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </span>
      ),
    },
    { id: 'produit_nom', header: 'Produit', minWidth: 160, accessor: (t) => t.produit_nom ?? '' },
    {
      id: 'trajet', header: 'De → Vers', minWidth: 180, searchable: false,
      accessor: (t) => `${t.source_nom ?? ''} → ${t.destination_nom ?? ''}`,
      cell: (v) => <span className="whitespace-nowrap">{v}</span>,
    },
    { id: 'quantite', header: 'Qté', align: 'right', width: 80, searchable: false,
      cell: (v) => <strong>{v}</strong> },
    {
      id: 'note', header: 'Note', minWidth: 140,
      accessor: (t) => t.note ?? '',
      cell: (v) => (v ? <span className="line-clamp-2">{v}</span> : <span className="text-muted-foreground">—</span>),
    },
    {
      id: 'created_by_username', header: 'Par', width: 120,
      accessor: (t) => t.created_by_username ?? '',
      cell: (v) => <span className="text-muted-foreground">{v || '—'}</span>,
    },
  ], [])

  // ZSTK7 — colonnes de la vue groupée (pivot) : libellé du groupe + quantités
  // entrées/sorties/nettes agrégées.
  const pivotColumns = useMemo(() => [
    { id: 'libelle', header: 'Groupe', minWidth: 200, accessor: (r) => r.libelle ?? '' },
    { id: 'entrees', header: 'Entrées', align: 'right', width: 110, searchable: false,
      accessor: (r) => r.entrees ?? 0,
      cell: (v) => <span className="text-success tabular-nums">+{v}</span> },
    { id: 'sorties', header: 'Sorties', align: 'right', width: 110, searchable: false,
      accessor: (r) => r.sorties ?? 0,
      cell: (v) => <span className="text-destructive tabular-nums">-{v}</span> },
    { id: 'net', header: 'Net', align: 'right', width: 110, searchable: false,
      accessor: (r) => r.net ?? ((r.entrees ?? 0) - (r.sorties ?? 0)),
      cell: (v) => (
        <strong className={v >= 0 ? 'text-success' : 'text-destructive'}>
          {v >= 0 ? '+' : ''}{v}
        </strong>
      ) },
  ], [])

  const isTransferts = activeTab === 'transfert'

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-xl font-semibold tracking-tight">Mouvements de stock</h2>
          {mouvements.length > 0 && (
            <Badge tone="primary">{mouvements.length}</Badge>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* ZSTK7 — bascule Vue liste / Vue groupée (pivot). */}
          {!isTransferts && (
            <Button variant="outline" size="sm"
                    onClick={() => setVuePivot((v) => !v)}
                    title={vuePivot ? 'Revenir à la liste détaillée' : 'Regrouper les mouvements (pivot)'}>
              {vuePivot ? <List /> : <LayoutGrid />}
              {vuePivot ? 'Vue liste' : 'Vue groupée'}
            </Button>
          )}
          {!isTransferts && !vuePivot && (
            <Button variant="outline" size="sm" loading={exportBusy} onClick={exportXlsx}
                    title="Exporter la liste (filtrée) des mouvements en Excel">
              <Download /> Exporter Excel
            </Button>
          )}
          {!isTransferts && vuePivot && (
            <Button variant="outline" size="sm" loading={pivotExportBusy} onClick={exportPivotXlsx}
                    title="Exporter l'agrégation affichée en Excel">
              <Download /> Exporter Excel
            </Button>
          )}
          {canPostMouvement && (
            <Button onClick={() => setShowForm(true)}>
              <Plus /> Saisir mouvement
            </Button>
          )}
        </div>
      </header>

      {exportError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {exportError}
        </div>
      )}

      {!vuePivot && (
        <Segmented
          size="sm"
          value={activeTab}
          onChange={setActiveTab}
          options={tabOptions}
          className="flex-wrap"
        />
      )}

      {vuePivot && (
        <div className="w-56">
          <Select value={pivotGroupBy} onValueChange={setPivotGroupBy}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {AGREGATION_GROUP_BY.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {produitFiltre && !vuePivot && (
        <div className="flex items-center gap-2">
          <Badge tone="primary" className="inline-flex items-center gap-1">
            Produit : {produitFiltre.nom}
            <button type="button" aria-label="Retirer le filtre produit"
                    className="ml-0.5 rounded hover:opacity-70" onClick={clearProduitFiltre}>
              <X className="size-3" />
            </button>
          </Badge>
        </div>
      )}

      {pivotError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {pivotError}
        </div>
      )}

      {vuePivot ? (
        <DataTable
          data={pivotRows}
          columns={pivotColumns}
          loading={pivotLoading}
          getRowId={(r, i) => `${r.libelle ?? ''}-${i}`}
          searchPlaceholder="Groupe…"
          globalColumns={['libelle']}
          emptyTitle="Aucune donnée"
          emptyDescription="Aucun mouvement à agréger sur cette période."
          aria-label="Mouvements de stock — vue groupée (pivot)"
        />
      ) : isTransferts ? (
        <DataTable
          data={produitParam
            ? transferts.filter(t => String(t.produit) === String(produitParam))
            : transferts}
          columns={transfertColumns}
          loading={transfertsLoading}
          getRowId={(t) => t.id}
          searchPlaceholder="Produit, emplacement, note…"
          globalColumns={['produit_nom', 'note']}
          emptyTitle="Aucun transfert"
          emptyDescription="Aucun transfert entre emplacements enregistré."
          aria-label="Transferts entre emplacements"
        />
      ) : (
        <DataTable
          data={filtered}
          columns={columns}
          loading={loading}
          error={error ? `Erreur : ${JSON.stringify(error)}` : null}
          getRowId={(m) => m.id}
          searchPlaceholder="Produit, référence, note…"
          globalColumns={['produit_nom', 'reference', 'note']}
          emptyTitle="Aucun mouvement"
          emptyDescription={
            activeTab !== 'tous'
              ? 'Aucun mouvement dans cet onglet.'
              : 'Aucun mouvement de stock enregistré.'
          }
          aria-label="Mouvements de stock"
        />
      )}

      {showForm && (
        <MouvementForm
          produits={produits}
          initialProduit={produitParam ?? ''}
          onClose={() => setShowForm(false)}
          onSaved={() => { dispatch(fetchMouvements()); setShowForm(false) }}
        />
      )}
    </div>
  )
}

// ── Formulaire mouvement ────────────────────────────────────────────────────────

function MouvementForm({ produits, initialProduit = '', onClose, onSaved }) {
  const dispatch = useDispatch()
  const [saving, setSaving] = useState(false)
  const [errors, setErrors] = useState({})

  const [fields, setFields] = useState({
    // Pré-sélection du produit quand le formulaire est ouvert depuis sa fiche.
    produit:        initialProduit ? String(initialProduit) : '',
    type_mouvement: 'entree',
    quantite:       '1',
    reference:      '',
    note:           '',
  })

  const setField = (k, v) => setFields(f => ({ ...f, [k]: v }))

  const selectedProduit = produits.find(p => String(p.id) === String(fields.produit))

  const previewApres = useMemo(() => {
    if (!selectedProduit) return null
    const qte = parseInt(fields.quantite) || 0
    if (fields.type_mouvement === 'entree')     return selectedProduit.quantite_stock + qte
    if (fields.type_mouvement === 'sortie')     return selectedProduit.quantite_stock - qte
    if (fields.type_mouvement === 'ajustement') return qte
    return null
  }, [selectedProduit, fields.quantite, fields.type_mouvement])

  const validate = () => {
    const e = {}
    if (!fields.produit)                          e.produit  = 'Produit requis'
    // Pour un ajustement, la quantité saisie EST le nouveau stock : 0 doit être
    // accepté (remettre un produit à zéro). Entrée/Sortie restent strictement > 0.
    const qte = parseInt(fields.quantite)
    if (fields.type_mouvement === 'ajustement') {
      if (!(Number.isInteger(qte) && qte >= 0))   e.quantite = 'Quantité invalide (≥ 0)'
    } else if (!(qte > 0)) {
      e.quantite = 'Quantité invalide (> 0)'
    }
    if (fields.type_mouvement === 'sortie' && selectedProduit) {
      if (parseInt(fields.quantite) > selectedProduit.quantite_stock)
        e.quantite = `Stock insuffisant (disponible : ${selectedProduit.quantite_stock})`
    }
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      await dispatch(createMouvement({
        produit:        parseInt(fields.produit),
        type_mouvement: fields.type_mouvement,
        quantite:       parseInt(fields.quantite),
        reference:      fields.reference.trim() || null,
        note:           fields.note.trim()      || null,
      })).unwrap()
      onSaved()
    } catch (err) {
      const msg = err?.detail ?? err?.non_field_errors?.[0] ?? JSON.stringify(err)
      setErrors(prev => ({ ...prev, submit: msg }))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Saisir un mouvement de stock</DialogTitle>
          <DialogDescription>
            Entrée, sortie ou ajustement — la quantité résultante est prévisualisée.
          </DialogDescription>
        </DialogHeader>

        <Form onSubmit={handleSubmit} className="gap-4">
          <FormField label="Produit" required htmlFor="mv-produit" error={errors.produit} fullWidth>
            <Select value={fields.produit} onValueChange={(v) => setField('produit', v)}>
              <SelectTrigger id="mv-produit" invalid={!!errors.produit}>
                <SelectValue placeholder="— Sélectionner un produit —" />
              </SelectTrigger>
              <SelectContent>
                {produits.map(p => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.nom}{p.sku ? ` (${p.sku})` : ''} — stock : {p.quantite_stock}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>

          <FormField label="Type de mouvement" htmlFor="mv-type">
            <Select value={fields.type_mouvement} onValueChange={(v) => setField('type_mouvement', v)}>
              <SelectTrigger id="mv-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="entree">Entrée (ajoute au stock)</SelectItem>
                <SelectItem value="sortie">Sortie (retire du stock)</SelectItem>
                <SelectItem value="ajustement">Ajustement (fixe le stock)</SelectItem>
              </SelectContent>
            </Select>
          </FormField>

          <FormField
            label={fields.type_mouvement === 'ajustement' ? 'Nouvelle quantité' : 'Quantité'}
            required htmlFor="mv-quantite" error={errors.quantite}
          >
            <Input
              id="mv-quantite" type="number" min="0" step="1" inputMode="numeric"
              invalid={!!errors.quantite}
              value={fields.quantite}
              onChange={e => setField('quantite', e.target.value)}
            />
          </FormField>

          {selectedProduit && previewApres !== null && (
            <div className="sm:col-span-2 flex flex-col gap-1">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
                <span>Stock actuel : <strong>{selectedProduit.quantite_stock}</strong></span>
                <ArrowDownUp className="size-3.5 rotate-90 text-muted-foreground" aria-hidden="true" />
                <span>
                  Après :{' '}
                  <strong className={previewApres < 0 ? 'text-destructive' : ''}>{previewApres}</strong>
                </span>
              </div>
              {previewApres < 0 && (
                <p className="text-xs text-warning">
                  Attention : cette saisie mène à un stock négatif ({previewApres}).
                </p>
              )}
            </div>
          )}

          <FormField label="Référence" htmlFor="mv-reference" fullWidth>
            <Input
              id="mv-reference"
              value={fields.reference}
              onChange={e => setField('reference', e.target.value)}
              placeholder="Numéro BL, facture fournisseur…"
            />
          </FormField>

          <FormField label="Note" htmlFor="mv-note" fullWidth>
            <Textarea
              id="mv-note" rows={2}
              value={fields.note}
              onChange={e => setField('note', e.target.value)}
              placeholder="Raison du mouvement…"
            />
          </FormField>

          {errors.submit && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </div>
          )}

          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer le mouvement'}
            </Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
