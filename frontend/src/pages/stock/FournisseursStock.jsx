import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { useHasPermission, useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Pencil, Trash2, Package, ShoppingCart, BarChart3, Upload, LayoutGrid, Tags, Archive, Truck,
  RotateCcw, UserCheck, Check, X,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import ExcelImport from '../../components/ExcelImport'
import { toastError, toastSuccess, toastWithUndo } from '../../lib/toast'
import {
  Button, IconButton, DataTable, Spinner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Form, FormField,
  Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Badge, EmptyState,
  AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription,
  AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

// XPUR4 — les 4 statuts fournisseur (miroir de `Fournisseur.Statut` côté
// serveur — le blocage est déjà appliqué et testé serveur, cf.
// apps/stock/services.py:check_fournisseur_statut_commande/paiement). Ce
// module n'ajoute qu'un sélecteur + motif : jamais de logique de blocage
// dupliquée côté client.
// source-choix: stock.Fournisseur.statut
const STATUT_OPTIONS = [
  { value: 'actif', label: 'Actif' },
  { value: 'bloque_commandes', label: 'Bloqué (commandes)' },
  { value: 'bloque_paiements', label: 'Bloqué (paiements)' },
  { value: 'bloque_total', label: 'Bloqué (total)' },
]
const STATUT_LABELS = Object.fromEntries(STATUT_OPTIONS.map((o) => [o.value, o.label]))
const STATUT_TONE = {
  actif: 'success',
  bloque_commandes: 'warning',
  bloque_paiements: 'warning',
  bloque_total: 'danger',
}

// WIR219/NTPRT25 — validation d'une candidature d'auto-inscription au portail
// fournisseur (axe INDÉPENDANT de STATUT_OPTIONS ci-dessus : `statut_validation`
// n'entre jamais dans le blocage commercial). `valide` (défaut historique)
// n'affiche aucun badge — seule une candidature en attente/rejetée se signale.
const STATUT_VALIDATION_LABELS = {
  en_attente_validation: 'En attente de validation',
  rejete: 'Candidature rejetée',
}
const STATUT_VALIDATION_TONE = {
  en_attente_validation: 'warning',
  rejete: 'danger',
}

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

// ── WIR108 — gestion des catégories fournisseur (XPUR5, référentiel léger) ──
function CategorieFournisseurManager({ categories, onClose, onChanged, isAdmin }) {
  const [nom, setNom] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const creer = async (ev) => {
    ev.preventDefault()
    if (!nom.trim()) return
    setSaving(true)
    setError(null)
    try {
      await stockApi.createCategorieFournisseur({ nom: nom.trim() })
      setNom('')
      onChanged()
    } catch (err) {
      setError(frErr(err, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  const toggleArchive = async (cat) => {
    try {
      await stockApi.updateCategorieFournisseur(cat.id, { archived: !cat.archived })
      onChanged()
    } catch (err) {
      setError(frErr(err, 'Modification impossible.'))
    }
  }

  const supprimer = async (cat) => {
    if (!window.confirm(`Supprimer la catégorie « ${cat.nom} » ?`)) return
    try {
      await stockApi.deleteCategorieFournisseur(cat.id)
      onChanged()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible (catégorie utilisée).'))
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Catégories fournisseur</DialogTitle>
          <DialogDescription>
            Référentiel léger (XPUR5), filtrable sur la liste des fournisseurs.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={creer} className="flex items-end gap-2">
          <div className="flex-1">
            <Input value={nom} onChange={(e) => setNom(e.target.value)}
                   placeholder="Nouvelle catégorie…" />
          </div>
          <Button type="submit" loading={saving} disabled={!nom.trim()}>
            <Plus className="size-4" /> Ajouter
          </Button>
        </form>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune catégorie.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {categories.map((c) => (
              <li key={c.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
                <span className={c.archived ? 'text-muted-foreground line-through' : ''}>{c.nom}</span>
                <span className="flex items-center gap-1">
                  <IconButton size="sm" variant="ghost"
                              label={c.archived ? 'Réactiver' : 'Archiver'}
                              onClick={() => toggleArchive(c)}>
                    <Archive className="size-4" aria-hidden="true" />
                  </IconButton>
                  {isAdmin && (
                    <IconButton size="sm" variant="ghost" label="Supprimer"
                                className="text-destructive hover:text-destructive"
                                onClick={() => supprimer(c)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Modal de création / édition d'un fournisseur ────────────────────────────
function FournisseurForm({ fournisseur, categories, onClose, onSaved }) {
  const isNew = !fournisseur?.id
  const [fields, setFields] = useState({
    nom: fournisseur?.nom ?? '',
    contact_personne: fournisseur?.contact_personne ?? '',
    email: fournisseur?.email ?? '',
    telephone: fournisseur?.telephone ?? '',
    adresse: fournisseur?.adresse ?? '',
    // XPUR4 — statut de blocage (actif par défaut, comportement historique).
    statut: fournisseur?.statut ?? 'actif',
    motif_blocage: fournisseur?.motif_blocage ?? '',
    // XPUR5 — catégorie (référentiel léger, optionnelle).
    categorie: fournisseur?.categorie != null ? String(fournisseur.categorie) : '',
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
        statut: fields.statut,
        motif_blocage: fields.motif_blocage.trim() || null,
        // XPUR5 — catégorie référentielle (optionnelle).
        categorie: fields.categorie ? Number(fields.categorie) : null,
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
          {/* XPUR5/WIR108 — catégorie (référentiel léger, « Gérer les
              catégories » sur la liste pour créer/archiver). */}
          <FormField label="Catégorie" htmlFor="fou-categorie">
            <Select value={fields.categorie || '__none__'}
                    onValueChange={(v) => setField('categorie', v === '__none__' ? '' : v)}>
              <SelectTrigger id="fou-categorie"><SelectValue placeholder="Aucune" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Aucune</SelectItem>
                {(categories ?? []).filter((c) => !c.archived).map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Adresse" htmlFor="fou-adr" fullWidth>
            <Textarea id="fou-adr" rows={2} value={fields.adresse}
                      onChange={(e) => setField('adresse', e.target.value)} />
          </FormField>
          {/* XPUR4 — statut de blocage : appliqué et testé côté serveur
              (check_fournisseur_statut_commande/paiement) — ce sélecteur ne
              fait que le piloter, aucune logique dupliquée ici. */}
          <FormField label="Statut" htmlFor="fou-statut">
            <Select value={fields.statut} onValueChange={(v) => setField('statut', v)}>
              <SelectTrigger id="fou-statut"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUT_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Motif de blocage" htmlFor="fou-motif-blocage" fullWidth>
            <Textarea id="fou-motif-blocage" rows={2} value={fields.motif_blocage}
                      placeholder="Visible sur le message de refus BCF/paiement (optionnel)"
                      onChange={(e) => setField('motif_blocage', e.target.value)} />
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

// ── WR4 / FG59 — Scorecard performance fournisseur (admin, INTERNE) ──────────
// Délai moyen de livraison, taux de remplissage, taux de retour, dépenses
// totales (prix d'achat) — jamais client-facing.
const fmtMad = (v) => formatMAD(v)

function ScorecardModal({ fournisseur, onClose }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.performanceFournisseur(fournisseur.id)
      .then((r) => { if (active) setData(r.data) })
      .catch((e) => {
        if (active) {
          setError(e?.response?.status === 403
            ? 'Réservé à l\'administrateur.'
            : (e?.response?.data?.detail ?? 'Chargement de la performance impossible.'))
        }
      })
    return () => { active = false }
  }, [fournisseur.id])

  const pct = (v) => (v == null ? '—' : `${v} %`)
  const jours = (v) => (v == null ? '—' : `${v} j`)

  const cartes = data ? [
    { label: 'Bons de commande', value: String(data.nb_bons ?? 0) },
    { label: 'Délai moyen de livraison', value: jours(data.avg_lead_time_days) },
    { label: 'Taux de remplissage', value: pct(data.fill_rate_pct) },
    { label: 'Retours', value: String(data.nb_retours ?? 0) },
    { label: 'Taux de retour', value: pct(data.return_rate_pct) },
    { label: 'Dépenses totales (interne)', value: fmtMad(data.total_achats_ht) },
  ] : []

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BarChart3 className="size-5 text-muted-foreground" aria-hidden="true" />
            Performance — {fournisseur.nom}
          </DialogTitle>
          <DialogDescription>
            Indicateurs d&apos;achat (délai, remplissage, retours, dépenses).
            Donnée interne — jamais sur un document client.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {!data && !error && (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner /> Chargement…
          </div>
        )}
        {data && (
          <div className="grid gap-3 sm:grid-cols-3">
            {cartes.map((c) => (
              <div key={c.label} className="rounded-lg border border-border bg-muted/30 p-3">
                <p className="text-xs text-muted-foreground">{c.label}</p>
                <p className="mt-1 text-lg font-semibold tabular-nums">{c.value}</p>
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── WIR190 — confirmation de suppression définitive (patron StockList) ──────
function ForceDeleteFournisseurModal({ fournisseur, onCancel, onConfirm, loading }) {
  const [typed, setTyped] = useState('')
  const expected = fournisseur.nom
  const isValid = typed.trim() === expected.trim()

  return (
    <AlertDialog open onOpenChange={(o) => { if (!o) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">Suppression définitive</AlertDialogTitle>
          <AlertDialogDescription>
            Cette action supprimera le fournisseur et son historique. Elle est{' '}
            <strong>irréversible</strong>.
          </AlertDialogDescription>
        </AlertDialogHeader>

        <div className="rounded-lg border border-border bg-muted/40 px-4 py-3 text-sm leading-relaxed">
          <div><span className="inline-block min-w-32 text-muted-foreground">Fournisseur</span><strong>{fournisseur.nom}</strong></div>
          <div><span className="inline-block min-w-32 text-muted-foreground">Produits liés</span>{fournisseur.nb_produits ?? 0}</div>
          <div><span className="inline-block min-w-32 text-muted-foreground">Bons de commande</span>{fournisseur.nb_bons_commande ?? 0}</div>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="fdf-confirm">
            Tapez <code className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">{expected}</code> pour confirmer
          </label>
          <Input id="fdf-confirm" value={typed} onChange={(e) => setTyped(e.target.value)}
                 placeholder={`Saisir : ${expected}`} autoFocus />
        </div>

        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Annuler</AlertDialogCancel>
          <AlertDialogAction
            disabled={!isValid || loading}
            onClick={(e) => { e.preventDefault(); onConfirm(fournisseur) }}
          >
            {loading ? 'Suppression…' : 'Supprimer définitivement'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export default function FournisseursStock() {
  // ARC47 — gating via le hook partagé. `hasFinePermissions` (présence de
  // codes ERP, PAS un droit) choisit la branche ; hooks appelés
  // inconditionnellement. Sémantique identique à l'origine.
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole
  const canDelete = useIsAdmin()

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null) // objet fournisseur ou {} (nouveau)
  const [scorecard, setScorecard] = useState(null) // WR4 — perf fournisseur (admin)
  const [showImport, setShowImport] = useState(false) // VX109 — import Excel/CSV
  const [categories, setCategories] = useState([]) // XPUR5/WIR108 — référentiel catégories
  const [showCategories, setShowCategories] = useState(false)
  const isAdmin = canDelete

  // WIR190 — fournisseurs archivés (repli PROTECT, même patron que StockList).
  const [showArchived, setShowArchived] = useState(false)
  const [itemsArchived, setItemsArchived] = useState([])
  const [loadingArchived, setLoadingArchived] = useState(false)
  const [confirmForceDelete, setConfirmForceDelete] = useState(null)
  const [forceDeleting, setForceDeleting] = useState(false)

  // WIR219/NTPRT25 — candidatures d'auto-inscription au portail fournisseur,
  // reçues (`statut_validation`) mais jusqu'ici jamais validables/rejetables.
  const [filterEnAttente, setFilterEnAttente] = useState(false)
  const [decidingId, setDecidingId] = useState(null)

  // setState n'arrive que dans les callbacks asynchrones (jamais synchrone dans
  // l'effet) : l'état initial loading=true couvre le premier chargement.
  const reload = () => {
    stockApi.getFournisseurs({ ordering: 'nom' })
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des fournisseurs impossible.'))
      .finally(() => setLoading(false))
  }
  // WIR108 — appel défensif : certains consommateurs pré-existants de cet
  // écran (ex. wr4Procurement.test.jsx) mockent `stockApi` sans ce nouvel
  // endpoint. Dégrade proprement (catégories vides) plutôt que de planter
  // tout l'écran sur `undefined(...) is not a function`.
  const reloadCategories = () => {
    stockApi.getCategoriesFournisseur?.({ ordering: 'nom' })
      ?.then((r) => setCategories(r.data?.results ?? r.data ?? []))
      ?.catch(() => {})
  }
  const reloadArchived = () => {
    setLoadingArchived(true)
    stockApi.getFournisseursArchived()
      .then((r) => setItemsArchived(r.data?.results ?? r.data ?? []))
      .catch(() => toastError('Chargement des fournisseurs archivés impossible.'))
      .finally(() => setLoadingArchived(false))
  }

  useEffect(() => { reload(); reloadCategories() }, [])
  useEffect(() => { if (showArchived) reloadArchived() }, [showArchived])

  // WIR190 — la suppression peut se replier en ARCHIVAGE (409 protégé côté
  // serveur : le fournisseur porte des prix d'achat négociés/BCF/factures
  // réels). Le serveur répond 200 `{archived: true, detail}` dans ce cas —
  // jamais une erreur — donc on l'explique honnêtement plutôt que de
  // recharger la liste en silence.
  const delFournisseur = async (f) => {
    if (!window.confirm(`Supprimer le fournisseur « ${f.nom} » ?`)) return
    setError(null)
    try {
      const r = await stockApi.deleteFournisseur(f.id)
      reload()
      if (r?.data?.archived) {
        toastWithUndo({
          message: r.data.detail || 'Fournisseur archivé.',
          onUndo: async () => {
            try { await stockApi.unarchiveFournisseur(f.id); reload() }
            catch { toastError('Désarchivage impossible.') }
          },
        })
        if (showArchived) reloadArchived()
      } else {
        toastSuccess('Fournisseur supprimé.')
      }
    } catch (err) {
      setError(frErr(err, 'Suppression impossible (fournisseur utilisé).'))
    }
  }

  const handleUnarchive = async (f) => {
    if (!window.confirm(`Désarchiver le fournisseur « ${f.nom} » ?`)) return
    try {
      await stockApi.unarchiveFournisseur(f.id)
      reloadArchived(); reload()
      toastSuccess('Fournisseur désarchivé.')
    } catch (err) {
      toastError(frErr(err, 'Désarchivage impossible.'))
    }
  }

  const handleForceDelete = async (f) => {
    setForceDeleting(true)
    try {
      await stockApi.forceDeleteFournisseur(f.id)
      setConfirmForceDelete(null)
      reloadArchived()
    } catch (err) {
      toastError(frErr(err, 'Suppression définitive impossible (données rattachées).'))
    } finally {
      setForceDeleting(false)
    }
  }

  // WIR219/NTPRT25 — valide/rejette une candidature d'auto-inscription.
  // Réservé Admin côté serveur (403 FR affiché tel quel si un rôle moindre
  // parvenait quand même jusqu'ici) ; idempotent (une candidature déjà
  // tranchée ne rejoue rien côté serveur).
  const deciderCandidature = async (f, valider) => {
    if (!window.confirm(valider
      ? `Valider la candidature de « ${f.nom} » ? Le fournisseur intègre le sourcing.`
      : `Rejeter la candidature de « ${f.nom} » ?`)) return
    setDecidingId(f.id)
    try {
      await stockApi.deciderCandidatureFournisseur(f.id, valider)
      reload()
      toastSuccess(valider ? 'Candidature validée.' : 'Candidature rejetée.')
    } catch (err) {
      toastError(frErr(err, valider ? 'Validation impossible.' : 'Rejet impossible.'))
    } finally {
      setDecidingId(null)
    }
  }

  // Compteur pour le filtre rapide (sur le catalogue COMPLET, pas seulement
  // la page filtrée) — visible même quand le filtre est désactivé.
  const enAttenteCount = useMemo(
    () => items.filter((f) => f.statut_validation === 'en_attente_validation').length,
    [items],
  )

  const archivedColumns = useMemo(() => [
    { id: 'nom', header: 'Nom', minWidth: 160,
      cell: (v) => <span className="line-through">{v}</span> },
    { id: 'categorie_nom', header: 'Catégorie', minWidth: 120,
      accessor: (f) => f.categorie_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
    { id: 'nb_produits', header: 'Produits', align: 'right', width: 90, searchable: false,
      accessor: (f) => f.nb_produits ?? 0 },
    { id: 'nb_bons_commande', header: 'BCF', align: 'right', width: 80, searchable: false,
      accessor: (f) => f.nb_bons_commande ?? 0 },
  ], [])

  const archivedRowActions = (f) => [
    { id: 'unarchive', label: 'Réactiver', icon: RotateCcw, onClick: () => handleUnarchive(f) },
    { id: 'delete', label: 'Supprimer définitivement', icon: Trash2, destructive: true,
      onClick: () => setConfirmForceDelete(f) },
  ]

  const columns = useMemo(() => [
    { id: 'nom', header: 'Nom', minWidth: 160, accessor: (f) => f.nom ?? '' },
    // XPUR4 — statut de blocage, visible en un coup d'œil sur la liste.
    { id: 'statut', header: 'Statut', width: 150, searchable: false,
      accessor: (f) => STATUT_LABELS[f.statut] ?? f.statut ?? 'Actif',
      cell: (_v, f) => (
        <Badge tone={STATUT_TONE[f.statut] ?? 'success'}>
          {STATUT_LABELS[f.statut] ?? 'Actif'}
        </Badge>
      ) },
    // WIR219/NTPRT25 — candidature d'auto-inscription (axe indépendant du
    // blocage commercial ci-dessus). `valide` (défaut historique) : aucun badge.
    { id: 'statut_validation', header: 'Candidature', width: 170, searchable: false,
      accessor: (f) => STATUT_VALIDATION_LABELS[f.statut_validation] ?? '',
      cell: (_v, f) => (
        STATUT_VALIDATION_LABELS[f.statut_validation]
          ? <Badge tone={STATUT_VALIDATION_TONE[f.statut_validation]}>
              {STATUT_VALIDATION_LABELS[f.statut_validation]}
            </Badge>
          : null
      ) },
    // XPUR5/WIR108 — catégorie assignée (référentiel « Catégories »).
    { id: 'categorie_nom', header: 'Catégorie', minWidth: 120,
      accessor: (f) => f.categorie_nom ?? '',
      cell: (v) => v || <span className="text-muted-foreground">—</span> },
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
    { id: 'actions', header: '', width: 180, searchable: false, sortable: false,
      cell: (_v, f) => (
        <div className="flex items-center justify-end gap-1">
          {/* XPUR25/WIR27 — fiche 360 (BCF/factures/retours/conformité/
              accords de prix) — jusqu'ici construite mais routée nulle part. */}
          <IconButton asChild size="md" variant="ghost" label="Fiche 360"
                      onClick={(e) => e.stopPropagation()}>
            <Link to={`/stock/fournisseurs/${f.id}/360`}>
              <LayoutGrid className="size-4" aria-hidden="true" />
            </Link>
          </IconButton>
          {isAdmin && (
            <IconButton size="md" variant="ghost" label="Voir la performance"
                        onClick={(e) => { e.stopPropagation(); setScorecard(f) }}>
              <BarChart3 className="size-4" aria-hidden="true" />
            </IconButton>
          )}
          {/* WIR219/NTPRT25 — décision réservée Admin (garde serveur
              IsAdminRole ; 403 FR affiché tel quel côté handler si un rôle
              moindre parvenait quand même jusqu'ici). */}
          {isAdmin && f.statut_validation === 'en_attente_validation' && (
            <>
              <IconButton size="md" variant="ghost" label="Valider la candidature"
                          disabled={decidingId === f.id}
                          onClick={(e) => { e.stopPropagation(); deciderCandidature(f, true) }}>
                <Check className="size-4 text-success" aria-hidden="true" />
              </IconButton>
              <IconButton size="md" variant="ghost" label="Rejeter la candidature"
                          disabled={decidingId === f.id}
                          onClick={(e) => { e.stopPropagation(); deciderCandidature(f, false) }}>
                <X className="size-4 text-destructive" aria-hidden="true" />
              </IconButton>
            </>
          )}
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
  // canDelete/isAdmin stables au sein d'une session ; reload via closure stable.
  // `decidingId` (WIR219) DOIT rester en dépendance : sinon le bouton
  // Valider/Rejeter garderait un `disabled` figé sur sa valeur au premier rendu.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [canDelete, decidingId])

  const rows = useMemo(
    () => (filterEnAttente ? items.filter((f) => f.statut_validation === 'en_attente_validation') : items),
    [items, filterEnAttente],
  )

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Truck}
        title="Fournisseurs"
        subtitle={`${items.length} fournisseur(s)`}
        actions={(
          <>
            {/* WIR190 — même patron que StockList : les archivés restent
                consultables/réactivables, réservé admin (destruction définitive). */}
            {isAdmin && (
              <Button variant={showArchived ? 'secondary' : 'outline'}
                      onClick={() => setShowArchived((v) => !v)}>
                <Archive /> {showArchived ? 'Masquer archivés' : `Archivés${itemsArchived.length > 0 ? ` (${itemsArchived.length})` : ''}`}
              </Button>
            )}
            {/* WIR219/NTPRT25 — candidatures d'auto-inscription en attente. */}
            {enAttenteCount > 0 && (
              <Button variant={filterEnAttente ? 'secondary' : 'outline'}
                      onClick={() => setFilterEnAttente((v) => !v)}
                      title="N'afficher que les candidatures en attente de validation">
                <UserCheck /> Candidatures en attente ({enAttenteCount})
              </Button>
            )}
            {canWrite && (
              <>
                {/* XPUR5/WIR108 — CRUD du référentiel catégories fournisseur. */}
                <Button variant="outline" onClick={() => setShowCategories(true)}>
                  <Tags /> Catégories
                </Button>
                <Button variant="outline" onClick={() => setShowImport(true)}>
                  <Upload /> Importer
                </Button>
                <Button onClick={() => setSelected({})}>
                  <Plus /> Nouveau fournisseur
                </Button>
              </>
            )}
          </>
        )}
      />

      {showImport && (
        <ExcelImport target="fournisseurs" onClose={() => setShowImport(false)}
                     onDone={reload} />
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <DataTable
        data={rows}
        columns={columns}
        loading={loading}
        getRowId={(f) => f.id}
        searchPlaceholder="Rechercher (nom, contact, email)…"
        globalColumns={['nom', 'contact_personne', 'email']}
        onRowClick={(f) => setSelected(f)}
        emptyTitle="Aucun fournisseur"
        emptyDescription="Créez-en un avec « Nouveau fournisseur »."
        emptyAction={canWrite
          ? <Button size="sm" onClick={() => setSelected({})}><Plus className="size-4" /> Nouveau fournisseur</Button>
          : undefined}
        aria-label="Fournisseurs"
      />

      {/* WIR190 — fournisseurs archivés : le patron produit de StockList,
          consultable/réactivable, la suppression définitive reste admin. */}
      {showArchived && (
        <div className="mt-2 flex flex-col gap-2">
          <h3 className="flex items-center gap-2 font-display text-base font-semibold tracking-tight text-muted-foreground">
            Fournisseurs archivés
            {itemsArchived.length > 0 && <Badge tone="warning">{itemsArchived.length}</Badge>}
          </h3>
          {itemsArchived.length === 0 ? (
            <EmptyState icon={Archive} title="Aucun fournisseur archivé"
                        description="Les fournisseurs archivés (données réelles rattachées) apparaissent ici." />
          ) : (
            <div className="opacity-80">
              <DataTable
                data={itemsArchived}
                columns={archivedColumns}
                loading={loadingArchived}
                getRowId={(f) => f.id}
                rowActions={archivedRowActions}
                searchPlaceholder="Rechercher un fournisseur archivé…"
                globalColumns={['nom']}
                emptyTitle="Aucun fournisseur archivé"
                aria-label="Fournisseurs archivés"
              />
            </div>
          )}
        </div>
      )}

      {selected && (
        <FournisseurForm fournisseur={selected} categories={categories}
                         onClose={() => setSelected(null)} onSaved={reload} />
      )}
      {scorecard && (
        <ScorecardModal fournisseur={scorecard} onClose={() => setScorecard(null)} />
      )}
      {showCategories && (
        <CategorieFournisseurManager categories={categories} isAdmin={isAdmin}
                                     onClose={() => setShowCategories(false)}
                                     onChanged={reloadCategories} />
      )}
      {confirmForceDelete && (
        <ForceDeleteFournisseurModal
          fournisseur={confirmForceDelete}
          loading={forceDeleting}
          onCancel={() => setConfirmForceDelete(null)}
          onConfirm={handleForceDelete}
        />
      )}
    </div>
  )
}
