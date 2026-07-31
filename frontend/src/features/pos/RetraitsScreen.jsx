import { useEffect, useMemo, useState } from 'react'
import { Plus, Minus, Trash2 } from 'lucide-react'
import posApi from '../../api/posApi'
import {
  Button, Input, Label, Badge, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  toast,
} from '../../ui'
import { Combobox } from '../../ui/Combobox'
import { errorMessageFrom } from '../../lib/toast'
import { searchProduitsPos, addToCart, removeFromCart, setQuantite, cartItemCount } from './pos'

/* XPOS15 — File click-and-collect (route /pos/retraits).
   Workflow : à préparer → prêt → retiré. « Marquer prêt » décrémente le stock
   (backend) ; « Remettre » vérifie le code de retrait du client.

   WIR151 — `CommandeRetraitViewSet.perform_create`/`ajouter_ligne` étaient
   complets côté backend mais cet écran ne faisait que lister/marquer prêt/
   remettre : « Nouvelle commande » ouvre un dialogue client (recherche,
   `Combobox` — même patron que `CaisseScreen.jsx`) + panier (recherche
   produit + quantités, `pos.js`), crée la commande puis ses lignes une à une. */
const STATUT_LABEL = {
  a_preparer: 'À préparer',
  pret: 'Prêt au retrait',
  retire: 'Retiré',
  annule: 'Annulé',
}
const STATUT_TONE = {
  a_preparer: 'warning',
  pret: 'info',
  retire: 'success',
  annule: 'neutral',
}

