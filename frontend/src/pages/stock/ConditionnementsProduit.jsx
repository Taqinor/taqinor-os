import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Pencil, Trash2 } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Button, IconButton, DataTable, Spinner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

/* WIR109 — XSTK15 : conditionnements d'ACHAT d'un produit (« Touret 100 m »,
   « Carton 50 ») avec leur facteur de conversion vers l'unité de stock. Le
   stock reste stocké dans UNE SEULE unité (jamais de double comptage) :
   recevoir « 2 tourets de 100 m » incrémente 200 m via `facteur`. CRUD
   complet côté serveur, jusqu'ici sans écran. */

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

function ConditionnementForm({ produits, conditionnement, onClose, onSaved }) {
  const isNew = !conditionnement?.id
  const [fields, setFields] = useState({
    produit: conditionnement?.produit != null ? String(conditionnement.produit) : '',
    nom: conditionnement?.nom ?? '',
    facteur: conditionnement?.facteur != null ? String(conditionnement.facteur) : '',
    code_barres: conditionnement?.code_barres ?? '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.produit) { setError('Un produit est requis.'); return }
    if (!fields.nom.trim()) { setError('Le nom est requis.'); return }
    const facteur = Number(fields.facteur)
    if (!facteur || facteur <= 0) { setError('Le facteur doit être positif.'); return }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        produit: Number(fields.produit),
        nom: fields.nom.trim(),
        facteur,
        code_barres: fields.code_barres.trim() || null,
      }
      if (isNew) await stockApi.createConditionnementProduit(payload)
      else await stockApi.updateConditionnementProduit(conditionnement.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau conditionnement' : `Conditionnement — ${conditionnement.nom}`}</DialogTitle>
          <DialogDescription>
            Conditionnement d&apos;achat (touret, carton…), converti vers l&apos;unité de stock du produit.
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Produit" required htmlFor="cond-produit" fullWidth>
            <Select value={fields.produit} onValueChange={(v) => setField('produit', v)}>
              <SelectTrigger id="cond-produit"><SelectValue placeholder="Choisir un produit…" /></SelectTrigger>
              <SelectContent>
                {produits.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Nom" required htmlFor="cond-nom" fullWidth>
            <Input id="cond-nom" placeholder="Ex. Touret 100 m" value={fields.nom}
                   onChange={(e) => setField('nom', e.target.value)} />
          </FormField>
          <FormField label="Facteur (→ unité de stock)" required htmlFor="cond-facteur">
            <Input id="cond-facteur" type="number" step="any" value={fields.facteur}
                   onChange={(e) => setField('facteur', e.target.value)} />
          </FormField>
          <FormField label="Code-barres" htmlFor="cond-code">
            <Input id="cond-code" value={fields.code_barres}
                   onChange={(e) => setField('code_barres', e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function ConditionnementsProduit() {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [produits, setProduits] = useState([])
  const [selected, setSelected] = useState(null)

  const reload = () => {
    stockApi.getConditionnementsProduit({ ordering: 'produit__nom' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des conditionnements impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    reload()
    stockApi.getProduits({ ordering: 'nom' })
      .then((r) => setProduits(r.data?.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const supprimer = async (c) => {
    if (!window.confirm(`Supprimer le conditionnement « ${c.nom} » ?`)) return
    try {
      await stockApi.deleteConditionnementProduit(c.id)
      reload()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible.'))
    }
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Conditionnement', minWidth: 160, accessor: (c) => c.nom ?? '' },
    { id: 'produit_nom', header: 'Produit', minWidth: 160, accessor: (c) => c.produit_nom ?? '' },
    { id: 'facteur', header: 'Facteur', align: 'right', width: 100, searchable: false,
      accessor: (c) => c.facteur ?? 0,
      cell: (v, c) => `${v} ${c.unite_stock ?? ''}`.trim() },
    { id: 'code_barres', header: 'Code-barres', minWidth: 120,
      accessor: (c) => c.code_barres ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'actions', header: '', width: 90, searchable: false, sortable: false,
      cell: (_v, c) => (
        canWrite ? (
          <div className="flex items-center justify-end gap-1">
            <IconButton size="sm" variant="ghost" label="Modifier" onClick={() => setSelected(c)}>
              <Pencil className="size-4" aria-hidden="true" />
            </IconButton>
            <IconButton size="sm" variant="ghost" label="Supprimer"
                        className="text-destructive hover:text-destructive"
                        onClick={() => supprimer(c)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
        ) : null
      ) },
  // canWrite stable au sein d'une session ; reload via closure stable.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [canWrite])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Conditionnements produit</h1>
          <p className="text-sm text-muted-foreground">
            Conditionnements d&apos;achat (touret, carton…) — le stock reste dans une seule unité.
          </p>
        </div>
        {canWrite && (
          <Button onClick={() => setSelected({})}>
            <Plus className="size-4" /> Nouveau conditionnement
          </Button>
        )}
      </header>

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <DataTable
        data={items}
        columns={columns}
        loading={loading}
        getRowId={(c) => c.id}
        searchPlaceholder="Rechercher (conditionnement, produit)…"
        globalColumns={['nom', 'produit_nom']}
        emptyTitle="Aucun conditionnement"
        emptyDescription="Créez-en un avec « Nouveau conditionnement »."
        emptyAction={canWrite
          ? <Button size="sm" onClick={() => setSelected({})}><Plus className="size-4" /> Nouveau conditionnement</Button>
          : undefined}
        aria-label="Conditionnements produit"
      />

      {selected && (
        <ConditionnementForm produits={produits} conditionnement={selected.id ? selected : null}
                             onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
