import { render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { vi } from 'vitest'

import authReducer from '../features/auth/store/authSlice'
import ventesReducer from '../features/ventes/store/ventesSlice'
import DevisGenerator from '../pages/ventes/DevisGenerator'
import { estimerMois } from '../features/ventes/solar'
import { exempleContrat } from './fixtures/contractSamples'

/* EDC (gardes CI) — banc PARTAGÉ des tests du générateur en Édition complète.

   Fixtures, store, rendu, `beforeEach` et ouverture d'écran que les tests
   EDC2/4/5/6/7/9 recopiaient les uns des autres (et des vieux tests du
   générateur) : `scripts/check_duplicats_litteraux.py` (ACAL345) refuse tout
   bloc de ≥ 6 lignes significatives copié dans deux fichiers. Chaque test
   garde SES `vi.mock(...)` (hissés, chemins relatifs à lui) — leurs fabriques
   viennent de `./mocksApiDevis.js`, le seul module sans import d'API. */

export const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
export const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}

// Devis n° 42 : un panneau (8) et un onduleur (1), brouillon modifiable.
export const DEVIS_EDITION = {
  id: 42, reference: 'DEV-202610-0042', statut: 'brouillon', modifiable: true,
  raison_non_modifiable: '', revision_possible: false, is_active: true,
  lead: null, client: 9, mode_installation: 'residentiel', taux_tva: '20.00',
  remise_globale: '0', updated_at: '2026-10-09T08:00:00Z',
  etude_params: { scenario: 'Sans batterie' },
  lignes: [
    { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
      prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
      type_ligne: 'produit', optionnelle: false },
    { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
      prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
      type_ligne: 'produit', optionnelle: false },
  ],
}

// Variante à UNE ligne libre « Installation » (aucun produit du catalogue).
export const DEVIS_INSTALLATION = {
  ...DEVIS_EDITION,
  lignes: [
    { id: 1, produit: null, designation: 'Installation', quantite: '1',
      prix_unitaire: '1000.00', taux_tva: '20.00', ordre: 0,
      type_ligne: 'produit', optionnelle: false },
  ],
}

/** Devis n° 42 brouillon sur le lead 7 (exemple COMMITTÉ du contrat PACT10). */
export function devisBrouillonLead7() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...DEVIS_EDITION, ...contrat, id: 42, lead: 7, client: 9, lead_nom: 'Karim Brouillon',
      updated_at: '2026-09-30T10:00:00Z',
      etude_params: { scenario: 'Sans batterie', factures_mensuelles_reelles: estimerMois(2000, 2000) },
    },
  }
}

/** Store minimal du générateur : `auth` (rôle au choix) + `ventes`. */
export function makeStoreGenerateur({
  role = 'normal', roleNom = 'Commercial', permissions = [],
} = {}) {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom: roleNom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

const rien = () => {}

/** Générateur embarqué sur le devis n° 42 ; `props` surcharge tout (`editId`…). */
export function renderGenerateurEdition(props = {}, { store = makeStoreGenerateur() } = {}) {
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/crm/leads/7']}>
        <DevisGenerator embedded editId={42} onDone={rien} onCancel={rien} {...props} />
      </MemoryRouter>
    </Provider>,
  )
}

/** Générateur PLEINE PAGE (`/ventes/devis/nouveau?edit=42` par défaut). */
export function renderGenerateurPage(route = '/ventes/devis/nouveau?edit=42') {
  return render(
    <Provider store={makeStoreGenerateur()}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

/** Générateur nu (route par défaut) pour un rôle / des permissions donnés. */
export function renderGenerateurRole({ role_nom: roleNom, permissions }) {
  return render(
    <Provider store={makeStoreGenerateur({ roleNom, permissions })}>
      <MemoryRouter>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

/** `window.matchMedia` factice ; `reduit` = « mouvement réduit » demandé. */
export const matchMediaDe = (reduit = false) => vi.fn().mockImplementation((q) => ({
  matches: reduit && q.includes('prefers-reduced-motion: reduce'), media: q, onchange: null,
  addListener: vi.fn(), removeListener: vi.fn(),
  addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
}))

/** Pose le stub seulement si jsdom n'en fournit pas. */
export function stubMatchMedia() {
  if (!window.matchMedia) window.matchMedia = matchMediaDe(false)
}

/** Corps commun des `beforeEach` : remise à zéro + réponses des API mockées. */
export function preparerApisGenerateur({
  stockApi, ventesApi, produits = [PANNEAU, ONDULEUR], devis = DEVIS_EDITION,
}) {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  stubMatchMedia()
  stockApi.getProduits.mockResolvedValue({ data: produits })
  ventesApi.getDevisById.mockResolvedValue({ data: devis })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: { updated_at: '2026-10-09T09:30:00Z' } })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
}

/** Attend l'éditeur monté (bouton « Enregistrer les modifications » + une désignation). */
export async function attendreEdition({ designation = PANNEAU.nom } = {}) {
  await screen.findByRole('button', { name: /Enregistrer les modifications/ })
  if (designation) await screen.findByDisplayValue(designation)
}

/** Ouvre l'édition et attend la fenêtre de référence QJR581 (1,5 s). */
export async function ouvrirEditionEtAttendreReference(options) {
  await attendreEdition(options)
  await new Promise((r) => setTimeout(r, 1700))
}
