// SPL40 — harnais PARTAGÉ des goldens du générateur de devis (capture seule).
//
// Le groupe SPL (SPL40-SPL55) découpe DevisGenerator.jsx par déplacements
// purs. Ce harnais fige ce que l'écran RÉEL rend et envoie, sur le code actuel,
// pour qu'un déplacement qui change un octet du DOM ou d'une charge enregistrée
// soit rouge. Il ne contient AUCUN vi.mock : les vi.mock restent dans chaque
// fichier de test (hissés par vitest) ; ici, seulement le magasin, les
// fixtures, la normalisation et le sérialiseur des mock.calls.
//
// Règles (NE PAS FAIRE du groupe SPL) : normalise() ne réécrit QUE les jetons
// useId de React — tout ce qui irait plus loin masquerait une vraie dérive ; un
// golden rouge est un bug du déplacement, jamais une raison de régénérer.
import { createElement } from 'react'
import { vi } from 'vitest'
import { render, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/** Instant figé de toutes les captures (Date.now / new Date de l'écran). */
export const DATE_FIGEE = new Date('2026-10-05T10:00:00Z')

/** Le palier machine pilote l'affichage admin (registre brut, QJR574). */
export function makeStore(role = 'normal') {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 },
        role,
        role_nom: role === 'admin' ? 'Directeur' : 'Commercial',
        permissions: [],
        isAuthenticated: true,
        loading: false,
      },
    },
  })
}

/** Monte l'écran RÉEL sous un routeur mémoire, à l'URL donnée. */
export function monter(DevisGenerator, url, { role = 'normal' } = {}) {
  return render(
    createElement(Provider, { store: makeStore(role) },
      createElement(MemoryRouter, { initialEntries: [url] },
        createElement(Routes, null,
          createElement(Route, {
            path: '/ventes/devis/nouveau', element: createElement(DevisGenerator),
          }),
          createElement(Route, {
            path: '*', element: createElement('div', null, 'APRES-ENREGISTREMENT'),
          }),
        ),
      ),
    ),
  )
}

// ── Normalisation : UNIQUEMENT les jetons useId de React ──────────────────
// React 19 émet « «r1» » (19.0/19.1) ou « _r_1_ » (19.2) ; les anciennes
// versions « :r1: ». Chaque jeton distinct est renuméroté dans l'ordre
// d'apparition : la structure (qui pointe vers qui) reste figée.
const JETON_USE_ID = /«[rR][0-9a-zA-Z]*»|_[rR]_[0-9a-zA-Z]+_|:[rR][0-9a-zA-Z]+:/g

export function normalise(html) {
  const vus = new Map()
  return String(html).replace(JETON_USE_ID, (jeton) => {
    if (!vus.has(jeton)) vus.set(jeton, `«id${vus.size + 1}»`)
    return vus.get(jeton)
  })
}

/**
 * Attend que le DOM ne bouge plus : les aperçus serveur sont temporisés à
 * 500 ms (useApercuServeur) ; on exige ~900 ms sans aucun changement du DOM.
 */
export async function stabiliser(container, { pasMs = 150, calmeRequis = 6, maxPas = 80 } = {}) {
  let precedent = null
  let calme = 0
  for (let i = 0; i < maxPas; i += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, pasMs)) })
    const courant = container.innerHTML
    calme = courant === precedent ? calme + 1 : 0
    if (calme >= calmeRequis) return courant
    precedent = courant
  }
  throw new Error('Le DOM du générateur ne se stabilise pas (capture impossible).')
}

/** JSON stable des mock.calls des API d'écriture d'un scénario. */
export function serialiserAppels(api, noms) {
  const sortie = {}
  for (const nom of noms) {
    const fn = api[nom]
    sortie[nom] = fn && fn.mock ? fn.mock.calls : null
  }
  return `${JSON.stringify(sortie, null, 2)}\n`
}

