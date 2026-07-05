import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  searchProduitsPos, addToCart, removeFromCart, setQuantite, cartLineTotal,
  cartTotal, cartItemCount, calculerRendu, peutEncaisser,
  parquerTicket, rappelerTicket, supprimerTicket, chargerTicketsEnAttente,
} from './pos'

/* Tests du module POS (XPOS2). Trois volets : (1) logique panier PURE, (2)
   rendu de monnaie / encaissement multi-modes, (3) tickets en attente
   (parquer/rappeler, localStorage) — puis un rendu smoke de l'écran caisse. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

// ── Mémoire localStorage isolée pour chaque test (tickets en attente) ──────
function memoryStorage() {
  const store = new Map()
  return {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, v),
    removeItem: (k) => store.delete(k),
  }
}

describe('recherche produit (searchProduitsPos)', () => {
  const produits = [
    { id: 1, nom: 'Panneau 550W Longi', sku: 'PAN-550', is_archived: false, prix_vente: '1000' },
    { id: 2, nom: 'Onduleur Deye 6kW', sku: 'OND-6K', is_archived: false, prix_vente: '5000' },
    { id: 3, nom: 'Ancien câble', sku: 'CBL-OLD', is_archived: true, prix_vente: '10' },
  ]

  it('filtre par nom/SKU (insensible à la casse) et exclut les archivés', () => {
    expect(searchProduitsPos(produits, 'panneau')).toHaveLength(1)
    expect(searchProduitsPos(produits, 'OND-6K')).toHaveLength(1)
    expect(searchProduitsPos(produits, '')).toHaveLength(2) // pas d'archivé
    expect(searchProduitsPos(produits, 'ancien')).toHaveLength(0)
  })
})

describe('panier (addToCart/removeFromCart/setQuantite/cartTotal)', () => {
  const produitA = { id: 1, nom: 'Panneau 550W', prixTtc: 1200 }
  const produitB = { id: 2, nom: 'Onduleur 6kW', prixTtc: 8000 }

  it('ajoute un produit avec quantité par défaut 1', () => {
    const cart = addToCart([], produitA)
    expect(cart).toEqual([{ produitId: 1, nom: 'Panneau 550W', prixTtc: 1200, quantite: 1 }])
  })

  it('cumule la quantité si le produit est déjà dans le panier', () => {
    let cart = addToCart([], produitA)
    cart = addToCart(cart, produitA, 2)
    expect(cart).toHaveLength(1)
    expect(cart[0].quantite).toBe(3)
  })

  it('ignore un ajout de quantité <= 0', () => {
    expect(addToCart([], produitA, 0)).toEqual([])
    expect(addToCart([], produitA, -1)).toEqual([])
  })

  it('retire une ligne du panier', () => {
    let cart = addToCart([], produitA)
    cart = addToCart(cart, produitB)
    cart = removeFromCart(cart, 1)
    expect(cart).toHaveLength(1)
    expect(cart[0].produitId).toBe(2)
  })

  it('setQuantite met à jour librement (jamais de rejet d’une valeur décimale)', () => {
    let cart = addToCart([], produitA)
    cart = setQuantite(cart, 1, 2.5)
    expect(cart[0].quantite).toBe(2.5)
  })

  it('setQuantite retire la ligne si la quantité tombe à 0 ou moins', () => {
    let cart = addToCart([], produitA)
    cart = setQuantite(cart, 1, 0)
    expect(cart).toEqual([])
  })

  it('setQuantite tolère une saisie non numérique en cours de frappe (retire, ne plante pas)', () => {
    let cart = addToCart([], produitA)
    cart = setQuantite(cart, 1, '')
    expect(cart).toEqual([])
  })

  it('cartLineTotal / cartTotal / cartItemCount calculent juste, y compris avec des décimales', () => {
    let cart = addToCart([], produitA, 2) // 1200 * 2 = 2400
    cart = addToCart(cart, produitB, 1.5) // 8000 * 1.5 = 12000
    expect(cartLineTotal(cart[0])).toBe(2400)
    expect(cartLineTotal(cart[1])).toBe(12000)
    expect(cartTotal(cart)).toBe(14400)
    expect(cartItemCount(cart)).toBe(3.5)
  })

  it('cartTotal arrondit au centime (évite les résidus flottants)', () => {
    const cart = [{ produitId: 1, nom: 'x', prixTtc: 0.1, quantite: 3 }]
    expect(cartTotal(cart)).toBe(0.3)
  })
})

describe('rendu de monnaie (calculerRendu / peutEncaisser)', () => {
  it('rendu = 0 quand le montant réglé égale exactement le total', () => {
    const r = calculerRendu(100, [{ mode: 'especes', montant: 100 }])
    expect(r).toEqual({ du: 100, encaisse: 100, rendu: 0, reste: 0 })
    expect(peutEncaisser(100, [{ mode: 'especes', montant: 100 }])).toBe(true)
  })

  it('calcule la monnaie à rendre sur un billet en espèces', () => {
    const r = calculerRendu(87.5, [{ mode: 'especes', montant: 100 }])
    expect(r.rendu).toBe(12.5)
    expect(r.reste).toBe(0)
  })

  it('signale un reste à payer si le montant réglé est insuffisant', () => {
    const r = calculerRendu(100, [{ mode: 'especes', montant: 60 }])
    expect(r.reste).toBe(40)
    expect(r.rendu).toBe(0)
    expect(peutEncaisser(100, [{ mode: 'especes', montant: 60 }])).toBe(false)
  })

  it('ne rend jamais plus que l’espèces reçue (le surplus carte n’est pas "rendu")', () => {
    // Total 100 : 90 en carte (pas de monnaie sur carte) + 20 en espèces.
    const r = calculerRendu(100, [
      { mode: 'carte', montant: 90 },
      { mode: 'especes', montant: 20 },
    ])
    // Excédent total = 10, mais seule l'espèces (20) peut être rendue → rendu = 10 (<=20), correct ici.
    expect(r.rendu).toBe(10)
  })

  it('plafonne le rendu à l’espèces reçue même si l’excédent la dépasse', () => {
    // Total 50 : 45 en carte + 10 en espèces → encaissé 55, excédent 5, espèces 10 → rendu = 5.
    const r1 = calculerRendu(50, [{ mode: 'carte', montant: 45 }, { mode: 'especes', montant: 10 }])
    expect(r1.rendu).toBe(5)

    // Total 10 : 0 en carte + 100 en espèces (gros billet) → excédent 90, espèces 100 → rendu plafonné à 90 (<=100).
    const r2 = calculerRendu(10, [{ mode: 'especes', montant: 100 }])
    expect(r2.rendu).toBe(90)
  })

  it('multi-modes cumule plusieurs paiements du même mode', () => {
    const r = calculerRendu(150, [
      { mode: 'especes', montant: 50 },
      { mode: 'especes', montant: 50 },
      { mode: 'carte', montant: 50 },
    ])
    expect(r.encaisse).toBe(150)
    expect(r.reste).toBe(0)
    expect(r.rendu).toBe(0)
  })

  it('peutEncaisser refuse un encaissement à 0', () => {
    expect(peutEncaisser(0, [])).toBe(false)
    expect(peutEncaisser(100, [{ mode: 'especes', montant: 0 }])).toBe(false)
  })
})

describe('tickets en attente (parquer/rappeler/supprimer)', () => {
  let storage
  beforeEach(() => { storage = memoryStorage() })

  it('parque un ticket puis le retrouve dans la liste', () => {
    const cart = [{ produitId: 1, nom: 'Panneau', prixTtc: 1000, quantite: 1 }]
    const ticket = parquerTicket({ cart, client: { id: 5, nom: 'Client X' } }, storage)
    const tickets = chargerTicketsEnAttente(storage)
    expect(tickets).toHaveLength(1)
    expect(tickets[0].id).toBe(ticket.id)
    expect(tickets[0].cart).toEqual(cart)
    expect(tickets[0].client).toEqual({ id: 5, nom: 'Client X' })
  })

  it('rappelle un ticket : le retire de la liste et restitue son panier', () => {
    const cart = [{ produitId: 2, nom: 'Onduleur', prixTtc: 5000, quantite: 1 }]
    const ticket = parquerTicket({ cart, client: null }, storage)
    const rappele = rappelerTicket(ticket.id, storage)
    expect(rappele.cart).toEqual(cart)
    expect(chargerTicketsEnAttente(storage)).toHaveLength(0)
  })

  it('rappelerTicket renvoie null pour un id inconnu (ne plante pas)', () => {
    expect(rappelerTicket('inexistant', storage)).toBeNull()
  })

  it('supprime un ticket sans le rappeler', () => {
    const t1 = parquerTicket({ cart: [], client: null }, storage)
    const t2 = parquerTicket({ cart: [], client: null }, storage)
    supprimerTicket(t1.id, storage)
    const tickets = chargerTicketsEnAttente(storage)
    expect(tickets).toHaveLength(1)
    expect(tickets[0].id).toBe(t2.id)
  })

  it('chargerTicketsEnAttente tolère un storage vide/corrompu', () => {
    expect(chargerTicketsEnAttente(storage)).toEqual([])
    storage.setItem('pos:tickets-en-attente', '{not-json')
    expect(chargerTicketsEnAttente(storage)).toEqual([])
  })
})

// ── Rendu smoke de l'écran (API mockée, hors réseau) ────────────────────────
vi.mock('../../api/posApi', () => ({
  default: {
    getProduits: () => Promise.resolve({ data: { results: [] } }),
    searchClients: () => Promise.resolve({ data: { results: [] } }),
    createClient: () => Promise.resolve({ data: { id: 1, nom: 'Client comptoir' } }),
    createFacture: () => Promise.resolve({ data: { id: 1 } }),
    createLigneFacture: () => Promise.resolve({ data: {} }),
    enregistrerPaiement: () => Promise.resolve({ data: {} }),
    emettreFacture: () => Promise.resolve({ data: {} }),
    getFacture: () => Promise.resolve({ data: { id: 1, reference: 'FAC-0001' } }),
  },
}))

import CaisseScreen from './CaisseScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de CaisseScreen', () => {
  it('affiche le titre et le panier vide au chargement', async () => {
    withProviders(<CaisseScreen />)
    expect(screen.getByRole('heading', { name: /Caisse/ })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/Panier vide/)).toBeInTheDocument())
    expect(screen.getByTestId('pos-total')).toHaveTextContent('0')
  })
})
