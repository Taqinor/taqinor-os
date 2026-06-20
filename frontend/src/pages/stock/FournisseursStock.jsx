import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Plus, Pencil, Trash2, Package, ShoppingCart } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Button, IconButton, DataTable,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField,
  Input, Textarea,
} from '../../ui'

// L697/L698/L699 — Écran de gestion des FOURNISSEURS : liste + édition des
// coordonnées (personne de contact, email, téléphone, adresse). L'email est
// validé (format) avant enregistrement, y compris à la création inline. La
// fiche affiche en lecture seule le nombre de produits liés et de bons de
// commande fournisseur associés.

// Validation simple du format email (avant appel réseau).
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
function emailValide(email) {
  return !email || EMAIL_RE.test(email.trim())
}

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

// ── Modal de création / édition d'un fournisseur ────────────────────────────
function FournisseurForm({ fournisseur, onClose, onSaved }) {
  const isNew = !fournisseur?.id
  const [fields, setFields] = useState({
    nom: fournisseur?.nom ?? '',
    contact_personne: fournisseur?.contact_personne ?? '',
    email: fournisseur?.email ?? '',
    telephone: fournisseur?.telephone ?? '',
    adresse: fournisseur?.adresse ?? '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const validate = () => {
    const e = {}
    if (!fields.nom.trim()) e.nom = 'Le nom est requis.'
    // L698 — format email validé AVANT enregistrement.
    if (!emailValide(fields.email)) e.email = 'Adresse email invalide.'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const submit = async (ev) => {
    ev.preventDefault()
    if (!validate()) return
    setSaving(true)
    try {
      const payload = {
        nom: fields.nom.trim(),
        contact_personne: fields.contact_personne.trim() || null,
        email: fields.email.trim() || null,
        telephone: fields.telephone.trim() || null,
        adresse: fields.adresse.trim() || null,
      }
      if (isNew) await stockApi.createFournisseur(payload)
      else await stockApi.updateFournisseur(fournisseur.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setErrors((prev) => ({ ...prev, submit: frErr(err, "L'enregistrement a échoué.") }))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau fournisseur' : `Fournisseur — ${fournisseur.nom}`}</DialogTitle>
          <DialogDescription>
            Coordonnées du fournisseur (achat). Donnée interne.
          </DialogDescription>
        </DialogHeader>

        {/* L699 — compteurs lecture seule sur une fiche existante. */}
        {!isNew && (
          <div className="flex flex-wrap gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-1">
              <Package className="size-3.5 text-muted-foreground" />
              {fournisseur.nb_produits ?? 0} produit(s)
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 px-2.5 py-1">
              <ShoppingCart className="size-3.5 text-muted-foreground" />
              {fournisseur.nb_bons_commande ?? 0} bon(s) de commande
            </span>
          </div>
        )}

        <Form onSubmit={submit} className="gap-4">
          <FormField label="Nom" required htmlFor="fou-nom" error={errors.nom} fullWidth>
            <Input id="fou-nom" value={fields.nom} invalid={!!errors.nom}
                   onChange={(e) => setField('nom', e.target.value)} />
          </FormField>
          <FormField label="Personne de contact" htmlFor="fou-contact">
            <Input id="fou-contact" value={fields.contact_personne}
                   onChange={(e) => setField('contact_personne', e.target.value)} />
          </FormField>
          <FormField label="Email" htmlFor="fou-email" error={errors.email}>
            <Input id="fou-email" type="email" value={fields.email} invalid={!!errors.email}
                   onChange={(e) => setField('email', e.target.value)} />
          </FormField>
          <FormField label="Téléphone" htmlFor="fou-tel">
            <Input id="fou-tel" value={fields.telephone}
                   onChange={(e) => setField('telephone', e.target.value)} />
          </FormField>
          <FormField label="Adresse" htmlFor="fou-adr" fullWidth>
            <Textarea id="fou-adr" rows={2} value={fields.adresse}
                      onChange={(e) => setField('adresse', e.target.value)} />
          </FormField>

          {errors.submit && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {errors.submit}
            </div>
          )}

          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default function FournisseursStock() {
  const role = useSelector((s) => s.auth.role)
  const permissions = useSelector((s) => s.auth.permissions) || []
  const canWrite = permissions.length
    ? permissions.includes('stock_modifier')
    : (role === 'responsable' || role === 'admin')
  const canDelete = role === 'admin'

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // objet fournisseur ou {} (nouveau)

  // setState n'arrive que dans les callbacks asynchrones (jamais synchrone dans
  // l'effet) : l'état initial loading=true couvre le premier chargement.
  const reload = () => {
    stockApi.getFournisseurs({ ordering: 'nom' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des fournisseurs impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { reload() }, [])

  const delFournisseur = async (f) => {
    if (!window.confirm(`Supprimer le fournisseur « ${f.nom} » ?`)) return
    setError(null)
    try {
      await stockApi.deleteFournisseur(f.id)
      reload()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible (fournisseur utilisé).'))
    }
  }

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', minWidth: 160, accessor: (f) => f.nom ?? '' },
    { id: 'contact_personne', header: 'Contact', minWidth: 140,
      accessor: (f) => f.contact_personne ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'email', header: 'Email', minWidth: 160,
      accessor: (f) => f.email ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'telephone', header: 'Téléphone', width: 130, searchable: false,
      accessor: (f) => f.telephone ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'nb_produits', header: 'Produits', align: 'right', width: 90, searchable: false,
      accessor: (f) => f.nb_produits ?? 0 },
    { id: 'nb_bons_commande', header: 'BCF', align: 'right', width: 80, searchable: false,
      accessor: (f) => f.nb_bons_commande ?? 0 },
    { id: 'actions', header: '', width: 100, searchable: false, sortable: false,
      cell: (_v, f) => (
        <div className="flex items-center justify-end gap-1">
          <IconButton size="md" variant="ghost" label="Modifier"
                      onClick={(e) => { e.stopPropagation(); setSelected(f) }}>
            <Pencil className="size-4" aria-hidden="true" />
          </IconButton>
          {canDelete && (
            <IconButton size="md" variant="ghost" label="Supprimer"
                        className="text-destructive hover:text-destructive"
                        onClick={(e) => { e.stopPropagation(); delFournisseur(f) }}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          )}
        </div>
      ) },
  // canDelete est stable au sein d'une session ; reload via closure stable.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [canDelete])

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Fournisseurs</h1>
          <p className="text-sm text-muted-foreground">{items.length} fournisseur(s)</p>
        </div>
        {canWrite && (
          <Button onClick={() => setSelected({})}>
            <Plus /> Nouveau fournisseur
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
        getRowId={(f) => f.id}
        searchPlaceholder="Rechercher (nom, contact, email)…"
        globalColumns={['nom', 'contact_personne', 'email']}
        onRowClick={(f) => setSelected(f)}
        emptyTitle="Aucun fournisseur"
        emptyDescription="Créez-en un avec « Nouveau fournisseur »."
        aria-label="Fournisseurs"
      />

      {selected && (
        <FournisseurForm fournisseur={selected}
                         onClose={() => setSelected(null)} onSaved={reload} />
      )}
    </div>
  )
}