// ── Fixtures (catalogue et devis) ─────────────────────────────────────────
// Prix de catalogue fictifs propres au test (ils ne sont imprimés nulle part
// ailleurs) ; les réponses serveur viennent des exemples de contrat COMMITTÉS.
export const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
export const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}
export const ONDULEUR_TRI = {
  id: 103, nom: 'Onduleur réseau 50kW Triphasé', prix_vente: 60000, tva: 20,
  is_archived: false, prix_achat: 45000,
}
export const CABLE = {
  id: 104, nom: 'Câble solaire 6mm²', prix_vente: 20, tva: 20,
  is_archived: false, prix_achat: 12,
}
// Pompe à courbe : SANS prix (QXG3 — les pompes OSP restent « prix à
// renseigner »), courbe débit→HMT du constructeur.
export const POMPE_COURBE = {
  id: 105, nom: 'Pompe immergée OSP 30-8', prix_vente: null, tva: 20,
  is_archived: false, prix_achat: null, pompe_kw: 5.5, tension_v: 380,
  courbe_pompe: [[0, 120], [10, 105], [20, 88], [30, 62], [36, 40]],
}
export const CATALOGUE = [PANNEAU, ONDULEUR, ONDULEUR_TRI, CABLE, POMPE_COURBE]

export const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'Golden', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

const ligne = (id, produit, quantite, prix, tva, ordre, extra = {}) => ({
  id, produit: produit.id, designation: produit.nom, quantite: String(quantite),
  prix_unitaire: String(prix), taux_tva: String(tva), ordre,
  type_ligne: 'produit', optionnelle: false, ...extra,
})

function enTete(id, mode, extra = {}) {
  return {
    id, reference: `DEV-202610-${String(id).padStart(4, '0')}`, statut: 'brouillon',
    modifiable: true, raison_non_modifiable: '', revision_possible: false,
    is_active: true, lead: null, client: 9, mode_installation: mode,
    taux_tva: '20.00', remise_globale: '0', ...extra,
  }
}

/** (c) devis ENVOYÉ résidentiel « Les deux » avec reco « Sans batterie ». */
export function devisEnvoyeLesDeux() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye')
  return {
    ...contrat, lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
    mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
    etude_params: {
      scenario: 'Les deux (Sans + Avec)',
      recommended_option: 'Sans batterie',
    },
    lignes: [
      ligne(1, PANNEAU, 8, '1200.00', '10.00', 0),
      ligne(2, ONDULEUR, 1, '9000.00', '20.00', 1),
    ],
  }
}

/** (d) industriel MT, consommation et profil déclarés (CIQ126 : plus de part diurne d'écran). */
export function devisIndustrielMt() {
  return enTete(401, 'industriel', {
    etude_params: {
      scenario: 'Sans batterie',
      tension: 'mt',
      puissance_souscrite_kva: 250,
      consommation: { kwh_annuel: 420000 },
    },
    lignes: [
      ligne(1, PANNEAU, 120, '1000.00', '10.00', 0),
      ligne(2, ONDULEUR_TRI, 1, '60000.00', '20.00', 1),
    ],
  })
}

/** (e) commercial hôtel. */
export function devisCommercialHotel() {
  return enTete(402, 'commercial', {
    etude_params: {
      scenario: 'Sans batterie',
      categorie_commerciale: 'hotel',
      tension: 'bt',
      consommation: { kwh_annuel: 90000 },
    },
    lignes: [
      ligne(1, PANNEAU, 40, '1000.00', '10.00', 0),
      ligne(2, ONDULEUR_TRI, 1, '60000.00', '20.00', 1),
    ],
  })
}

/** (f) agricole, pompe à courbe (sans prix). */
export function devisAgricolePompeCourbe() {
  return enTete(403, 'agricole', {
    // Entrées v2 (AGR130) : pompe neuve, volume déclaré, HMT saisie.
    etude_params: {
      mode_pompe: 'neuve',
      besoin: { mode: 'volume_declare', volume_m3_jour: 120, debit_souhaite_m3h: 18 },
      hmt_entrees: { saisie_m: 60 },
      type_pompe: 'immergee',
      alim: 'solaire',
    },
    lignes: [
      ligne(1, PANNEAU, 14, '1000.00', '10.00', 0),
      ligne(2, POMPE_COURBE, 1, '0.00', '20.00', 1),
    ],
  })
}

