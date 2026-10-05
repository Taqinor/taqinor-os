/* Harnais PARTAGÉ des tests de l'écran ToitureDesign (SPL194, SPL213-216).

   Les sept fichiers `ToitureDesign*.test.jsx` recopiaient les mêmes doubles
   (axios, ventesApi, crmApi, toast, builder simulé) et les mêmes helpers de
   rendu : chaque copie dérivait seule (garde ACAL345). Ce module les range en
   UN endroit. Ses `vi.mock` s'enregistrent avant l'import de l'écran. ORDRE :
   `toitureDesignHarnessCalepinage` et `toitureDesignHarnessNavigation` (si le
   test en a besoin) s'importent AVANT ce module, car il charge l'écran.
   Il n'est pas collecté comme test (pas de suffixe `.test.`). */
import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import crmApi from '../api/crmApi'
import ToitureDesign from '../pages/ventes/ToitureDesign'

vi.mock('../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../api/ventesApi', () => ({
  default: {
    getDevisDesignContext: vi.fn(),
    // PV75 — devis complet (etude_params.simulation.pr), lu EN PARALLÈLE du
    // design-context pour l'étude bancable ; par défaut aucune étude rangée
    // (payload sans `etude_params`) pour que les tests écrits avant PV75
    // restent inchangés.
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    syncDevisLayout: vi.fn(),
    shareLinkDevis: vi.fn(),
    whatsappPreviewDevis: vi.fn(),
    reviserDevis: vi.fn(),
  },
}))
// VT13 — l'écran interroge la porte VT12 `crmApi.getLeadPhotoToit` : défaut =
// la réponse « rien à montrer » du contrat (les TROIS clés à null). Seul
// `getLeadPhotoToit` est stubé : `getRoofFootprint` reste le VRAI client (les
// tests QJ25 le pilotent par le mock d'`api/axios`).
vi.mock('../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: {
      ...actual.default,
      getLeadPhotoToit: vi.fn(() => Promise.resolve({
        data: { visite_id: null, url: null, texture_calage: null },
      })),
    },
  }
})
vi.mock('../lib/toast', () => ({ toastInfo: vi.fn() }))

// ── Builder simulé ──────────────────────────────────────────────────────────
// Il expose seulement l'API que la page consomme, posée via `onApiReady`
// comme en vrai.
export const LAYOUT = { version: 2, zones: [{ id: 'z1' }] }
export const serializeLayout = vi.fn(() => LAYOUT)
export const snapshot = vi.fn(() => null)
export const setReferenceContourVisible = vi.fn()
export const recommencerDepuisTraceClient = vi.fn(() => true)
export const initRoofToolPro8 = vi.fn()
vi.mock('@roofbuilder', () => ({ initRoofToolPro8: (...a) => initRoofToolPro8(...a) }))

/** L'API du builder remise à la page (les quatre clés de base + `extra`). */
export function apiBuilder(extra = {}) {
  return {
    serializeLayout, snapshot, setReferenceContourVisible,
    recommencerDepuisTraceClient, ...extra,
  }
}

/** Le builder simulé appelle `onApiReady(apiBuilder(extra))` au boot. */
export function brancherBoot(extra = {}) {
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.(apiBuilder(extra))
  })
}

/** État de départ d'un test : garde de boot levée, builder de base rebranché. */
export function reinitialiserBoot(extra = {}) {
  delete window.__taqinorRoofBooted
  serializeLayout.mockReturnValue(LAYOUT)
  snapshot.mockReturnValue(null)
  brancherBoot(extra)
}

/** Boot minimal des câblages CALX : builder réduit à `serializeLayout`/`snapshot`. */
export function reinitialiserBootMinimal(extra = {}) {
  delete window.__taqinorRoofBooted
  initRoofToolPro8.mockImplementation((options) => {
    options?.onApiReady?.({
      serializeLayout: vi.fn(() => ({ version: 2, zones: [] })),
      snapshot: vi.fn(() => null),
      ...extra,
    })
  })
}

/** Les câblages CALX stubent l'empreinte OSM (`roof-footprint`) : réponse vide. */
export function stubberEmpreinteOsm() {
  crmApi.getRoofFootprint = vi.fn(() => Promise.resolve({ data: {} }))
}

// ── Écrans montés dans leur routeur ─────────────────────────────────────────
export function ecranCalepinage(id) {
  return (
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/:id"
          element={<ToitureDesign mode="calepinage" />} />
      </Routes>
    </MemoryRouter>
  )
}

export function ecranDevis(id, chemin = '/ventes/devis/:id/design') {
  return (
    <MemoryRouter initialEntries={[chemin.replace(':id', String(id))]}>
      <Routes>
        <Route path={chemin} element={<ToitureDesign mode="devis" />} />
      </Routes>
    </MemoryRouter>
  )
}

export function ecranLead(id = 88, chemin = '/devis-design/:id') {
  return (
    <MemoryRouter initialEntries={[chemin.replace(':id', String(id))]}>
      <Routes>
        <Route path={chemin} element={<ToitureDesign />} />
      </Routes>
    </MemoryRouter>
  )
}

export const rendreCalepinage = (id) => render(ecranCalepinage(id))
export const rendreDevis = (id, chemin) => render(ecranDevis(id, chemin))
export const rendreLead = (id, chemin) => render(ecranLead(id, chemin))

// ── Mode lead : la fiche et les deux GET qu'il émet ─────────────────────────
export const LEAD_88 = {
  id: 88, nom: 'Alaoui', prenom: 'Youssef', ville: 'Casablanca',
  telephone: '0600000000', roof_point: { lat: 33.5, lng: -7.6 },
  roof_outline: [[33.5, -7.6]], bill_kwh: 7200,
}

/** `api.get` répond à la fiche lead et à la config carte, rejette le reste. */
export function simulerApiLead(api, lead = LEAD_88, maptilerKey = 'k-lead') {
  api.get.mockImplementation((url) => {
    if (url.startsWith('/crm/leads/')) return Promise.resolve({ data: lead })
    if (url === '/ventes/roof-config/') {
      return Promise.resolve({ data: { available: true, maptilerKey } })
    }
    return Promise.reject(new Error(`URL inattendue ${url}`))
  })
}
