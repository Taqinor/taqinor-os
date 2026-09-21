import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  optionsFrom, tourneeToStops, ecartLigne, grouperLignesParEcart,
  progressionComptage, actionsDisponiblesTransfert, aPreuveLivraison, podComplete,
  LIVRAISON_STATUTS,
} from './logistique'

// jsdom n'implémente pas ResizeObserver (mesuré par certains primitifs UI) —
// on le polyfill localement pour que les écrans se montent proprement.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

/* Tests du module Logistique (XSTK2). Deux volets : (1) la logique PURE
   (regroupement des écarts de comptage, rendu de la tournée FG332, actions
   disponibles pour une demande de transfert) ; (2) un rendu smoke des écrans,
   enveloppés dans <MemoryRouter> + <ThemeProvider>. Les appels API sont mockés
   pour rester hors réseau. */

describe('optionsFrom', () => {
  it('transforme un map de statuts en options {value,label}', () => {
    expect(optionsFrom(LIVRAISON_STATUTS)).toEqual([
      { value: 'planifiee', label: 'Planifiée' },
      { value: 'en_transit', label: 'En transit' },
      { value: 'livree', label: 'Livrée' },
      { value: 'annulee', label: 'Annulée' },
    ])
  })
})

describe('tourneeToStops', () => {
  it('numérote les arrêts géolocalisés dans l’ordre reçu', () => {
    const tournee = {
      ordre: [
        { livraison_id: 1, reference: 'LIV-202607-0001', gps_lat: 33.5, gps_lng: -7.6 },
        { livraison_id: 2, reference: 'LIV-202607-0002', gps_lat: 33.6, gps_lng: -7.5 },
      ],
      sans_gps: [{ livraison_id: 3, reference: 'LIV-202607-0003' }],
    }
    const stops = tourneeToStops(tournee)
    expect(stops).toHaveLength(3)
    expect(stops[0]).toMatchObject({ position: 1, livraisonId: 1, geolocalisee: true })
    expect(stops[1]).toMatchObject({ position: 2, livraisonId: 2, geolocalisee: true })
    expect(stops[2]).toMatchObject({ position: null, livraisonId: 3, geolocalisee: false })
  })

  it('ne plante jamais sur une réponse absente/partielle', () => {
    expect(tourneeToStops(null)).toEqual([])
    expect(tourneeToStops(undefined)).toEqual([])
    expect(tourneeToStops({})).toEqual([])
    expect(tourneeToStops([])).toEqual([])
  })
})

describe('ecartLigne', () => {
  it('renvoie null tant que la ligne n’est pas comptée', () => {
    expect(ecartLigne({ quantite_theorique: 10, quantite_comptee: null })).toBeNull()
    expect(ecartLigne({ quantite_theorique: 10 })).toBeNull()
  })

  it('calcule comptée − théorique une fois comptée', () => {
    expect(ecartLigne({ quantite_theorique: 10, quantite_comptee: 8 })).toBe(-2)
    expect(ecartLigne({ quantite_theorique: 10, quantite_comptee: 10 })).toBe(0)
    expect(ecartLigne({ quantite_theorique: 10, quantite_comptee: 12 })).toBe(2)
  })
})

describe('grouperLignesParEcart', () => {
  it('répartit les lignes en trois seaux (non comptées / conformes / écarts)', () => {
    const lignes = [
      { id: 1, quantite_theorique: 5, quantite_comptee: null },
      { id: 2, quantite_theorique: 5, quantite_comptee: 5 },
      { id: 3, quantite_theorique: 5, quantite_comptee: 3 },
      { id: 4, quantite_theorique: 5, quantite_comptee: 7 },
    ]
    const { nonComptees, conformes, ecarts } = grouperLignesParEcart(lignes)
    expect(nonComptees.map((l) => l.id)).toEqual([1])
    expect(conformes.map((l) => l.id)).toEqual([2])
    expect(ecarts.map((l) => l.id)).toEqual([3, 4])
    expect(ecarts.find((l) => l.id === 3).ecart).toBe(-2)
    expect(ecarts.find((l) => l.id === 4).ecart).toBe(2)
  })

  it('ne mute pas la liste d’entrée et tolère undefined/non-tableau', () => {
    const lignes = [{ id: 1, quantite_theorique: 1, quantite_comptee: 1 }]
    const copy = [...lignes]
    grouperLignesParEcart(lignes)
    expect(lignes).toEqual(copy)
    expect(grouperLignesParEcart(undefined)).toEqual({ nonComptees: [], conformes: [], ecarts: [] })
    expect(grouperLignesParEcart(null)).toEqual({ nonComptees: [], conformes: [], ecarts: [] })
    expect(grouperLignesParEcart('nope')).toEqual({ nonComptees: [], conformes: [], ecarts: [] })
  })
})

