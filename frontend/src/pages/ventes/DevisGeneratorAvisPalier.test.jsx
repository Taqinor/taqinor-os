// QJR602 (D-QJR5-13, 30/09/2026) — plus aucun palier n'est appliqué à une
// taille explicite : l'avis ci-dessous ne s'affiche plus jamais.
//
// QJR308 — L'avis du palier 5 kWc de `noticePalierKwc` (autoQuote.js) était
// bien branché aux DEUX points de PRÉ-navigation (DevisTab.jsx,
// LeadDevisPanel.jsx) mais PAS au troisième point d'entrée de
// `createAutoQuote` : `runAutoQuote` dans le générateur lui-même
// (`?lead=&auto=1` / prop `autoProp`). Le vendeur qui arrive par CE chemin
// voyait sa puissance snappée au palier de 5 kWc sans jamais lire pourquoi.
//
// Correctif : `runAutoQuote` calcule l'avis (MÊME fonction partagée, aucune
// seconde formulation) au moment RÉEL où le snap a lieu — juste avant l'appel
// réseau `createAutoQuote` — et le pose dans `warnings`, qui alimente le bloc
// d'avertissements non bloquants déjà rendu par l'écran.
//
// QJR239 (garde `scripts/check_tests_source_regex.py`) interdit tout NOUVEAU
// test de la famille DevisGenerator*/solar*/autoQuote* qui lit le SOURCE via
// `readFileSync` puis asserte par regex : ce fichier MONTE réellement
// DevisGenerator (patron de DevisGeneratorScenarioDefaut.test.jsx /
// DevisGeneratorTarif.test.jsx / DevisGeneratorRename.test.jsx) et exécute le
// vrai code — le résidentiel est choisi car sa branche `createAutoQuote` part
// directement au serveur (`ventesApi.creerDevisAuto`) sans exiger un
// catalogue de produits réaliste.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorAvisPalier.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
// Module PUR (aucun JSX, aucune dépendance React) : rejoué avec la VRAIE
// fonction, jamais une réplique qui pourrait diverger.
// CIQ128 — l'arrondi au palier de 5 kWc a quitté solar.js : le test le
// rejoue ici pour son seul besoin (une taille HORS palier).
const auPalier5 = (k) => Math.max(5, Math.round(k / 5) * 5)

// APIs mockées (aucun appel réseau réel au montage).
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
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    // QJR308 — chemin résidentiel de `createAutoQuote` : composition ET
    // création côté serveur, l'écran ne transmet que la puissance cible.
    creerDevisAuto: vi.fn(() => Promise.resolve({ data: { id: 501, reference: 'DEV-2026-09-0501' } })),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

// Catalogue minimal : l'effet « arrivée depuis le lead » (?lead=…) n'applique
// le lead qu'une fois les produits chargés (résidentiel n'en a pas besoin
// pour composer — le serveur compose — mais l'effet attend `produits.length`).
const PRODUITS = [
  { id: 10, nom: 'Panneau Solaire 710W', prix_vente: 1200, tva: 20, is_archived: false },
]

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderGenerator({ leads = [], produits = PRODUITS, route } = {}) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: leads })
  stockApi.getProduits.mockResolvedValue({ data: produits })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[route]}>
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

describe('QJR308 → QJR602 — runAutoQuote : plus aucun avis de palier, la taille explicite est souveraine', () => {
  it('QJR602 — un lead à 6,5 kWc : AUCUN avis, la taille part TELLE QUELLE (10 panneaux de 710 W)', async () => {
    // D-QJR5-13 (fondateur 30/09/2026) : une taille explicite n'est plus
    // ramenée au palier de 5 kWc — il n'y a donc plus de snap à annoncer.
    const kwcSaisi = 6.5
    expect(auPalier5(kwcSaisi)).not.toBe(kwcSaisi)
    ventesApi.creerDevisAuto.mockImplementation(
      () => Promise.resolve({ data: { id: 501, reference: 'DEV-2026-09-0501' } }))

    renderGenerator({
      leads: [{
        id: 42, nom: 'Bennani', prenom: 'Yassine',
        type_installation: 'residentiel', taille_souhaitee_kwc: kwcSaisi,
      }],
      route: '/ventes/devis/nouveau?lead=42&auto=1',
    })

    await waitFor(() => expect(screen.getByTestId('devis-succes')).toBeInTheDocument())
    expect(screen.queryByText(/Palier appliqué/)).not.toBeInTheDocument()
    expect(ventesApi.creerDevisAuto).toHaveBeenCalledTimes(1)
    expect(ventesApi.creerDevisAuto.mock.calls[0][0].target_kwc).toBeCloseTo(7.1, 9)
  })

  it('un kWc déjà aligné sur le palier : AUCUN avis ne s’affiche', async () => {
    const kwcSaisi = 5
    expect(auPalier5(kwcSaisi)).toBe(kwcSaisi)

    // `vi.clearAllMocks()` efface les APPELS, pas les implémentations : sans
    // ceci, la promesse EN ATTENTE posée par le test précédent resterait la
    // mock active et `devis-succes` n'arriverait jamais.
    ventesApi.creerDevisAuto.mockImplementation(
      () => Promise.resolve({ data: { id: 502, reference: 'DEV-2026-09-0502' } }))

    renderGenerator({
      leads: [{
        id: 43, nom: 'Alaoui', prenom: 'Salma',
        type_installation: 'residentiel', taille_souhaitee_kwc: kwcSaisi,
      }],
      route: '/ventes/devis/nouveau?lead=43&auto=1',
    })

    // Preuve que le devis auto a bien été déclenché et abouti (sinon
    // l'absence de texte ne prouverait rien).
    await waitFor(() => expect(screen.getByTestId('devis-succes')).toBeInTheDocument())
    expect(screen.queryByText(/Palier appliqué/)).not.toBeInTheDocument()
  })
})
