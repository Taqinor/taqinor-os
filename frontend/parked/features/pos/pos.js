// XPOS2 — Logique PURE de l'écran caisse (vente rapide, /pos) : panier, totaux
// 100 % TTC, rendu de monnaie, tickets en attente (parquer/rappeler), et le
// filtrage produit réutilisé du catalogue existant (features/stock/catalogue.js).
// Aucune I/O ici : les appels réseau restent dans posApi.js / CaisseScreen.jsx.
import { searchCatalogue } from '../stock/catalogue'

// Modes d'encaissement — reflet exact de apps/ventes/models.py Paiement.Mode
// (jamais une liste réinventée côté front : mêmes clés que le backend accepte
// tel quel dans enregistrer-paiement).
export const MODES_PAIEMENT = [
  { value: 'especes', label: 'Espèces' },
  { value: 'carte', label: 'Carte bancaire' },
  { value: 'virement', label: 'Virement' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'autre', label: 'Autre' },
]

// ── Recherche produit (nom/SKU/référence/catégorie) + stock dispo affiché ──
// Réutilise searchCatalogue (stock/catalogue.js) : même moteur transverse que
// le reste de l'appli. `quantite_disponible` (N14) vient tel quel du serializer
// stock (GET /stock/produits/) — jamais recalculé côté front.
export function searchProduitsPos(produits, query) {
  const actifs = (produits || []).filter((p) => !p.is_archived)
  return searchCatalogue(actifs, query)
}

// ── Panier ──────────────────────────────────────────────────────────────────
// Ligne panier : { produitId, nom, prixTtc, quantite }. Toujours en TTC (règle
// du module — la caisse est 100 % TTC, jamais de HT affiché à l'écran).
export function addToCart(cart, produit, quantite = 1) {
  const qty = Number(quantite) || 0
  if (qty <= 0) return cart
  const idx = cart.findIndex((l) => l.produitId === produit.id)
  if (idx === -1) {
    return [...cart, {
      produitId: produit.id,
      nom: produit.nom,
      prixTtc: Number(produit.prixTtc ?? produit.prix_ttc ?? 0),
      quantite: qty,
    }]
  }
  return cart.map((l, i) => (i === idx ? { ...l, quantite: l.quantite + qty } : l))
}

export function removeFromCart(cart, produitId) {
  return cart.filter((l) => l.produitId !== produitId)
}

// setQuantite tolère toute saisie numérique (y compris décimale/incomplète) —
// jamais de snap/rejet : une quantité <= 0 retire la ligne (comportement
// attendu d'un champ quantité de panier), tout le reste est accepté tel quel.
export function setQuantite(cart, produitId, quantite) {
  const qty = Number(quantite)
  if (!Number.isFinite(qty) || qty <= 0) return removeFromCart(cart, produitId)
  return cart.map((l) => (l.produitId === produitId ? { ...l, quantite: qty } : l))
}

export function cartLineTotal(line) {
  return (Number(line.prixTtc) || 0) * (Number(line.quantite) || 0)
}

// Total TTC du panier — arrondi au centime pour éviter les résidus flottants
// (0.1 + 0.2 …) dans l'affichage et le calcul du rendu de monnaie.
export function cartTotal(cart) {
  const total = (cart || []).reduce((sum, l) => sum + cartLineTotal(l), 0)
  return Math.round(total * 100) / 100
}

export function cartItemCount(cart) {
  return (cart || []).reduce((sum, l) => sum + (Number(l.quantite) || 0), 0)
}

// ── Encaissement multi-modes + rendu de monnaie ─────────────────────────────
// `paiements` = [{ mode, montant }] — plusieurs modes possibles sur une même
// vente (ex. partie espèces + partie carte). Le rendu de monnaie ne s'applique
// qu'à la part réglée en espèces (rendre la monnaie sur une carte n'a pas de
// sens) : seul l'excédent au-delà du total dû, plafonné par l'espèces reçue,
// est rendu.
export function totalEncaisse(paiements) {
  return (paiements || []).reduce((sum, p) => sum + (Number(p.montant) || 0), 0)
}

export function totalEspeces(paiements) {
  return (paiements || [])
    .filter((p) => p.mode === 'especes')
    .reduce((sum, p) => sum + (Number(p.montant) || 0), 0)
}

// Retourne { du, encaisse, rendu, reste } — `rendu` > 0 = monnaie à rendre au
// client (plafonné à l'espèces reçue) ; `reste` > 0 = il manque de l'argent.
export function calculerRendu(total, paiements) {
  const du = Math.round((Number(total) || 0) * 100) / 100
  const encaisse = Math.round(totalEncaisse(paiements) * 100) / 100
  const especes = Math.round(totalEspeces(paiements) * 100) / 100
  const excedent = Math.round((encaisse - du) * 100) / 100
  const rendu = excedent > 0 ? Math.min(excedent, especes) : 0
  const reste = excedent < 0 ? Math.round(Math.abs(excedent) * 100) / 100 : 0
  return { du, encaisse, rendu, reste }
}

export function peutEncaisser(total, paiements) {
  return calculerRendu(total, paiements).reste <= 0 && totalEncaisse(paiements) > 0
}

// ── Tickets en attente (parquer / rappeler) ─────────────────────────────────
// Purement client-side (localStorage) : aucun endpoint backend "ticket en
// attente" n'existe. Un ticket parqué reprend son propre id, son panier et le
// client éventuellement choisi ; il est retiré de la liste au rappel.
const TICKETS_KEY = 'pos:tickets-en-attente'

export function chargerTicketsEnAttente(storage = safeStorage()) {
  try {
    const raw = storage?.getItem(TICKETS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function sauvegarderTickets(tickets, storage = safeStorage()) {
  try { storage?.setItem(TICKETS_KEY, JSON.stringify(tickets)) } catch { /* quota/privé */ }
}

export function parquerTicket({ cart, client }, storage = safeStorage()) {
  const tickets = chargerTicketsEnAttente(storage)
  const ticket = {
    id: `tk-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    cart,
    client: client || null,
    creeLe: new Date().toISOString(),
  }
  sauvegarderTickets([...tickets, ticket], storage)
  return ticket
}

// Retire le ticket rappelé de la liste des tickets en attente et le retourne
// (ou null si introuvable) — l'appelant restaure `cart`/`client` dans l'état.
export function rappelerTicket(ticketId, storage = safeStorage()) {
  const tickets = chargerTicketsEnAttente(storage)
  const ticket = tickets.find((t) => t.id === ticketId) || null
  if (ticket) sauvegarderTickets(tickets.filter((t) => t.id !== ticketId), storage)
  return ticket
}

export function supprimerTicket(ticketId, storage = safeStorage()) {
  const tickets = chargerTicketsEnAttente(storage)
  sauvegarderTickets(tickets.filter((t) => t.id !== ticketId), storage)
}

function safeStorage() {
  return typeof window !== 'undefined' && window.localStorage ? window.localStorage : null
}
