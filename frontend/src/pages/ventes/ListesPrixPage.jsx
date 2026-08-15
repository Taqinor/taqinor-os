import { useEffect, useState } from 'react'
import { Tags, Plus, Pencil, Archive, ArchiveRestore, Trash2 } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Skeleton, EmptyState, Button, Input, Label,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { Table } from '../reporting/Table'
import { useConfirmDialog } from '../../ui/confirm'
import { frenchError } from '../../lib/frenchError'
// APX11 — en-tête unique VX28 + accent de module (identité Ventes).
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'

const dh = (v) => formatMAD(v, { decimals: 2 })

const TYPES_REGLE = [
  { value: 'prix_fixe', label: 'Prix fixe (MAD)' },
  { value: 'remise_pct', label: 'Remise (%)' },
  { value: 'formule_sur_prix_vente', label: 'Formule sur prix de vente (coefficient)' },
]

// XSAL1-2 — administration des listes de prix clients (détail / revendeur /
// export) : CRUD sur ventes.ListePrix + lignes (prix fixe par produit) +
// règles (paliers de quantité / remise / formule). Écriture réservée
// Responsable/Admin côté serveur (ListePrixViewSet) — cet écran ne fait
// qu'appeler l'API, le 403 serveur reste la seule garde qui compte.
export default function ListesPrixPage() {
  const [listes, setListes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [detail, setDetail] = useState(null) // liste ouverte (avec lignes/regles)
  const [produits, setProduits] = useState([])

  const fetchListes = () =>
    ventesApi.getListesPrix()
      .then(r => setListes(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les listes de prix.'))
      .finally(() => setLoading(false))

  // Rechargement explicite (après création/édition) : ré-affiche le squelette
  // pendant le refetch, contrairement au chargement initial (déjà `true`).
  const reload = () => { setLoading(true); fetchListes() }

  useEffect(() => {
    fetchListes()
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const openDetail = (liste) => setDetail(liste)
  const refreshDetail = (id) => {
    ventesApi.getListePrix(id).then(r => setDetail(r.data)).catch(() => {})
  }

  return (
    <div className="ui-root page">
      {/* APX11 — en-tête unique VX28 + accent Ventes. */}
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={Tags}
        title="Listes de prix"
        subtitle="Tarifs négociés par client"
        actions={(
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="size-4" /> Nouvelle liste
          </Button>
        )}
      />

      {error && (
        <div className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <Card><CardContent className="space-y-2 pt-5">
          {Array.from({ length: 4 }).map((unused, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </CardContent></Card>
      ) : (
        <Card>
          <CardContent className="p-0 sm:p-0">
            <Table
              aria-label="Listes de prix"
              getRowKey={(l) => l.id}
              columns={[
                { key: 'nom', header: 'Nom', cell: (l) => (
                  <button type="button" className="font-medium text-info hover:underline"
                          onClick={() => openDetail(l)}>{l.nom}</button>
                ) },
                { key: 'devise', header: 'Devise', cell: (l) => l.devise },
                { key: 'lignes', header: 'Prix fixés', align: 'right', cell: (l) => (l.lignes?.length ?? 0) },
                { key: 'regles', header: 'Règles/paliers', align: 'right', cell: (l) => (l.regles?.length ?? 0) },
                { key: 'archived', header: 'Statut', cell: (l) => (l.archived ? 'Archivée' : 'Active') },
              ]}
              rows={listes}
              empty={(
                <EmptyState
                  icon={Tags}
                  title="Aucune liste de prix"
                  description="Créez une liste (ex. « Revendeur », « Export ») pour proposer un tarif négocié à certains clients."
                  className="border-0 py-6"
                />
              )}
            />
          </CardContent>
        </Card>
      )}

      {createOpen && (
        <CreateListeDialog
          onClose={() => setCreateOpen(false)}
          onCreated={() => { setCreateOpen(false); reload() }}
        />
      )}

      {detail && (
        <ListeDetailDialog
          liste={detail}
          produits={produits}
          onClose={() => setDetail(null)}
          onChanged={() => { refreshDetail(detail.id); reload() }}
          // WIR226 — la liste supprimée n'existe plus : on ferme le détail.
          onDeleted={() => { setDetail(null); reload() }}
        />
      )}
    </div>
  )
}

/* WIR226 — champs partagés par la création ET l'édition d'une liste de prix
   (le formulaire de création n'en portait que deux, si bien qu'un segment ou
   une période de validité n'étaient réglables nulle part). */
function ListePrixFields({ prefix, valeurs, set, autoFocus = false }) {
  return (
    <>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-nom`} required>Nom</Label>
        <Input id={`${prefix}-nom`} value={valeurs.nom} autoFocus={autoFocus}
               onChange={(e) => set('nom', e.target.value)} placeholder="ex : Revendeur" />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-devise`}>Devise</Label>
        <Input id={`${prefix}-devise`} value={valeurs.devise}
               onChange={(e) => set('devise', e.target.value)} />
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${prefix}-segment`}>Segment client</Label>
        <Input id={`${prefix}-segment`} value={valeurs.segment_client}
               onChange={(e) => set('segment_client', e.target.value)}
               placeholder="ex : Revendeur, Grand compte" />
        <p className="text-[11px] text-muted-foreground">
          Laissé vide, la liste ne s'applique qu'aux clients qui la portent
          explicitement. Renseigné, elle s'applique à tout client de ce segment.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor={`${prefix}-debut`}>Début de validité</Label>
          <Input id={`${prefix}-debut`} type="date" value={valeurs.date_debut}
                 onChange={(e) => set('date_debut', e.target.value)} />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor={`${prefix}-fin`}>Fin de validité</Label>
          <Input id={`${prefix}-fin`} type="date" value={valeurs.date_fin}
                 onChange={(e) => set('date_fin', e.target.value)} />
        </div>
      </div>
    </>
  )
}

// Les dates vides doivent partir en `null` (le DateField DRF refuse '').
const payloadListe = (v) => ({
  nom: v.nom.trim(),
  devise: v.devise,
  segment_client: v.segment_client.trim(),
  date_debut: v.date_debut || null,
  date_fin: v.date_fin || null,
})

const videListe = { nom: '', devise: 'MAD', segment_client: '', date_debut: '', date_fin: '' }

function CreateListeDialog({ onClose, onCreated }) {
  const [valeurs, setValeurs] = useState(videListe)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setValeurs(s => ({ ...s, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!valeurs.nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    setError(null)
    try {
      await ventesApi.createListePrix(payloadListe(valeurs))
      onCreated()
    } catch (err) {
      setError(frenchError(err, 'La création a échoué.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nouvelle liste de prix</DialogTitle>
          <DialogDescription>
            Ex. « Revendeur », « Export ». Assignez-la ensuite à un client depuis sa fiche.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <ListePrixFields prefix="lp" valeurs={valeurs} set={set} autoFocus />
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Annuler</Button>
            <Button type="submit" loading={busy}>{busy ? 'Création…' : 'Créer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ListeDetailDialog({ liste, produits, onClose, onChanged, onDeleted }) {
  const [addLigneOpen, setAddLigneOpen] = useState(false)
  const [addRegleOpen, setAddRegleOpen] = useState(false)
  // WIR226 — édition / archivage / suppression : l'écran était Create+Read.
  const [editOpen, setEditOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const { confirmDelete, confirm } = useConfirmDialog()

  const produitNom = (id) => produits.find(p => String(p.id) === String(id))?.nom || `Produit #${id}`

  const basculerArchivage = async () => {
    const versArchive = !liste.archived
    if (versArchive) {
      const ok = await confirm({
        title: `Archiver « ${liste.nom} » ?`,
        description: 'Une liste archivée cesse immédiatement de servir à la '
          + 'résolution automatique des prix. Les devis déjà établis ne bougent pas.',
        confirmLabel: 'Archiver',
      })
      if (!ok) return
    }
    setBusy(true); setError(null)
    try {
      await ventesApi.patchListePrix(liste.id, { archived: versArchive })
      onChanged()
    } catch (err) {
      setError(frenchError(err, "L'archivage a échoué."))
    } finally { setBusy(false) }
  }

  const supprimer = async () => {
    const ok = await confirmDelete({
      title: `Supprimer « ${liste.nom} » ?`,
      description: 'La liste, ses prix fixés et ses règles sont supprimés '
        + 'définitivement, et elle disparaît du sélecteur de la fiche client. '
        + 'Préférez l\'archivage pour conserver l\'historique.',
    })
    if (!ok) return
    setBusy(true); setError(null)
    try {
      await ventesApi.deleteListePrix(liste.id)
      onDeleted()
    } catch (err) {
      setError(frenchError(err, 'La suppression a échoué.'))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{liste.nom}</DialogTitle>
          <DialogDescription>
            Prix fixés par produit + règles de paliers (quantité, remise, formule).
            {/* WIR226 — l'état et les critères d'application, jusqu'ici invisibles. */}
            {liste.archived && (
              <span className="mt-1 block font-medium text-warning">
                Liste archivée — elle ne sert plus à la résolution des prix.
              </span>
            )}
            {liste.segment_client && (
              <span className="mt-1 block">Segment : {liste.segment_client}</span>
            )}
            {(liste.date_debut || liste.date_fin) && (
              <span className="mt-1 block">
                Validité : {liste.date_debut || '—'} → {liste.date_fin || '—'}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-semibold">Prix fixés</h4>
              <Button size="sm" variant="outline" onClick={() => setAddLigneOpen(true)}>
                <Plus className="size-3.5" /> Ajouter un prix
              </Button>
            </div>
            {(liste.lignes ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun prix fixé pour l'instant.</p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border text-sm">
                {liste.lignes.map((l) => (
                  <li key={l.id} className="flex items-center justify-between px-3 py-2">
                    <span>{produitNom(l.produit)}</span>
                    <span className="font-medium tabular-nums">{dh(l.prix_unitaire)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-sm font-semibold">Règles / paliers</h4>
              <Button size="sm" variant="outline" onClick={() => setAddRegleOpen(true)}>
                <Plus className="size-3.5" /> Ajouter une règle
              </Button>
            </div>
            {(liste.regles ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune règle de palier pour l'instant.</p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border text-sm">
                {liste.regles.map((r) => (
                  <li key={r.id} className="flex items-center justify-between px-3 py-2">
                    <span>
                      {r.produit ? produitNom(r.produit) : (r.categorie_nom || r.marque || 'Tout le catalogue')}
                      {' — à partir de '}{r.quantite_min}
                    </span>
                    <span className="font-medium tabular-nums">
                      {TYPES_REGLE.find(t => t.value === r.type_regle)?.label ?? r.type_regle} : {r.valeur}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {error && (
          <div role="alert" className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <DialogFooter className="flex-wrap gap-2">
          {/* WIR226 — le trio manquant : modifier / archiver / supprimer. */}
          <Button type="button" variant="outline" size="sm" disabled={busy}
                  onClick={() => setEditOpen(true)}>
            <Pencil className="size-3.5" /> Modifier
          </Button>
          <Button type="button" variant="outline" size="sm" disabled={busy}
                  onClick={basculerArchivage}>
            {liste.archived
              ? <><ArchiveRestore className="size-3.5" /> Réactiver</>
              : <><Archive className="size-3.5" /> Archiver</>}
          </Button>
          <Button type="button" variant="destructive" size="sm" disabled={busy}
                  onClick={supprimer}>
            <Trash2 className="size-3.5" /> Supprimer
          </Button>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>

      {editOpen && (
        <EditListeDialog
          liste={liste}
          onClose={() => setEditOpen(false)}
          onSaved={() => { setEditOpen(false); onChanged() }}
        />
      )}
      {addLigneOpen && (
        <AddLigneDialog
          liste={liste} produits={produits}
          onClose={() => setAddLigneOpen(false)}
          onSaved={() => { setAddLigneOpen(false); onChanged() }}
        />
      )}
      {addRegleOpen && (
        <AddRegleDialog
          liste={liste} produits={produits}
          onClose={() => setAddRegleOpen(false)}
          onSaved={() => { setAddRegleOpen(false); onChanged() }}
        />
      )}
    </Dialog>
  )
}

/* WIR226 — édition d'une liste existante par PATCH (nom / devise / segment /
   période). PATCH et non PUT : on ne renvoie que les champs du formulaire, sans
   jamais toucher aux lignes ni aux règles déjà posées. */
function EditListeDialog({ liste, onClose, onSaved }) {
  const [valeurs, setValeurs] = useState({
    nom: liste.nom ?? '',
    devise: liste.devise ?? 'MAD',
    segment_client: liste.segment_client ?? '',
    date_debut: liste.date_debut ?? '',
    date_fin: liste.date_fin ?? '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setValeurs(s => ({ ...s, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!valeurs.nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true); setError(null)
    try {
      await ventesApi.patchListePrix(liste.id, payloadListe(valeurs))
      onSaved()
    } catch (err) {
      setError(frenchError(err, "L'enregistrement a échoué."))
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Modifier la liste de prix</DialogTitle>
          <DialogDescription>
            Les prix fixés et les règles de paliers de cette liste ne sont pas
            touchés.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <ListePrixFields prefix="lp-edit" valeurs={valeurs} set={set} autoFocus />
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Annuler</Button>
            <Button type="submit" loading={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AddLigneDialog({ liste, produits, onClose, onSaved }) {
  const [produit, setProduit] = useState('')
  const [prixUnitaire, setPrixUnitaire] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!produit || prixUnitaire === '') { setError('Produit et prix sont requis.'); return }
    setBusy(true)
    setError(null)
    try {
      await ventesApi.setLignePrixListe(liste.id, { produit, prix_unitaire: prixUnitaire })
      onSaved()
    } catch (err) {
      setError(err?.response?.data?.detail || "L'ajout a échoué.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Ajouter un prix — {liste.nom}</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="al-produit" required>Produit</Label>
            <Select value={produit} onValueChange={setProduit}>
              <SelectTrigger id="al-produit"><SelectValue placeholder="— Produit —" /></SelectTrigger>
              <SelectContent>
                {produits.map(p => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="al-prix" required>Prix unitaire (TTC/HT selon mode générateur)</Label>
            <Input id="al-prix" type="number" min="0" step="any"
                   value={prixUnitaire} onChange={(e) => setPrixUnitaire(e.target.value)} placeholder="0" />
          </div>
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Annuler</Button>
            <Button type="submit" loading={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AddRegleDialog({ liste, produits, onClose, onSaved }) {
  const [scope, setScope] = useState('produit') // 'produit' | 'categorie' | 'marque' | 'catalogue'
  const [produit, setProduit] = useState('')
  const [categorieNom, setCategorieNom] = useState('')
  const [marque, setMarque] = useState('')
  const [typeRegle, setTypeRegle] = useState('remise_pct')
  const [valeur, setValeur] = useState('')
  const [quantiteMin, setQuantiteMin] = useState('1')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (valeur === '') { setError('La valeur est requise.'); return }
    setBusy(true)
    setError(null)
    try {
      const payload = {
        type_regle: typeRegle,
        valeur,
        quantite_min: quantiteMin || '1',
        produit: scope === 'produit' ? produit : null,
        categorie_nom: scope === 'categorie' ? categorieNom : '',
        marque: scope === 'marque' ? marque : '',
      }
      await ventesApi.addRegleListePrix(liste.id, payload)
      onSaved()
    } catch (err) {
      setError(err?.response?.data?.detail || "L'ajout a échoué.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader><DialogTitle>Ajouter une règle — {liste.nom}</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit} noValidate className="grid gap-4">
          <div className="grid gap-1.5">
            <Label htmlFor="ar-scope">Portée</Label>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger id="ar-scope"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="produit">Produit précis</SelectItem>
                <SelectItem value="categorie">Catégorie</SelectItem>
                <SelectItem value="marque">Marque</SelectItem>
                <SelectItem value="catalogue">Tout le catalogue</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {scope === 'produit' && (
            <div className="grid gap-1.5">
              <Label htmlFor="ar-produit">Produit</Label>
              <Select value={produit} onValueChange={setProduit}>
                <SelectTrigger id="ar-produit"><SelectValue placeholder="— Produit —" /></SelectTrigger>
                <SelectContent>
                  {produits.map(p => (
                    <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {scope === 'categorie' && (
            <div className="grid gap-1.5">
              <Label htmlFor="ar-categorie">Catégorie</Label>
              <Input id="ar-categorie" value={categorieNom} onChange={(e) => setCategorieNom(e.target.value)} />
            </div>
          )}
          {scope === 'marque' && (
            <div className="grid gap-1.5">
              <Label htmlFor="ar-marque">Marque</Label>
              <Input id="ar-marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
            </div>
          )}
          <div className="grid gap-1.5">
            <Label htmlFor="ar-type">Type de règle</Label>
            <Select value={typeRegle} onValueChange={setTypeRegle}>
              <SelectTrigger id="ar-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES_REGLE.map(t => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="ar-valeur" required>Valeur</Label>
              <Input id="ar-valeur" type="number" min="0" step="any"
                     value={valeur} onChange={(e) => setValeur(e.target.value)} placeholder="0" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ar-qtemin">Quantité min (palier)</Label>
              <Input id="ar-qtemin" type="number" min="0" step="any"
                     value={quantiteMin} onChange={(e) => setQuantiteMin(e.target.value)} />
            </div>
          </div>
          {error && (
            <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Annuler</Button>
            <Button type="submit" loading={busy}>{busy ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
