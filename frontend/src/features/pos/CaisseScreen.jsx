import { useEffect, useMemo, useState } from 'react'
import { Plus, Minus, Trash2, Printer, Link2, Usb } from 'lucide-react'
import posApi from '../../api/posApi'
import api from '../../api/axios'
import { prixTtc, sansPrix } from '../stock/catalogue'
import { formatMAD } from '../../lib/format'
import {
  Button, Input, Label, Badge, EmptyState,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  toast,
} from '../../ui'
import { Combobox } from '../../ui/Combobox'
import {
  MODES_PAIEMENT, searchProduitsPos, addToCart, removeFromCart, setQuantite,
  cartLineTotal, cartTotal, cartItemCount, calculerRendu, peutEncaisser,
  chargerTicketsEnAttente, parquerTicket, rappelerTicket, supprimerTicket,
} from './pos'

/* XPOS2 — Écran caisse (vente rapide), route /pos.
   Objectif "done" : une vente accessoire se conclut en < 5 clics — chercher
   (1 frappe + Entrée/clic) → ajouter au panier (1 clic) → Encaisser (1 clic) →
   choisir un mode + confirmer (1 clic) → imprimer/télécharger (1 clic). */
export default function CaisseScreen() {
  const [produits, setProduits] = useState([])
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState([])
  const [client, setClient] = useState(null) // { id, nom } | null (comptoir)
  const [quickCreateOpen, setQuickCreateOpen] = useState(false)
  const [nomRapide, setNomRapide] = useState('')
  const [tickets, setTickets] = useState(() => chargerTicketsEnAttente())
  const [encaissementOpen, setEncaissementOpen] = useState(false)
  const [paiements, setPaiements] = useState([{ mode: 'especes', montant: '' }])
  const [busy, setBusy] = useState(false)
  // XPOS7/9 — la vente validée (VenteComptoir) pilote les actions ticket
  // (PDF / ESC/POS / lien public). null tant qu'aucune vente n'est encaissée.
  const [derniereVente, setDerniereVente] = useState(null)
  // XPOS9 — numéros de série saisis par produitId ("SN1, SN2" → liste).
  const [numerosSerie, setNumerosSerie] = useState({})

  useEffect(() => {
    posApi.getProduits().then((r) => {
      const data = r?.data?.results ?? r?.data ?? []
      setProduits(Array.isArray(data) ? data : [])
    }).catch(() => setProduits([]))
  }, [])

  const resultats = useMemo(() => searchProduitsPos(produits, query), [produits, query])

  const total = useMemo(() => cartTotal(cart), [cart])
  const nbArticles = useMemo(() => cartItemCount(cart), [cart])
  const rendu = useMemo(() => calculerRendu(total, paiements), [total, paiements])
  const encaissable = useMemo(() => peutEncaisser(total, paiements), [total, paiements])

  const handleAjouter = (produit) => {
    if (sansPrix(produit)) {
      toast.error('Ce produit n’a pas encore de prix — à renseigner avant vente.')
      return
    }
    setCart((c) => addToCart(c, { id: produit.id, nom: produit.nom, prixTtc: prixTtc(produit) }))
  }

  const handleQuantite = (produitId, valeur) => setCart((c) => setQuantite(c, produitId, valeur))
  const handleRetirer = (produitId) => {
    setCart((c) => removeFromCart(c, produitId))
    setNumerosSerie((s) => {
      const next = { ...s }
      delete next[produitId]
      return next
    })
  }

  // XPOS9 — capture des numéros de série (séparés par virgule/retour ligne).
  const handleNumerosSerie = (produitId, valeur) =>
    setNumerosSerie((s) => ({ ...s, [produitId]: valeur }))

  const parseNumerosSerie = (valeur) =>
    (valeur || '')
      .split(/[\n,;]+/)
      .map((v) => v.trim())
      .filter(Boolean)

  const onSearchClient = (q) =>
    posApi.searchClients(q).then((r) => {
      const hits = r?.data?.results ?? r?.data ?? []
      return (Array.isArray(hits) ? hits : []).map((h) => ({
        value: String(h.id), label: h.nom, hit: h,
      }))
    })

  const handleClientChoisi = (_v, opt) => {
    if (opt?.hit) setClient({ id: opt.hit.id, nom: opt.hit.nom })
  }

  const handleQuickCreateClient = async () => {
    if (!nomRapide.trim()) return
    setBusy(true)
    try {
      const res = await posApi.createClient({ nom: nomRapide.trim() })
      setClient({ id: res.data.id, nom: res.data.nom })
      setNomRapide('')
      setQuickCreateOpen(false)
      toast.success('Client créé et sélectionné.')
    } catch {
      toast.error('La création du client a échoué.')
    } finally {
      setBusy(false)
    }
  }

  // ── Tickets en attente : parquer la vente en cours / rappeler ────────────
  const handleParquer = () => {
    if (cart.length === 0) return
    parquerTicket({ cart, client })
    setTickets(chargerTicketsEnAttente())
    setCart([])
    setClient(null)
    toast.success('Vente parquée — rappelable depuis les tickets en attente.')
  }

  const handleRappeler = (ticketId) => {
    const ticket = rappelerTicket(ticketId)
    if (!ticket) return
    setCart(ticket.cart || [])
    setClient(ticket.client || null)
    setTickets(chargerTicketsEnAttente())
    toast.success('Ticket rappelé.')
  }

  const handleSupprimerTicket = (ticketId) => {
    supprimerTicket(ticketId)
    setTickets(chargerTicketsEnAttente())
  }

  // ── Encaissement multi-modes ──────────────────────────────────────────────
  const ajouterModePaiement = () =>
    setPaiements((p) => [...p, { mode: 'especes', montant: '' }])
  const majPaiement = (idx, patch) =>
    setPaiements((p) => p.map((pm, i) => (i === idx ? { ...pm, ...patch } : pm)))
  const retirerPaiement = (idx) =>
    setPaiements((p) => (p.length > 1 ? p.filter((_, i) => i !== idx) : p))

  const ouvrirEncaissement = () => {
    if (cart.length === 0) return
    setPaiements([{ mode: 'especes', montant: String(total) }])
    setEncaissementOpen(true)
  }

  // Encaissement (app POS dédiée) : crée une VenteComptoir (brouillon), ajoute
  // ses lignes (produit + qté + prix TTC + numéros de série éventuels), puis la
  // valide avec les paiements — la validation crée la Facture légale + les
  // Paiement côté backend (services.valider_vente). Le client est optionnel.
  const handleConfirmerEncaissement = async () => {
    setBusy(true)
    try {
      const venteRes = await posApi.createVente(
        client?.id ? { client: client.id } : {})
      const venteId = venteRes.data.id
      for (const ligne of cart) {
        await posApi.ajouterLigne(venteId, {
          produit: ligne.produitId,
          quantite: ligne.quantite,
          prix_unitaire_ttc: ligne.prixTtc,
          numeros_serie: parseNumerosSerie(numerosSerie[ligne.produitId]),
        })
      }
      const utiles = paiements
        .map((p) => ({ mode: p.mode, montant: Number(p.montant) || 0 }))
        .filter((p) => p.montant > 0)
      const finale = await posApi.validerVente(venteId, { paiements: utiles })
      setDerniereVente(finale.data)
      toast.success('Vente encaissée.')
      setEncaissementOpen(false)
      setCart([])
      setClient(null)
      setNumerosSerie({})
    } catch {
      toast.error('L’encaissement a échoué — la vente n’a pas été validée.')
    } finally {
      setBusy(false)
    }
  }

  // XPOS7 — ticket PDF : ouvre le PDF rendu par le backend (vente validée).
  const handleImprimer = () => {
    if (!derniereVente?.id) return
    window.open(`${api.defaults.baseURL || ''}/api/django${posApi.ticketPdfUrl(derniereVente.id)}`, '_blank')
  }

  // XPOS7 — ticket ESC/POS : pousse le flux vers l'imprimante réseau configurée
  // (no-op côté backend si aucune imprimante active — le message le reflète).
  const handleTicketEscpos = async () => {
    if (!derniereVente?.id) return
    setBusy(true)
    try {
      const res = await posApi.ticketEscpos(derniereVente.id)
      toast.success(res?.data?.sent_to_printer
        ? 'Ticket envoyé à l’imprimante.'
        : 'Aucune imprimante active — flux ESC/POS généré (non envoyé).')
    } catch {
      toast.error('L’impression ESC/POS a échoué.')
    } finally {
      setBusy(false)
    }
  }

  // XPOS7 — lien public partageable du ticket (tokenisé, sans login client).
  const handleTicketShareLink = async () => {
    if (!derniereVente?.id) return
    setBusy(true)
    try {
      const res = await posApi.ticketShareLink(derniereVente.id)
      const url = `${window.location.origin}/api/django/public/pos/ticket/${res.data.token}/`
      try {
        await navigator.clipboard?.writeText(url)
        toast.success('Lien du ticket copié.')
      } catch {
        toast.success('Lien du ticket généré.')
      }
    } catch {
      toast.error('La génération du lien a échoué.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-semibold">Caisse — vente rapide</h1>
        {tickets.length > 0 && (
          <div className="flex flex-wrap items-center gap-2" data-testid="tickets-en-attente">
            <span className="text-sm text-muted-foreground">Tickets en attente :</span>
            {tickets.map((t) => (
              <Badge key={t.id} className="cursor-pointer" onClick={() => handleRappeler(t.id)}>
                {t.client?.nom || 'Comptoir'} · {cartItemCount(t.cart)} art.
                <button
                  type="button"
                  aria-label="Supprimer ce ticket"
                  onClick={(e) => { e.stopPropagation(); handleSupprimerTicket(t.id) }}
                  className="ml-1"
                >
                  ×
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        {/* Recherche produit instantanée */}
        <div className="rounded-lg border border-border bg-card p-3">
          <Label htmlFor="pos-search">Rechercher un produit — nom, SKU, référence, catégorie</Label>
          <Input
            id="pos-search"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && resultats[0]) handleAjouter(resultats[0]) }}
            placeholder="Taper un nom, un SKU… puis Entrée pour ajouter le premier résultat"
          />
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {resultats.map((p) => {
              const dispo = !sansPrix(p)
              return (
                <button
                  key={p.id}
                  type="button"
                  disabled={!dispo}
                  onClick={() => handleAjouter(p)}
                  className="flex flex-col items-start gap-1 rounded-md border border-border p-2.5 text-left text-sm outline-none transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="line-clamp-2 font-medium">{p.nom}</span>
                  <span className="text-xs tabular-nums text-muted-foreground">
                    {dispo ? `${formatMAD(prixTtc(p), { withSymbol: false })} DH` : 'prix à renseigner'}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Stock : {p.quantite_disponible ?? '—'}
                  </span>
                </button>
              )
            })}
            {resultats.length === 0 && (
              <div className="col-span-full py-6 text-center text-sm text-muted-foreground">
                {query ? `Aucun produit pour « ${query} »` : 'Commencez à taper pour chercher un produit'}
              </div>
            )}
          </div>
        </div>

        {/* Panier tactile */}
        <div className="flex flex-col gap-3 rounded-lg border border-border bg-card p-3">
          <div className="grid gap-1.5">
            <Label htmlFor="pos-client">Client — optionnel</Label>
            <Combobox
              id="pos-client"
              value={client ? String(client.id) : null}
              onSearch={onSearchClient}
              onChange={handleClientChoisi}
              placeholder="Vente comptoir (sans client)"
              searchPlaceholder="Nom du client…"
              emptyText="Aucun client trouvé"
            />
            <Button type="button" variant="ghost" size="sm" onClick={() => setQuickCreateOpen(true)}>
              + Nouveau client
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto" data-testid="panier">
            {cart.length === 0 ? (
              <EmptyState title="Panier vide" description="Ajoutez un produit pour démarrer une vente." />
            ) : (
              <ul className="flex flex-col gap-2">
                {cart.map((l) => (
                  <li key={l.produitId} className="flex flex-col gap-1.5 rounded-md border border-border p-2">
                   <div className="flex items-center gap-2">
                    <div className="flex-1">
                      <div className="text-sm font-medium">{l.nom}</div>
                      <div className="text-xs tabular-nums text-muted-foreground">
                        {formatMAD(l.prixTtc, { withSymbol: false })} DH TTC × {l.quantite} = {formatMAD(cartLineTotal(l), { withSymbol: false })} DH
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button type="button" variant="ghost" size="icon"
                              aria-label={`Diminuer la quantité de ${l.nom}`}
                              onClick={() => handleQuantite(l.produitId, l.quantite - 1)}>
                        <Minus className="size-3.5" />
                      </Button>
                      <input
                        type="number"
                        step="any"
                        aria-label={`Quantité de ${l.nom}`}
                        value={l.quantite}
                        onChange={(e) => handleQuantite(l.produitId, e.target.value)}
                        className="h-8 w-14 rounded-md border border-input bg-card text-center text-sm"
                      />
                      <Button type="button" variant="ghost" size="icon"
                              aria-label={`Augmenter la quantité de ${l.nom}`}
                              onClick={() => handleQuantite(l.produitId, l.quantite + 1)}>
                        <Plus className="size-3.5" />
                      </Button>
                      <Button type="button" variant="ghost" size="icon"
                              aria-label={`Retirer ${l.nom} du panier`}
                              onClick={() => handleRetirer(l.produitId)}>
                        <Trash2 className="size-3.5 text-destructive" />
                      </Button>
                    </div>
                   </div>
                   {/* XPOS9 — numéros de série (optionnel, séparés par virgule). */}
                   <input
                     type="text"
                     aria-label={`Numéros de série de ${l.nom}`}
                     value={numerosSerie[l.produitId] || ''}
                     onChange={(e) => handleNumerosSerie(l.produitId, e.target.value)}
                     className="h-7 w-full rounded-md border border-input bg-card px-2 text-xs"
                     placeholder="N° de série (optionnel, séparés par une virgule)"
                   />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex items-center justify-between border-t border-border pt-2 text-sm">
            <span className="text-muted-foreground">{nbArticles} article(s)</span>
            <span className="text-lg font-semibold tabular-nums" data-testid="pos-total">
              {formatMAD(total, { withSymbol: false })} DH TTC
            </span>
          </div>

          <div className="flex gap-2">
            <Button type="button" variant="outline" className="flex-1"
                    disabled={cart.length === 0} onClick={handleParquer}>
              Parquer
            </Button>
            <Button type="button" className="flex-1"
                    disabled={cart.length === 0} onClick={ouvrirEncaissement}>
              Encaisser
            </Button>
          </div>

          {derniereVente && (
            <div className="flex flex-col gap-2 border-t border-border pt-2" data-testid="ticket-actions">
              <span className="text-xs text-muted-foreground">
                Vente {derniereVente.reference} validée — ticket :
              </span>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={handleImprimer} className="gap-1.5">
                  <Printer className="size-4" /> PDF
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={handleTicketEscpos}
                        disabled={busy} className="gap-1.5">
                  <Usb className="size-4" /> Imprimante caisse
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={handleTicketShareLink}
                        disabled={busy} className="gap-1.5">
                  <Link2 className="size-4" /> Lien partageable
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Quick-create client — pattern QG3/QC1 minimal (nom seul requis). */}
      <Dialog open={quickCreateOpen} onOpenChange={(o) => { if (!o) setQuickCreateOpen(false) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Nouveau client</DialogTitle>
            <DialogDescription>Création rapide — le nom suffit pour la caisse.</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleQuickCreateClient() }} className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="pos-nom-rapide" required>Nom</Label>
              <Input id="pos-nom-rapide" autoFocus value={nomRapide}
                     onChange={(e) => setNomRapide(e.target.value)} placeholder="Nom du client" />
            </div>
            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setQuickCreateOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy}>Créer et sélectionner</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Encaissement multi-modes + rendu de monnaie */}
      <Dialog open={encaissementOpen} onOpenChange={(o) => { if (!o) setEncaissementOpen(false) }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Encaissement</DialogTitle>
            <DialogDescription>Total à payer : {formatMAD(total, { withSymbol: false })} DH TTC</DialogDescription>
          </DialogHeader>
          <form noValidate onSubmit={(e) => { e.preventDefault(); handleConfirmerEncaissement() }} className="grid gap-3">
            {paiements.map((p, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <select
                  aria-label="Mode de paiement"
                  value={p.mode}
                  onChange={(e) => majPaiement(idx, { mode: e.target.value })}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm"
                >
                  {MODES_PAIEMENT.map((m) => (
                    <option key={m.value} value={m.value}>{m.label}</option>
                  ))}
                </select>
                <input
                  type="number"
                  step="any"
                  aria-label="Montant"
                  value={p.montant}
                  onChange={(e) => majPaiement(idx, { montant: e.target.value })}
                  className="h-9 flex-1 rounded-md border border-input bg-card px-2 text-sm"
                  placeholder="Montant"
                />
                {paiements.length > 1 && (
                  <Button type="button" variant="ghost" size="icon" aria-label="Retirer ce mode de paiement"
                          onClick={() => retirerPaiement(idx)}>
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={ajouterModePaiement}>
              + Ajouter un mode de paiement
            </Button>

            <div className="rounded-md bg-muted/40 p-2 text-sm">
              {rendu.reste > 0 && (
                <div className="text-destructive" data-testid="reste-a-payer">
                  Il manque {formatMAD(rendu.reste, { withSymbol: false })} DH
                </div>
              )}
              {rendu.rendu > 0 && (
                <div className="font-medium" data-testid="rendu-monnaie">
                  Monnaie à rendre : {formatMAD(rendu.rendu, { withSymbol: false })} DH
                </div>
              )}
            </div>

            <DialogFooter>
              <Button type="button" variant="ghost" onClick={() => setEncaissementOpen(false)}>Annuler</Button>
              <Button type="submit" loading={busy} disabled={!encaissable}>Confirmer l’encaissement</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