/** (g) multi-villas : une ligne commune, deux groupes nommés. */
export function devisMultiVillas() {
  return enTete(404, 'residentiel', {
    etude_params: { scenario: 'Sans batterie' },
    lignes: [
      ligne(1, CABLE, 50, '20.00', '20.00', 0, { groupe_index: 0, groupe_label: '' }),
      ligne(2, PANNEAU, 8, '1200.00', '10.00', 1, { groupe_index: 1, groupe_label: 'Villa A' }),
      ligne(3, ONDULEUR, 1, '9000.00', '20.00', 2, { groupe_index: 2, groupe_label: 'Villa B' }),
    ],
  })
}

/** (h) devis rouvert par un admin, registre de surcharges NON vide. */
export function devisAdminRegistre() {
  return enTete(405, 'residentiel', {
    etude_params: { scenario: 'Sans batterie' },
    lignes: [
      ligne(4231, PANNEAU, 14, '1200.00', '10.00', 0),
      ligne(4235, ONDULEUR, 1, '9000.00', '20.00', 1),
    ],
  })
}

/** (i) résidentiel dont l'aperçu d'étude horaire serveur répond. */
export function devisResidentielEtudeHoraire() {
  return enTete(406, 'residentiel', {
    etude_params: { scenario: 'Sans batterie' },
    lignes: [
      ligne(1, PANNEAU, 8, '1200.00', '10.00', 0),
      ligne(2, ONDULEUR, 1, '9000.00', '20.00', 1),
    ],
  })
}

// ── Environnement et chargement NEUF partagés par tous les goldens ─────────
const ECOUTEURS_MQL = [
  'addListener', 'removeListener', 'addEventListener', 'removeEventListener', 'dispatchEvent',
]
const fabriqueMql = (q) => ({
  matches: false, media: q, onchange: null,
  ...Object.fromEntries(ECOUTEURS_MQL.map((nom) => [nom, vi.fn()])),
})

/** À appeler dans `beforeEach` : date figée, stockages vides, polyfills jsdom. */
export function preparerEnvironnement({ confirmeAccepte = false } = {}) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(DATE_FIGEE)
  for (const stockage of ['localStorage', 'sessionStorage']) {
    try { window[stockage].clear() } catch { /* stockage indisponible */ }
  }
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) window.matchMedia = vi.fn().mockImplementation(fabriqueMql)
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
  // Hors <ConfirmProvider>, useConfirm retombe sur window.confirm (jsdom ne
  // l'implémente pas) : stub accepté, ses appels sont figés par les gestes.
  if (confirmeAccepte) window.confirm = vi.fn(() => true)
}

/**
 * Charge un jeu de modules NEUF (compteur `_keyCounter` de module remis à 0)
 * et renvoie les API mockées de CE jeu + l'écran.
 */
export async function chargerNeuf(catalogue = CATALOGUE) {
  // Les fabriques vi.mock sont mises en cache par vitest : sans remise à zéro,
  // les appels et les réponses d'un scénario fuiraient dans le suivant.
  // mockReset rend à chaque vi.fn son implémentation d'origine (la fabrique).
  vi.resetAllMocks()
  vi.resetModules()
  const modules = await Promise.all([
    import('../../api/crmApi'), import('../../api/stockApi'),
    import('../../api/parametresApi'), import('../../api/ventesApi'),
    import('../../api/axios'), import('./DevisGenerator'),
  ])
  const [crm, stock, parametres, ventes, axios, gen] = modules
  const apis = {
    crmApi: crm.default, stockApi: stock.default, parametresApi: parametres.default,
    ventesApi: ventes.default, api: axios.default,
  }
  apis.stockApi.getProduits.mockResolvedValue({ data: catalogue })
  return { ...apis, DevisGenerator: gen.default }
}
