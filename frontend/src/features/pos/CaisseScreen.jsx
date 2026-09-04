import { useEffect, useMemo, useState } from 'react'
import { Plus, Minus, Trash2, Printer, Link2, Usb, Lock, ScanLine } from 'lucide-react'
// NTRET3 — verrouillage rapide entre deux ventes : overlay plein écran qui
// laisse le panier INTACT dans l'état de cet écran (pas de re-login, la
// session JWT n'est jamais perdue).
import PinLock from './PinLock'
// NTRET22 — mode « scan douchette en flux continu » + raccourcis clavier
// (F2 nouveau ticket, F4 encaisser, Échap annuler la dernière ligne).
import ScanMode from './ScanMode'
import { attacherRaccourcisClavier } from './scanApi'
// NTRET1 / AUD230 — mode offline caisse : la file de synchronisation existait
// (`offlineQueue.js`, testée) mais n'était câblée NULLE PART — une coupure
// réseau pendant un encaissement perdait purement et simplement la vente.
import {
  estHorsLigne, getOfflineVenteQueue, makeUuidClient,
} from './offlineQueue'
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
// WIR7 — extraction canonique du message d'erreur backend (VX203) : plus
// jamais un échec d'encaissement avalé en silence sur ce chemin d'argent.
import { errorMessageFrom } from '../../lib/toast'
import {
  MODES_PAIEMENT, searchProduitsPos, addToCart, removeFromCart, setQuantite,
  cartLineTotal, cartTotal, cartItemCount, calculerRendu, peutEncaisser,
  chargerTicketsEnAttente, parquerTicket, rappelerTicket, supprimerTicket,
} from './pos'

/* NTRET1 / AUD230 — envoi d'UNE vente comptoir au serveur, depuis un payload
   COMPLET (client + lignes + paiements + `uuid_client`).

   C'est le MÊME chemin en ligne et au rejeu : la vente porte son `uuid_client`
   dès la PREMIÈRE tentative, ce qui est la condition pour qu'un rejeu se
   dédupe. Sans cela la dédup serveur ne protégeait que la 1re des 3 étapes
   (`perform_create`), et rejouer une vente à moitié appliquée la dupliquait.

   Le rejeu reprend donc là où la coupure a laissé la vente :
     * vente déjà VALIDÉE (statut ≠ brouillon) → rien à refaire, on la rend ;
     * lignes déjà posées → on ne repose que celles qui manquent (le panier
       fusionne les lignes d'un même produit, `pos.addToCart` : un produit
       déjà présent côté serveur est donc bien la MÊME ligne) ;
     * puis validation avec les paiements.
   Fonction PURE de l'état React (elle ne lit que son payload) : elle peut donc
   servir de `sender` à la file, qui la rejouera longtemps après le démontage
   de l'écran. */
export async function envoyerVenteComptoir(payload) {
  const { uuid_client: uuidClient, client, lignes = [], paiements = [] } = payload || {}
  const venteRes = await posApi.createVente({
    ...(uuidClient ? { uuid_client: uuidClient } : {}),
    ...(client ? { client } : {}),
  })
  const vente = venteRes?.data || {}
  if (vente.statut && vente.statut !== 'brouillon') return vente
  const dejaPosees = new Set(
    (vente.lignes || []).map((l) => String(l.produit)))
  for (const ligne of lignes) {
    if (dejaPosees.has(String(ligne.produit))) continue
    await posApi.ajouterLigne(vente.id, ligne)
  }
  const finale = await posApi.validerVente(vente.id, { paiements })
  return finale?.data
}

// File partagée (IndexedDB → localStorage → mémoire) : le `sender` est câblé
// UNE fois, sur la fonction ci-dessus.
const fileVentes = () => getOfflineVenteQueue(envoyerVenteComptoir)

// Un échec SANS réponse serveur est une coupure réseau ; un 4xx/5xx est un
// refus métier, qui doit rester visible et NE JAMAIS partir en file.
const estPanneReseau = (err) => !err?.response

/* XPOS2 — Écran caisse (vente rapide), route /pos.
   Objectif "done" : une vente accessoire se conclut en < 5 clics — chercher
   (1 frappe + Entrée/clic) → ajouter au panier (1 clic) → Encaisser (1 clic) →
   choisir un mode + confirmer (1 clic) → imprimer/télécharger (1 clic). */
