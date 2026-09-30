// ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — quand l'étude horaire SERVEUR a
// répondu, la carte ROI de l'écran affiche le payback du MOTEUR (cashflow 25
// ans QX39, `paybackMoteurHoraire`), plus `coût ÷ économie` ; un cumul qui ne
// croise jamais zéro s'affiche « Non rentabilisé sur 25 ans ».
//
// L'écran RÉEL est rendu en édition (`?edit=`), l'aperçu horaire mocké ; la
// valeur lue est l'ancre QA-FIGURES `data-figure="payback_ans"` — aucune
// lecture de source (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPaybackMoteur.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { paybackMoteurHoraire } from '../../features/ventes/solar'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.reject(new Error('sans lead'))),
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
    getDevisById: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(),
    postEtudeHorairePreview: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}
// 8 × 1 200 HT à 10 % + 9 000 HT à 20 % = 10 560 + 10 800 = 21 360 TTC ;
// l'onduleur (10 800 TTC) est la provision de remplacement de l'option.
const TOTAL_SANS = 21360
const ONDULEUR_TTC = 10800

const ANNUEL = {
  production_kwh: 6813, consommation_kwh: 6120,
  taux_autoconso_sans: 0.45, taux_autoconso_avec: 0.45,
  couverture_sans: 0.5, couverture_avec: 0.5,
}

function devisRouvert() {
  return {
    data: {
      id: 336, reference: 'DEV-202609-0201', statut: 'brouillon', lead: null, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  }
}

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Commercial', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderEdition() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=336']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

async function paybackAffiche(container) {
  let valeur = null
  await waitFor(() => {
    const ancre = container.querySelector(
      '[data-figure="payback_ans"][data-figure-option="sans"]')
    valeur = ancre?.getAttribute('data-figure-value') ?? null
    expect(valeur).not.toBeNull()
    // L'aperçu serveur a répondu : la carte « Taux de couverture » n'existe
    // que dans cette branche.
    expect(container.querySelector('[data-figure="couverture_pct"]')).not.toBeNull()
  }, { timeout: 5000 })
  return valeur
}

beforeEach(() => {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
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
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR] })
  ventesApi.getDevisById.mockResolvedValue(devisRouvert())
})

function repondreAvecEconomie(eco) {
  ventesApi.postEtudeHorairePreview.mockResolvedValue({
    data: {
      etude: {
        annuel: { ...ANNUEL, economie_sans_mad: eco, economie_avec_mad: eco },
        mois: [],
      },
      dimensionnement: null,
      consommation: { source: 'factures_mensuelles_reelles' },
      avertissements: [],
    },
  })
}

describe('ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — carte ROI de la branche serveur', () => {
  it('affiche le payback du MOTEUR (cashflow 25 ans), jamais coût ÷ économie', async () => {
    repondreAvecEconomie(4580)
    const { container } = renderEdition()
    const attendu = paybackMoteurHoraire(TOTAL_SANS, 4580, {
      annuel: { ...ANNUEL, economie_sans_mad: 4580, economie_avec_mad: 4580 },
      inverterReplaceCost: ONDULEUR_TTC,
    })
    expect(attendu.jamaisRembourse).toBe(false)
    // Témoin : la division naïve donnerait un AUTRE chiffre.
    expect(attendu.paybackYears).not.toBe(Math.round((TOTAL_SANS / 4580) * 100) / 100)
    expect(await paybackAffiche(container)).toBe(`${attendu.paybackYears} ans`)
    expect(ventesApi.postEtudeHorairePreview).toHaveBeenCalled()
  })

  it('un cumul qui ne croise jamais zéro : « Non rentabilisé sur 25 ans », jamais « 25 ans »', async () => {
    repondreAvecEconomie(300)
    expect(paybackMoteurHoraire(TOTAL_SANS, 300, {
      inverterReplaceCost: ONDULEUR_TTC }).jamaisRembourse).toBe(true)
    const { container } = renderEdition()
    expect(await paybackAffiche(container)).toBe('Non rentabilisé sur 25 ans')
  })
})
