import { useEffect, useState, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useSearchParams } from 'react-router-dom'
import { Plus, ArrowDownUp, X } from 'lucide-react'
import stockApi from '../../api/stockApi'
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
  const role = useSelector(s => s.auth.role)
  const permissions = useSelector(s => s.auth.permissions)
  // Rôle fin : la permission stock_mouvement décide ; comptes hérités :
  // comportement historique par rôle.
  const canPostMouvement = permissions.length
    ? permissions.includes('stock_mouvement')
    : (role === 'responsable' || role === 'admin')

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
        {canPostMouvement && (
          <Button onClick={() => setShowForm(true)}>
            <Plus /> Saisir mouvement
          </Button>
        )}
      </header>

      <Segmented
        size="sm"
        value={activeTab}
        onChange={setActiveTab}
        options={tabOptions}
        className="flex-wrap"
      />

      {produitFiltre && (
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

      {isTransferts ? (
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
    if (!(parseInt(fields.quantite) > 0))         e.quantite = 'Quantité invalide (> 0)'
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