export default function CaisseScreen() {
  // NTRET3 — `verrouille` reste local à cet écran pour que le panier survive
  // au verrouillage ; l'utilisateur JWT attendu au déverrouillage est lu par
  // `PinLock` lui-même (useSelector n'y vit QUE quand l'overlay est monté).
  const [verrouille, setVerrouille] = useState(false)
  // NTRET22 — mode scan douchette : basculable, hors état par défaut (aucun
  // coût pour un poste qui ne l'utilise pas — même patron que `verrouille`).
  const [modeScan, setModeScan] = useState(false)
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
  // WIR58 — encaisser une facture/devis existant au comptoir (XPOS6) :
  // recherche par référence/client → sélection → montant + mode → encaissement.
  const [factureDialogOpen, setFactureDialogOpen] = useState(false)
  const [factureQuery, setFactureQuery] = useState('')
  const [factureResults, setFactureResults] = useState([])
  const [factureRecherche, setFactureRecherche] = useState(false)
  const [factureSel, setFactureSel] = useState(null) // { id, reference, client, montant_du }
  const [factureMontant, setFactureMontant] = useState('')
  const [factureMode, setFactureMode] = useState('especes')
  // NTRET31 — écran client : session ouverte détectée une fois au montage
  // (best-effort, `?.()` — jamais d'exception si l'API n'est pas montée,
  // ex. un test qui mocke un posApi partiel).
  const [sessionId, setSessionId] = useState(null)
  // NTRET1 / AUD230 — nombre de ventes encore en file locale (0 = tout est
  // parti). Affiché en permanence : une vente en attente ne doit jamais être
  // invisible pour le caissier.
  const [ventesEnFile, setVentesEnFile] = useState(0)

  // NTRET1 / AUD230 — rejeu au montage (une coupure a pu survivre à une
  // fermeture d'onglet) puis à CHAQUE retour réseau. `flush()` est réentrante
  // (garde `_flushing`) et le serveur dédupe sur `uuid_client` : ni double
  // envoi, ni double vente.
  useEffect(() => {
    const queue = fileVentes()
    let monte = true
    const majCompteur = () => queue.count()
      .then((n) => { if (monte) setVentesEnFile(n) })
      .catch(() => undefined)
    const rejouer = () => queue.flush()
      .then(majCompteur, majCompteur)
    rejouer()
    if (typeof window === 'undefined') return () => { monte = false }
    window.addEventListener('online', rejouer)
    return () => {
      monte = false
      window.removeEventListener('online', rejouer)
    }
  }, [])

  useEffect(() => {
    posApi.getProduits().then((r) => {
      const data = r?.data?.results ?? r?.data ?? []
      setProduits(Array.isArray(data) ? data : [])
    }).catch(() => setProduits([]))
  }, [])

  useEffect(() => {
    posApi.getSessions?.()?.then((r) => {
      const data = r?.data?.results ?? r?.data ?? []
      const ouverte = (Array.isArray(data) ? data : []).find((s) => s.statut === 'ouverte')
      if (ouverte) setSessionId(ouverte.id)
    }).catch(() => {})
  }, [])

  const resultats = useMemo(() => searchProduitsPos(produits, query), [produits, query])

  const total = useMemo(() => cartTotal(cart), [cart])
  const nbArticles = useMemo(() => cartItemCount(cart), [cart])
  const rendu = useMemo(() => calculerRendu(total, paiements), [total, paiements])
  const encaissable = useMemo(() => peutEncaisser(total, paiements), [total, paiements])

  // NTRET31 — pousse un snapshot du panier vers l'écran client (débounced,
  // best-effort — une erreur réseau ne doit JAMAIS perturber la vente en
  // cours). No-op tant qu'aucune session ouverte n'a été détectée.
  useEffect(() => {
    if (!sessionId) return undefined
    const timer = setTimeout(() => {
      posApi.pushPanierCourant?.(sessionId, {
        lignes: cart.map((l) => ({ nom: l.nom, quantite: l.quantite, prix_ttc: l.prixTtc })),
        total,
        client_nom: client?.nom || '',
        rendu: encaissementOpen ? rendu.rendu : 0,
      })?.catch(() => {})
    }, 500)
    return () => clearTimeout(timer)
  }, [sessionId, cart, total, client, encaissementOpen, rendu.rendu])

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

  // NTRET22 — un code scanné (douchette) cherche une correspondance EXACTE
  // (code-barres, SKU, puis id en dernier recours) — jamais la recherche
  // floue de `resultats` : un scan doit ajouter LE bon article, sans
  // ambiguïté. Silencieux si rien ne correspond (le caissier voit le champ
  // se vider sans effet, plutôt qu'une exception qui casserait le flux).
  const handleScanCode = (code) => {
    const produit = produits.find((p) => (
      (p.code_barres && p.code_barres === code) ||
      (p.sku && p.sku === code) ||
      String(p.id) === code
    ))
    if (!produit) {
      toast.error(`Aucun produit pour le code « ${code} ».`)
      return
    }
    handleAjouter(produit)
  }

  const ouvrirEncaissement = () => {
    if (cart.length === 0) return
    setPaiements([{ mode: 'especes', montant: String(total) }])
    setEncaissementOpen(true)
  }

  // NTRET22 — raccourcis clavier caisse : F2 nouveau ticket, F4 encaisser,
  // Échap annule la dernière ligne du panier. Ré-attaché à chaque
  // changement de panier pour que les callbacks lisent l'état courant
  // (aucun useSelector ici — un simple écouteur DOM, sans risque pour les
  // tests qui montent cet écran sans <Provider>).
  useEffect(() => {
    return attacherRaccourcisClavier({
      onNouveauTicket: () => {
        setCart([])
        setClient(null)
        setNumerosSerie({})
      },
      onEncaisser: () => { if (cart.length > 0) ouvrirEncaissement() },
      onAnnulerLigne: () => setCart((c) => c.slice(0, -1)),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart])

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

  // Encaissement (app POS dédiée) : crée une VenteComptoir (brouillon), ajoute
  // ses lignes (produit + qté + prix TTC + numéros de série éventuels), puis la
  // valide avec les paiements — la validation crée la Facture légale + les
  // Paiement côté backend (services.valider_vente). WIR7 — un client est en
  // réalité TOUJOURS requis (apps/pos/services.py : « Un client est requis
  // pour émettre la facture légale. ») : le champ est visuellement obligatoire
  // ci-dessous, et un échec ici affiche le message réel du backend (jamais un
  // échec silencieux).
  const handleConfirmerEncaissement = async () => {
    setBusy(true)
    // NTRET1 / AUD230 — le payload est assemblé EN ENTIER avant le premier
    // appel : c'est lui, et non trois requêtes séparées, qui part en file si
    // le réseau tombe. `uuid_client` est posé dès la première tentative, sans
    // quoi un rejeu ne pourrait pas se dédupliquer côté serveur.
    const payload = {
      uuid_client: makeUuidClient(),
      ...(client?.id ? { client: client.id } : {}),
      lignes: cart.map((ligne) => ({
        produit: ligne.produitId,
        quantite: ligne.quantite,
        prix_unitaire_ttc: ligne.prixTtc,
        numeros_serie: parseNumerosSerie(numerosSerie[ligne.produitId]),
      })),
      paiements: paiements
        .map((p) => ({ mode: p.mode, montant: Number(p.montant) || 0 }))
        .filter((p) => p.montant > 0),
    }

    const viderLePanier = () => {
      setEncaissementOpen(false)
      setCart([])
      setClient(null)
      setNumerosSerie({})
    }

    const mettreEnFile = async () => {
      const queue = fileVentes()
      await queue.enqueue(payload, { uuidClient: payload.uuid_client })
      setVentesEnFile(await queue.count())
      toast.success(
        'Réseau indisponible — vente enregistrée hors ligne, elle partira '
        + 'automatiquement à la reconnexion.')
      viderLePanier()
    }

    try {
      // Coupure DÉJÀ connue (`navigator.onLine === false`) : inutile de
      // tenter trois appels condamnés — la vente part directement en file.
      if (await estHorsLigne()) {
        await mettreEnFile()
        return
      }
      const finale = await envoyerVenteComptoir(payload)
      setDerniereVente(finale)
      toast.success('Vente encaissée.')
      viderLePanier()
    } catch (err) {
      // AUD230 — une COUPURE RÉSEAU (aucune réponse serveur) ne perd plus la
      // vente : le payload complet part en file, y compris si la coupure est
      // survenue APRÈS la création ou après l'ajout des lignes (le rejeu
      // reprend la vente existante par son `uuid_client`).
      if (estPanneReseau(err)) {
        try {
          await mettreEnFile()
          return
        } catch {
          toast.error(
            'Réseau indisponible ET mise en file impossible — ne videz pas '
            + 'le panier, réessayez.')
          return
        }
      }
      // WIR7 — un REFUS serveur (4xx/5xx) n'est jamais mis en file : le
      // caissier voit le motif exact renvoyé par le backend (ex. « Un client
      // est requis pour émettre la facture légale. »).
      toast.error(errorMessageFrom(err, 'L’encaissement a échoué — la vente n’a pas été validée.'))
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

  // ── WIR58 — encaissement d'une facture existante (XPOS6) ──────────────────
  const ouvrirFactureDialog = () => {
    setFactureQuery('')
    setFactureResults([])
    setFactureSel(null)
    setFactureMontant('')
    setFactureMode('especes')
    setFactureDialogOpen(true)
  }

  const rechercherFactures = async (q) => {
    setFactureRecherche(true)
    try {
      const res = await posApi.rechercheFactures(q)
      const rows = res?.data?.results ?? res?.data ?? []
      setFactureResults(Array.isArray(rows) ? rows : [])
    } catch {
      setFactureResults([])
      toast.error('La recherche de factures a échoué.')
    } finally {
      setFactureRecherche(false)
    }
  }

  const choisirFacture = (facture) => {
    setFactureSel(facture)
    // pré-remplir avec le solde dû (le caissier peut encaisser un acompte).
    setFactureMontant(String(facture.montant_du ?? ''))
  }

  const confirmerEncaissementFacture = async () => {
    if (!factureSel) return
    const montant = Number(factureMontant)
    if (!(montant > 0)) {
      toast.error('Montant invalide.')
      return
    }
    setBusy(true)
    try {
      const res = await posApi.encaisserFacture({
        facture: factureSel.id,
        montant: factureMontant,
        mode: factureMode,
      })
      toast.success(`Encaissement de ${res?.data?.montant ?? factureMontant} DH enregistré sur ${res?.data?.facture ?? factureSel.reference}.`)
      setFactureDialogOpen(false)
    } catch (err) {
      // même exigence WIR7 que l'encaissement panier : jamais un échec avalé.
      toast.error(errorMessageFrom(err, 'L’encaissement de la facture a échoué.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6">
      {/* NTRET3 — overlay de verrouillage : monté SEULEMENT si verrouillé
          (jamais monté sur l'écran déverrouillé), le panier ci-dessous reste
          intact pendant tout le verrouillage. */}
      {verrouille && <PinLock onUnlock={() => setVerrouille(false)} />}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="font-display text-xl font-semibold">Caisse — vente rapide</h1>
          <Button type="button" variant="outline" size="sm" onClick={ouvrirFactureDialog}>
            Encaisser une facture existante
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setVerrouille(true)}
            data-testid="verrouiller-caisse"
          >
            <Lock className="mr-1.5 size-4" aria-hidden="true" />
            Verrouiller
          </Button>
          {/* NTRET22 — bascule le mode scan douchette en flux continu. */}
          <Button
            type="button"
            variant={modeScan ? 'default' : 'outline'}
            size="sm"
            onClick={() => setModeScan((v) => !v)}
            data-testid="basculer-mode-scan"
          >
            <ScanLine className="mr-1.5 size-4" aria-hidden="true" />
            Mode scan
          </Button>
        </div>
        {/* NTRET1 / AUD230 — une vente encaissée hors ligne n'est JAMAIS
            invisible : le caissier voit combien restent à partir. */}
        {ventesEnFile > 0 && (
          <div
            className="flex flex-wrap items-center gap-2"
            data-testid="ventes-hors-ligne"
            role="status"
          >
            <Badge tone="warning">
              {ventesEnFile === 1
                ? '1 vente hors ligne en attente d’envoi'
                : `${ventesEnFile} ventes hors ligne en attente d’envoi`}
            </Badge>
          </div>
        )}
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
          {/* NTRET22 — mode scan douchette, monté SEULEMENT si basculé actif
              (même patron que PinLock/NTRET3 : aucun coût hors usage). */}
          <ScanMode actif={modeScan} onScan={handleScanCode} />
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
            {/* WIR7 — un client est en réalité TOUJOURS requis pour valider
                l'encaissement (facture légale) : le placeholder précédent
                (« Vente comptoir (sans client) ») laissait croire le
                contraire. Champ visuellement obligatoire, jamais un échec
                silencieux à la validation. */}
            <Label htmlFor="pos-client" required>Client</Label>
            <Combobox
              id="pos-client"
              value={client ? String(client.id) : null}
              onSearch={onSearchClient}
              onChange={handleClientChoisi}
              placeholder="Rechercher un client…"
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

      {/* WIR58 — encaisser une facture/devis existant (XPOS6) */}
      <Dialog open={factureDialogOpen} onOpenChange={(o) => { if (!o) setFactureDialogOpen(false) }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Encaisser une facture existante</DialogTitle>
            <DialogDescription>
              Recherchez une facture par référence ou client, puis encaissez son solde au comptoir.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <form
              noValidate
              onSubmit={(e) => { e.preventDefault(); rechercherFactures(factureQuery) }}
              className="flex items-end gap-2"
            >
              <div className="grid flex-1 gap-1.5">
                <Label htmlFor="pos-facture-search">Référence ou client</Label>
                <Input
                  id="pos-facture-search"
                  value={factureQuery}
                  onChange={(e) => setFactureQuery(e.target.value)}
                  placeholder="Ex. FA-2026-… ou nom du client"
                />
              </div>
              <Button type="submit" loading={factureRecherche}>Rechercher</Button>
            </form>

            {factureResults.length > 0 && (
              <ul className="max-h-48 overflow-y-auto rounded-md border border-border" data-testid="facture-resultats">
                {factureResults.map((f) => (
                  <li key={f.id}>
                    <button
                      type="button"
                      onClick={() => choisirFacture(f)}
                      className={
                        'flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm outline-none transition-colors hover:bg-accent ' +
                        (factureSel?.id === f.id ? 'bg-accent' : '')
                      }
                    >
                      <span className="flex flex-col">
                        <span className="font-medium">{f.reference}</span>
                        <span className="text-xs text-muted-foreground">{f.client || 'Sans client'}</span>
                      </span>
                      <span className="tabular-nums text-xs text-muted-foreground">
                        Dû : {formatMAD(f.montant_du, { withSymbol: false })} DH
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {factureResults.length === 0 && factureQuery && !factureRecherche && (
              <div className="py-4 text-center text-sm text-muted-foreground">
                Aucune facture avec solde dû pour « {factureQuery} ».
              </div>
            )}

            {factureSel && (
              <form
                noValidate
                onSubmit={(e) => { e.preventDefault(); confirmerEncaissementFacture() }}
                className="grid gap-3 border-t border-border pt-3"
              >
                <div className="text-sm">
                  Encaissement sur <span className="font-medium">{factureSel.reference}</span>
                </div>
                <div className="flex items-end gap-2">
                  <select
                    aria-label="Mode de paiement"
                    value={factureMode}
                    onChange={(e) => setFactureMode(e.target.value)}
                    className="h-9 rounded-md border border-input bg-card px-2 text-sm"
                  >
                    {MODES_PAIEMENT.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                  <div className="grid flex-1 gap-1.5">
                    <Label htmlFor="pos-facture-montant" required>Montant</Label>
                    <input
                      id="pos-facture-montant"
                      type="number"
                      step="any"
                      aria-label="Montant à encaisser"
                      value={factureMontant}
                      onChange={(e) => setFactureMontant(e.target.value)}
                      className="h-9 rounded-md border border-input bg-card px-2 text-sm"
                      placeholder="Montant"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="button" variant="ghost" onClick={() => setFactureDialogOpen(false)}>Annuler</Button>
                  <Button type="submit" loading={busy}>Encaisser la facture</Button>
                </DialogFooter>
              </form>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