export default function RetraitsScreen() {
  const [retraits, setRetraits] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  // Remise : dialogue de vérification du code de retrait.
  const [remiseOpen, setRemiseOpen] = useState(false)
  const [commande, setCommande] = useState(null)
  const [code, setCode] = useState('')

  // WIR151 — création d'une commande retrait (client + lignes).
  const [creationOpen, setCreationOpen] = useState(false)
  const [nouveauClient, setNouveauClient] = useState(null) // { id, nom }
  const [produits, setProduits] = useState([])
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState([])

  const load = () => {
    return posApi.getRetraits()
      .then((r) => {
        const data = r?.data?.results ?? r?.data ?? []
        setRetraits(Array.isArray(data) ? data : [])
      })
      .catch(() => setRetraits([]))
      .finally(() => setLoading(false))
  }
  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, [])

  const enAttente = useMemo(
    () => retraits.filter((c) => c.statut === 'a_preparer' || c.statut === 'pret'),
    [retraits])

  const handleMarquerPret = async (c) => {
    setBusy(true)
    try {
      await posApi.marquerPret(c.id)
      toast.success('Commande prête au retrait.')
      await charger()
    } catch {
      toast.error('Impossible de marquer prête (stock insuffisant ?).')
    } finally {
      setBusy(false)
    }
  }

  const ouvrirRemise = (c) => {
    setCommande(c)
    setCode('')
    setRemiseOpen(true)
  }

  const handleRemettre = async () => {
    if (!commande) return
    setBusy(true)
    try {
      await posApi.remettreRetrait(commande.id, { code: code.trim() })
      toast.success('Commande remise au client.')
      setRemiseOpen(false)
      setCommande(null)
      await charger()
    } catch {
      toast.error('Code de retrait invalide ou commande non prête.')
    } finally {
      setBusy(false)
    }
  }

  // WIR151 — ouverture du dialogue de création (réinitialise le panier/client).
  const ouvrirCreation = () => {
    setNouveauClient(null)
    setQuery('')
    setCart([])
    setCreationOpen(true)
    if (produits.length === 0) {
      posApi.getProduits().then((r) => {
        const data = r?.data?.results ?? r?.data ?? []
        setProduits(Array.isArray(data) ? data : [])
      }).catch(() => setProduits([]))
    }
  }

  const resultatsProduits = useMemo(
    () => searchProduitsPos(produits, query), [produits, query])

  const onSearchClient = (q) =>
    posApi.searchClients(q).then((r) => {
      const hits = r?.data?.results ?? r?.data ?? []
      return (Array.isArray(hits) ? hits : []).map((h) => ({
        value: String(h.id), label: h.nom, hit: h,
      }))
    })

  const handleClientChoisi = (_v, opt) => {
    if (opt?.hit) setNouveauClient({ id: opt.hit.id, nom: opt.hit.nom })
  }

  const handleAjouterAuPanier = (produit) =>
    setCart((c) => addToCart(c, { id: produit.id, nom: produit.nom }))
  const handleQuantitePanier = (produitId, valeur) =>
    setCart((c) => setQuantite(c, produitId, valeur))
  const handleRetirerDuPanier = (produitId) =>
    setCart((c) => removeFromCart(c, produitId))

  // Crée la commande (client) puis chaque ligne l'une après l'autre — même
  // séquence create→ajouterLigne que `CaisseScreen.handleConfirmerEncaissement`.
  const handleCreerCommande = async () => {
    if (!nouveauClient?.id || cart.length === 0) return
    setBusy(true)
    try {
      const res = await posApi.createRetrait({ client: nouveauClient.id })
      const retraitId = res.data.id
      for (const ligne of cart) {
        await posApi.ajouterLigneRetrait(retraitId, {
          produit: ligne.produitId,
          quantite: ligne.quantite,
        })
      }
      toast.success('Commande retrait créée.')
      setCreationOpen(false)
      await charger()
    } catch (err) {
      toast.error(errorMessageFrom(err, 'La création de la commande a échoué.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-xl font-semibold">Retraits en magasin</h1>
          <Button type="button" size="sm" onClick={ouvrirCreation}>
            + Nouvelle commande
          </Button>
        </div>
        <span className="text-sm text-muted-foreground">{enAttente.length} en attente</span>
      </div>

      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : retraits.length === 0 ? (
        <EmptyState title="Aucune commande" description="Les commandes à retirer apparaîtront ici." />
      ) : (
        <ul className="flex flex-col gap-2" data-testid="retraits-liste">
          {retraits.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-card p-3">
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{c.reference}</span>
                  <Badge tone={STATUT_TONE[c.statut] || 'neutral'}>
                    {STATUT_LABEL[c.statut] || c.statut}
                  </Badge>
                </div>
                <span className="text-xs text-muted-foreground">
                  {c.client_nom || `Client #${c.client}`}
                  {' · '}{(c.lignes || []).length} article(s)
                </span>
              </div>
              <div className="flex gap-2">
                {c.statut === 'a_preparer' && (
                  <Button type="button" size="sm" onClick={() => handleMarquerPret(c)} disabled={busy}>
                    Marquer prêt
                  </Button>
                )}
                {c.statut === 'pret' && (
                  <Button type="button" size="sm" onClick={() => ouvrirRemise(c)} disabled={busy}>
                    Remettre
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Remise au client — vérification du code de retrait */}
      <Dialog open={remiseOpen} onOpenChange={(o) => { if (!o) setRemiseOpen(false) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Remettre la commande {commande?.reference}</DialogTitle>
            <DialogDescription>Saisissez le code de retrait communiqué au client.</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleRemettre() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="retrait-code" required>Code de retrait</Label>
              <Input id="retrait-code" autoFocus value={code}
                     onChange={(e) => setCode(e.target.value)} placeholder="Ex. A1B2C3" />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setRemiseOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy}>Confirmer la remise</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* WIR151 — Nouvelle commande retrait : client + lignes (produit + qté) */}
      <Dialog open={creationOpen} onOpenChange={(o) => { if (!o) setCreationOpen(false) }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Nouvelle commande retrait</DialogTitle>
            <DialogDescription>Choisissez un client puis ajoutez les articles à préparer.</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleCreerCommande() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="retrait-client" required>Client</Label>
              <Combobox
                id="retrait-client"
                value={nouveauClient ? String(nouveauClient.id) : null}
                onSearch={onSearchClient}
                onChange={handleClientChoisi}
                placeholder="Rechercher un client…"
                searchPlaceholder="Nom du client…"
                emptyText="Aucun client trouvé"
              />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="retrait-produit">Ajouter un article</Label>
              <Input
                id="retrait-produit"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Nom, SKU, référence…"
              />
              {query && (
                <ul className="max-h-32 overflow-y-auto rounded-md border border-border">
                  {resultatsProduits.map((p) => (
                    <li key={p.id}>
                      <button
                        type="button"
                        onClick={() => { handleAjouterAuPanier(p); setQuery('') }}
                        className="flex w-full items-center justify-between px-3 py-1.5 text-left text-sm outline-none hover:bg-accent"
                      >
                        {p.nom}
                      </button>
                    </li>
                  ))}
                  {resultatsProduits.length === 0 && (
                    <li className="px-3 py-2 text-sm text-muted-foreground">Aucun produit pour « {query} »</li>
                  )}
                </ul>
              )}
            </div>

            {cart.length === 0 ? (
              <EmptyState title="Aucun article" description="Ajoutez au moins un article à préparer." />
            ) : (
              <ul className="flex flex-col gap-1.5" data-testid="retrait-panier">
                {cart.map((l) => (
                  <li key={l.produitId} className="flex items-center gap-2 rounded-md border border-border p-2">
                    <span className="flex-1 text-sm">{l.nom}</span>
                    <Button type="button" variant="ghost" size="icon"
                            aria-label={`Diminuer la quantité de ${l.nom}`}
                            onClick={() => handleQuantitePanier(l.produitId, l.quantite - 1)}>
                      <Minus className="size-3.5" />
                    </Button>
                    <input
                      type="number" step="any"
                      aria-label={`Quantité de ${l.nom}`}
                      value={l.quantite}
                      onChange={(e) => handleQuantitePanier(l.produitId, e.target.value)}
                      className="h-8 w-14 rounded-md border border-input bg-card text-center text-sm"
                    />
                    <Button type="button" variant="ghost" size="icon"
                            aria-label={`Augmenter la quantité de ${l.nom}`}
                            onClick={() => handleQuantitePanier(l.produitId, l.quantite + 1)}>
                      <Plus className="size-3.5" />
                    </Button>
                    <Button type="button" variant="ghost" size="icon"
                            aria-label={`Retirer ${l.nom} de la commande`}
                            onClick={() => handleRetirerDuPanier(l.produitId)}>
                      <Trash2 className="size-3.5 text-destructive" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setCreationOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy} disabled={!nouveauClient?.id || cart.length === 0}>
                Créer la commande ({cartItemCount(cart)} article{cartItemCount(cart) > 1 ? 's' : ''})
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