describe('progressionComptage', () => {
  it('calcule comptées/total/pct', () => {
    const lignes = [
      { quantite_comptee: 1 }, { quantite_comptee: null }, { quantite_comptee: 3 }, { quantite_comptee: null },
    ]
    expect(progressionComptage(lignes)).toEqual({ comptees: 2, total: 4, pct: 50 })
  })

  it('renvoie pct=0 sur une liste vide/absente (jamais NaN)', () => {
    expect(progressionComptage([])).toEqual({ comptees: 0, total: 0, pct: 0 })
    expect(progressionComptage(undefined)).toEqual({ comptees: 0, total: 0, pct: 0 })
  })
})

describe('actionsDisponiblesTransfert', () => {
  it('mirror les gardes 409 backend selon le statut', () => {
    expect(actionsDisponiblesTransfert('demande')).toEqual(['approuver', 'refuser'])
    expect(actionsDisponiblesTransfert('approuve')).toEqual(['executer'])
    expect(actionsDisponiblesTransfert('refuse')).toEqual([])
    expect(actionsDisponiblesTransfert('execute')).toEqual([])
    expect(actionsDisponiblesTransfert(undefined)).toEqual([])
  })
})

describe('aPreuveLivraison / podComplete', () => {
  it('détecte la présence d’une preuve et sa complétude', () => {
    expect(aPreuveLivraison({})).toBe(false)
    expect(aPreuveLivraison({ preuve: { id: 1 } })).toBe(true)
    expect(aPreuveLivraison({ preuve_id: 1 })).toBe(true)
    expect(podComplete({ signature_data: null, signataire_nom: 'X' })).toBe(false)
    expect(podComplete({ signature_data: 'data:image/png;base64,x', signataire_nom: '' })).toBe(false)
    expect(podComplete({ signature_data: 'data:image/png;base64,x', signataire_nom: 'M. Alami' })).toBe(true)
  })
})

// ── Smoke render des écrans (API mockées, hors réseau) ──

vi.mock('../../api/installationsApi', () => ({
  default: {
    getLivraisons: vi.fn(() => Promise.resolve({ data: [] })),
    getTransporteurs: vi.fn(() => Promise.resolve({ data: [] })),
    getTourneeLivraison: vi.fn(() => Promise.resolve({ data: null })),
    getSessionsComptage: vi.fn(() => Promise.resolve({ data: [] })),
    getDemandesTransfert: vi.fn(() => Promise.resolve({ data: [] })),
    createSessionComptage: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: {
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    getEmplacements: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import LivraisonsPlanningScreen from './LivraisonsPlanningScreen'
import ComptageCyclesScreen from './ComptageCyclesScreen'
import TransfertsScreen from './TransfertsScreen'

beforeEach(() => { vi.clearAllMocks() })

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('écrans Logistique (smoke)', () => {
  it('LivraisonsPlanningScreen se rend sans planter (aucune livraison)', async () => {
    withProviders(<LivraisonsPlanningScreen />)
    await waitFor(() => screen.getByText('Planning des livraisons'))
    await waitFor(() => screen.getByText('Aucune livraison planifiée'))
  })

  it('ComptageCyclesScreen se rend sans planter (aucune session)', async () => {
    withProviders(<ComptageCyclesScreen />)
    await waitFor(() => screen.getByText('Comptages cycliques'))
    await waitFor(() => screen.getByText('Aucune session'))
  })

  it('TransfertsScreen se rend sans planter (aucune demande)', async () => {
    withProviders(<TransfertsScreen />)
    await waitFor(() => screen.getByText('Demandes de transfert'))
    await waitFor(() => screen.getByText('Aucune demande de transfert'))
  })
})
