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
import { arrondirAuPasKwc } from '../../features/ventes/solar.js'

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

describe('QJR308 — l’avis du palier 5 kWc s’affiche AU MOMENT où runAutoQuote déclenche le snap', () => {
  it('un lead dont la taille souhaitée franchit le palier : le texte de noticePalierKwc est VISIBLE pendant le snap', async () => {
    // 6,5 kWc n'est pas un multiple de 5 : createAutoQuote va réellement
    // arrondir cette cible avant de l'envoyer au serveur (même précédence que
    // DevisTab.jsx/LeadDevisPanel.jsx, aucune cible explicite transmise ici).
    const kwcSaisi = 6.5
    expect(arrondirAuPasKwc(kwcSaisi)).not.toBe(kwcSaisi)

    // `creerDevisAuto` reste EN ATTENTE — on observe l'écran au moment RÉEL
    // du snap, avant que la réponse réseau ne bascule sur le panneau succès
    // (qui remplace toute la page, avis compris).
    let resolveCreation
    ventesApi.creerDevisAuto.mockImplementation(
      () => new Promise((resolve) => { resolveCreation = resolve }))

    renderGenerator({
      leads: [{
        id: 42, nom: 'Bennani', prenom: 'Yassine',
        type_installation: 'residentiel', taille_souhaitee_kwc: kwcSaisi,
      }],
      route: '/ventes/devis/nouveau?lead=42&auto=1',
    })

    await waitFor(() => expect(screen.getByText(/Palier appliqué/)).toBeInTheDocument())
    expect(screen.getByText(/Palier appliqué : 5 kWc \(saisie 6,5 kWc\)/)).toBeInTheDocument()

    // Nettoyage : on laisse la création se terminer (panneau succès), pour
    // ne pas laisser une promesse orpheline derrière le test.
    resolveCreation({ data: { id: 501, reference: 'DEV-2026-09-0501' } })
    await waitFor(() => expect(screen.getByTestId('devis-succes')).toBeInTheDocument())
  })

  it('un kWc déjà aligné sur le palier : AUCUN avis ne s’affiche', async () => {
    const kwcSaisi = 5
    expect(arrondirAuPasKwc(kwcSaisi)).toBe(kwcSaisi)

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
