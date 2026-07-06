import { useEffect, useState } from 'react'
import { Tags, Plus } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Skeleton, EmptyState, Button, Input, Label,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { Table } from '../reporting/Table'

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

  const load = () => {
    setLoading(true)
    ventesApi.getListesPrix()
      .then(r => setListes(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les listes de prix.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    stockApi.getProduits().then(r => setProduits(r.data.results ?? r.data)).catch(() => {})
  }, [])

  const openDetail = (liste) => setDetail(liste)
  const refreshDetail = (id) => {
    ventesApi.getListePrix(id).then(r => setDetail(r.data)).catch(() => {})
  }

  return (
    <div className="ui-root page">
      <div className="page-header flex items-center justify-between" style={{ marginBottom: '1.25rem' }}>
        <h2>Listes de prix</h2>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> Nouvelle liste
        </Button>
      </div>

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
          onCreated={() => { setCreateOpen(false); load() }}
        />
      )}

      {detail && (
        <ListeDetailDialog
          liste={detail}
          produits={produits}
          onClose={() => setDetail(null)}
          onChanged={() => { refreshDetail(detail.id); load() }}
        />
      )}
    </div>
  )
}

function CreateListeDialog({ onClose, onCreated }) {
  const [nom, setNom] = useState('')
  const [devise, setDevise] = useState('MAD')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!nom.trim()) { setError('Le nom est requis.'); return }
    setBusy(true)
    setError(null)
    try {
      await ventesApi.createListePrix({ nom: nom.trim(), devise })
      onCreated()
    } catch (err) {
      setError(err?.response?.data?.detail || 'La création a échoué.')
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
          <div className="grid gap-1.5">
            <Label htmlFor="lp-nom" required>Nom</Label>
            <Input id="lp-nom" value={nom} autoFocus
                   onChange={(e) => setNom(e.target.value)} placeholder="ex : Revendeur" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="lp-devise">Devise</Label>
            <Input id="lp-devise" value={devise} onChange={(e) => setDevise(e.target.value)} />
          </div>
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

function ListeDetailDialog({ liste, produits, onClose, onChanged }) {
  const [addLigneOpen, setAddLigneOpen] = useState(false)
  const [addRegleOpen, setAddRegleOpen] = useState(false)

  const produitNom = (id) => produits.find(p => String(p.id) === String(id))?.nom || `Produit #${id}`

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{liste.nom}</DialogTitle>
          <DialogDescription>
            Prix fixés par produit + règles de paliers (quantité, remise, formule).
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

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>

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
