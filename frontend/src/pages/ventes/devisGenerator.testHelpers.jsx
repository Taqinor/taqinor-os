/* Harnais partagé des tests DevisGenerator (ENF19) : store Directeur + rendu pleine page. */
import { vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

export function makeDevisStore(role = 'normal', role_nom = 'Directeur', permissions = []) {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role, role_nom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

export const makeStoreDirecteur = () => makeDevisStore('normal', 'Directeur')

// Catalogue / lead de référence des tests d'édition du générateur.
export const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
export const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}
export const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'SansStatut', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

/** Polyfills jsdom requis par l'écran (scroll, matchMedia, ResizeObserver). */
export function installPolyfillsDevis() {
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
}

/** Pose clients/leads/produits sur les mocks api puis rend le générateur (à `route` si donnée). */
export function renderGeneratorPage(DevisGenerator, {
  crmApi, stockApi, leads = [], produits = [], route, store = makeStoreDirecteur(),
}) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: leads })
  stockApi.getProduits.mockResolvedValue({ data: produits })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={route ? [route] : undefined}>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

/** Ligne produit d'un devis servi par l'API (type produit, non optionnelle). */
export function ligneProduit({ id, produit, designation, quantite, prix_unitaire, taux_tva, ordre }) {
  return {
    id, produit: produit.id, designation: designation ?? produit.nom, quantite,
    prix_unitaire, taux_tva, ordre, type_ligne: 'produit', optionnelle: false,
  }
}

/** Devis industriel de référence : 20 panneaux à 1000 (TVA 10) + 1 onduleur à 10000 (TVA 20). */
export function lignesPanneauxOnduleur(panneau, onduleur) {
  return [
    ligneProduit({ id: 1, produit: panneau, quantite: '20', prix_unitaire: '1000.00', taux_tva: '10.00', ordre: 0 }),
    ligneProduit({ id: 2, produit: onduleur, quantite: '1', prix_unitaire: '10000.00', taux_tva: '20.00', ordre: 1 }),
  ]
}

/** Écritures du devis (patch, lignes, étude) qui réussissent sans rien renvoyer. */
export function mockEcrituresDevisOk(ventesApi) {
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
}

