// F1 (revue adversariale 26/08/2026, BLOQUANT) — la première version du
// bouton « Recalculer le dimensionnement » reverrouillait TOUJOURS
// `nbPanneauxTouched.current = true` au lieu de restaurer sa valeur d'AVANT
// le clic. Conséquence prouvée par le reviewer : en CRÉATION, où ce
// garde-fou part FAUX (ouvert), un premier clic sur Recalculer le fermait en
// PERMANENCE pour le reste de la session — le redimensionnement facture→
// panneaux en direct (règle N3, `syncBillEstimator`) mourait silencieusement,
// et une « Auto-remplir » ultérieure retombait sur l'ancien compte de
// panneaux (via `resolveKwcAvec()`) pendant que l'écran continuait
// d'afficher un optimum différent.
//
// Ce fichier est un test COMPORTEMENTAL (rendu React réel, vitest — même
// patron que DevisGeneratorScenarioDefaut.test.jsx/
// DevisGeneratorMarquesPinning.test.jsx) : c'est le SEUL type de test qui
// aurait intercepté F1. Les tests source-pattern de
// DevisGeneratorRecalculerDimensionnement.test.mjs (node --test) vérifient
// la PRÉSENCE du bon code (capture + restauration), mais un test purement
// textuel ne peut pas prouver que le comportement RUNTIME est correct —
// celui-ci le prouve en observant l'écran après un vrai clic.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
// `composerDevis` DÉLIBÉRÉMENT absent de ce mock (même patron que
// DevisGeneratorMarquesPinning.test.jsx) : la branche résidentielle de
// `handleAutoFill` l'appelle sans le trouver (TypeError), retombe SANS
// EXCEPTION sur `composeLocalement()` (repli local, synchrone) — comme un
// vrai réseau indisponible. Ce choix rend le test déterministe (aucune
// promesse réseau à attendre) tout en exerçant EXACTEMENT le chemin de code
// que F1/F2 concernent (la fenêtre de déverrouillage autour de cet appel).
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(() => Promise.resolve({ data: { source: 'standard' } })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'

// Catalogue solaire complet (même fixture que DevisGeneratorMarquesPinning.
// test.jsx) : assez de rôles réels (panneau, onduleur, structures, socles,
// accessoires, tableau, installation, transport) pour que le balayage
// palier/payback (`computeAutoSizing`/`optimalKwcByPayback`) chiffre de
// VRAIS paliers, pas des lignes placeholder à 0 MAD.
const PRODUITS = [
  { id: 1, nom: 'Onduleur réseau Huawei 10kW Triphasé', prix_vente: 16666.67, tva: 20, is_archived: false },
  { id: 2, nom: 'Panneau Canadien Solar 710W', prix_vente: 1166.67, tva: 10, is_archived: false, marque: 'Canadian Solar' },
  { id: 3, nom: 'Structures acier', prix_vente: 416.67, tva: 20, is_archived: false },
  { id: 4, nom: 'Socles', prix_vente: 66.67, tva: 20, is_archived: false },
  { id: 5, nom: 'Accessoires', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 6, nom: 'Tableau De Protection AC/DC', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 7, nom: 'Installation', prix_vente: 4000, tva: 20, is_archived: false },
  { id: 8, nom: 'Transport', prix_vente: 833.33, tva: 20, is_archived: false },
]

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: ['stock_creer'],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderGenerator() {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const nbPanneauxField = () => screen.getByLabelText(/Nombre de panneaux/)
const hiverField = () => screen.getByLabelText(/Facture Hiver/)
const recalcButton = () => screen.getByRole('button', { name: /Recalculer le dimensionnement/i })

describe('F1 — le garde-fou nbPanneauxTouched est restauré à sa valeur EXACTE d\'avant le clic (jamais figé à true)', () => {
  it('création (garde-fou OUVERT avant le clic) : le redimensionnement en direct facture→panneaux SURVIT à un clic sur Recalculer', async () => {
    renderGenerator()
    // Le catalogue est chargé (table par défaut du simulateur) avant toute
    // interaction — même preuve de montage que les tests voisins.
    await screen.findByDisplayValue('Installation')

    // Garde-fou encore OUVERT (rien n'a jamais touché nbPanneaux à la main) :
    // taper une facture le redimensionne déjà tout seul (comportement N3
    // existant, pas ce qui est sous test ici).
    fireEvent.change(hiverField(), { target: { value: '1200' } })
    await waitFor(() => expect(parseFloat(nbPanneauxField().value) || 0).toBeGreaterThan(0))
    const avantClic = nbPanneauxField().value

    fireEvent.click(recalcButton())
    // Preuve que la composition déclenchée par le clic est allée à son terme
    // (repli composeLocalement synchrone — voir le mock ventesApi ci-dessus) :
    // l'onduleur réseau du stock apparaît dans les lignes.
    await screen.findByDisplayValue(/Onduleur réseau Huawei/)
    const apresClic = nbPanneauxField().value
    expect(parseFloat(apresClic) || 0).toBeGreaterThan(0)
    // Même facture qu'avant le clic (rien n'a changé entre-temps) : le
    // recalcul rejoue le MÊME balayage payback, donc retombe sur le MÊME
    // compte — confirme que le clic ne fabrique pas un chiffre différent
    // sans raison.
    expect(apresClic).toBe(avantClic)

    // LE CŒUR DE F1 — une facture TRÈS différente, tapée APRÈS le clic, doit
    // ENCORE redimensionner tout de suite : si le garde-fou avait été
    // reverrouillé à `true` en dur (l'ancienne régression), cette frappe
    // resterait silencieuse et `apresRecalculConstitue` == `apresClic`.
    fireEvent.change(hiverField(), { target: { value: '3000' } })
    await waitFor(() => {
      const v = nbPanneauxField().value
      expect(v).not.toBe(apresClic)
      expect(parseFloat(v) || 0).toBeGreaterThan(0)
    })
  })

  it('un nombre de panneaux tapé À LA MAIN avant le clic (garde-fou FERMÉ) reste verrouillé APRÈS le clic — la frappe suivante sur la facture reste silencieuse', async () => {
    renderGenerator()
    await screen.findByDisplayValue('Installation')

    fireEvent.change(hiverField(), { target: { value: '1200' } })
    await waitFor(() => expect(parseFloat(nbPanneauxField().value) || 0).toBeGreaterThan(0))

    // Ferme le garde-fou EXPLICITEMENT, comme un commercial qui ajuste le
    // compte à la main (onNbPanneauxChange).
    fireEvent.change(nbPanneauxField(), { target: { value: '99' } })
    await waitFor(() => expect(nbPanneauxField().value).toBe('99'))

    // Le clic recalcule quand même une fois (consentement explicite du clic
    // — remplace même une valeur manuelle), MAIS doit reverrouiller le
    // garde-fou à ce qu'il était AVANT ce clic (fermé), pas à `true` en dur
    // ni à `false` en dur.
    fireEvent.click(recalcButton())
    await screen.findByDisplayValue(/Onduleur réseau Huawei/)
    await waitFor(() => expect(nbPanneauxField().value).not.toBe('99'))
    const apresClic = nbPanneauxField().value

    // Une facture différente ne doit RIEN changer : le garde-fou était fermé
    // avant le clic, il doit le rester après (restauration EXACTE, pas un
    // `false` en dur qui rouvrirait le redimensionnement en direct par erreur).
    fireEvent.change(hiverField(), { target: { value: '3000' } })
    // Laisse le temps à un éventuel (mauvais) recalcul de se produire avant
    // de constater qu'il n'a PAS eu lieu.
    await waitFor(() => expect(hiverField().value).toBe('3000'))
    expect(nbPanneauxField().value).toBe(apresClic)
  })
})