/** Rend le générateur à `route` ; toute autre route affiche `apres` (sortie de l'écran). */
export function renderRouteSortie(DevisGenerator, store, route, apres = 'APRES') {
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>{apres}</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

export const renderEditionPage = (DevisGenerator, store, editId, apres) =>
  renderRouteSortie(DevisGenerator, store, `/ventes/devis/nouveau?edit=${editId}`, apres)

/** Devis résidentiel rouvert (8 panneaux + 1 onduleur) à partir d'une variante du contrat de modifiabilité. */
export function devisResidentielRouvert(variante, { dateEnvoi = '2026-09-28T10:00:00Z', ...extra } = {}) {
  return {
    data: {
      ...exempleContrat('ventes', 'devis_modifiabilite', variante),
      ...extra,
      lead: LEAD.id, client: 9,
      ...(dateEnvoi ? { date_envoi: dateEnvoi } : {}),
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: [
        ligneProduit({ id: 1, produit: PANNEAU, quantite: '8', prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0 }),
        ligneProduit({ id: 2, produit: ONDULEUR, quantite: '1', prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1 }),
      ],
    },
  }
}

/**
 * Banc d'édition (?edit=) du générateur : store, rendu, devis rouvert et beforeEach
 * standard (polyfills, catalogue PANNEAU/ONDULEUR, lead, écritures acceptées).
 */
export function bancEdition({
  DevisGenerator, stockApi, crmApi, ventesApi, parametresApi, role = 'normal', roleNom = 'Commercial',
  apres = 'APRES-ENREGISTREMENT', dateEnvoi, produits = [PANNEAU, ONDULEUR], lead = LEAD, devis, profil,
}) {
  const makeStore = () => makeDevisStore(role, roleNom)
  declarerBeforeEachDevis({
    stockApi, crmApi, ventesApi, parametresApi, produits, lead, devis, profil, ecritures: true, localStorage: true,
  })
  return {
    makeStore,
    renderEdition: (id) => renderEditionPage(DevisGenerator, makeStore(), id, apres),
    devisRouvert: (variante) => devisResidentielRouvert(variante, dateEnvoi === undefined ? {} : { dateEnvoi }),
  }
}

/** Brouillon enregistré sans ligne (le panneau Surcharges n'existe que sur un devis avec id). */
export const DEVIS_VIDE_ROUVERT = {
  id: 7, reference: 'DEV-2026-09-0007', statut: 'brouillon', modifiable: true,
  raison_non_modifiable: '', revision_possible: false, is_active: true,
  mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
  lignes: [],
}

/** Catalogue de la composition serveur (onduleur réseau, panneau 710 W, structures, pose, transport). */
export const PRODUITS_COMPOSITION = [
  { id: 1, nom: 'Onduleur réseau Huawei 10kW Triphasé', prix_vente: 16666.67, tva: 20, is_archived: false },
  { id: 2, nom: 'Panneau Canadien Solar 710W', prix_vente: 1166.67, tva: 10, is_archived: false, marque: 'Canadian Solar' },
  { id: 3, nom: 'Structures acier', prix_vente: 416.67, tva: 20, is_archived: false },
  { id: 4, nom: 'Socles', prix_vente: 66.67, tva: 20, is_archived: false },
  { id: 5, nom: 'Accessoires', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 6, nom: 'Tableau De Protection AC/DC', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 7, nom: 'Installation', prix_vente: 4000, tva: 20, is_archived: false },
  { id: 8, nom: 'Transport', prix_vente: 833.33, tva: 20, is_archived: false },
]

/** Deux lignes du devis résidentiel de référence : 8 panneaux à 1200 + 1 onduleur à 9000. */
export function lignesResidentielles(panneau, onduleur) {
  return [
    ligneProduit({ id: 1, produit: panneau, quantite: '8', prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0 }),
    ligneProduit({ id: 2, produit: onduleur, quantite: '1', prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1 }),
  ]
}

// Stockage indisponible (mode privé) : on le note et on continue, le test n'en dépend pas.
const stockage = { indisponible: false }
function viderStockageNavigateur() {
  try { window.localStorage.clear() } catch { stockage.indisponible = true }
}

/**
 * beforeEach standard du générateur : mocks remis à zéro, polyfills, puis les réponses
 * demandées (catalogue, lead, devis, profil, écritures acceptées).
 */
export function declarerBeforeEachDevis({
  stockApi, crmApi, ventesApi, parametresApi, produits, lead, devis, profil = false,
  ecritures = false, localStorage: viderStockage = false, extra,
}) {
  beforeEach(() => {
    vi.clearAllMocks()
    if (viderStockage) {
      viderStockageNavigateur()
    }
    installPolyfillsDevis()
    if (produits) stockApi.getProduits.mockResolvedValue({ data: produits })
    if (lead) crmApi.getLead.mockResolvedValue({ data: lead })
    if (profil) parametresApi.getProfile.mockResolvedValue({ data: profil === true ? {} : profil })
    if (devis) ventesApi.getDevisById.mockResolvedValue(devis())
    if (ecritures) mockEcrituresDevisOk(ventesApi)
    if (extra) extra()
  })
}

// Catalogue et devis de la famille « industriel / commercial » (panneaux 550 W, onduleur 10 kW).
export const PANNEAU_IND = { id: 201, nom: 'Panneau Mono 550W', prix_vente: 1000, tva: 10, is_archived: false }
export const ONDULEUR_IND = { id: 202, nom: 'Onduleur réseau 10kW Triphasé', prix_vente: 10000, tva: 20, is_archived: false }

/** Brouillon industriel/commercial rouvert : 20 panneaux + 1 onduleur, client 9. */
export function devisIndustrielBrouillon({ id, mode, etude_params, ...extra }) {
  return {
    data: {
      id, reference: `DEV-202609-0${id}`, statut: 'brouillon', modifiable: true,
      raison_non_modifiable: '', revision_possible: false, is_active: true, client: 9,
      mode_installation: mode, taux_tva: '20.00', remise_globale: '0', ...extra,
      etude_params, lignes: lignesPanneauxOnduleur(PANNEAU_IND, ONDULEUR_IND),
    },
  }
}

/** Banc « brouillon vide rouvert » (?edit=7) : rendu + beforeEach, sans catalogue. */
export function bancDevisVide({ DevisGenerator, crmApi, stockApi, ventesApi, role = 'admin', roleNom = 'Directeur' }) {
  declarerBeforeEachDevis({ stockApi, crmApi, ventesApi })
  return {
    renderGenerator() {
      ventesApi.getDevisById.mockResolvedValue({ data: DEVIS_VIDE_ROUVERT })
      return renderGeneratorPage(DevisGenerator, {
        crmApi, stockApi, store: makeDevisStore(role, roleNom), route: '/ventes/devis/nouveau?edit=7',
      })
    },
  }
}

/** Banc « nouveau devis » : store Directeur (stock_creer), rendu pleine page et beforeEach. */
export function bancCreation({ DevisGenerator, crmApi, stockApi, produits }) {
  declarerBeforeEachDevis({ stockApi, crmApi })
  const makeStore = () => makeDevisStore('normal', 'Directeur', ['stock_creer'])
  return {
    makeStore,
    renderGenerator: () => renderGeneratorPage(DevisGenerator, { crmApi, stockApi, produits, store: makeStore() }),
  }
}

/** Banc industriel/commercial : catalogue 550 W / 10 kW, pas de lead, profil société posé. */
export function bancIndustriel(options) {
  return bancEdition({ lead: null, produits: [PANNEAU_IND, ONDULEUR_IND], profil: true, ...options })
}
