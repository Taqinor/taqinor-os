import { vi, beforeEach, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/* Neutralisations COMMUNES des suites LeadWorkspace (ENF19) : les enfants qui
   feraient un appel réseau au montage sont remplacés une fois pour toutes.
   Importer ce module (de préférence en PREMIER) enregistre ces `vi.mock` ;
   `LeadDevisPanel` / `SigneDialog` / rails restent propres à chaque suite (un
   `vi.mock` posé ici écraserait celui de la suite, enregistré avant). Le module
   ne dépend d'aucun composant : il est sûr à charger depuis une fabrique. */
vi.mock('../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
vi.mock('../features/crm/useCanaux', () => ({ default: () => ({ labels: { walk_in: 'Visite/Walk-in' } }) }))
vi.mock('../components/AssigneePicker', () => ({ default: () => <div data-testid="assignee" /> }))
vi.mock('../components/CustomFieldsInput', () => ({ default: () => null }))
vi.mock('../pages/crm/leads/AppointmentBooker', () => ({ default: () => null }))
vi.mock('../pages/crm/leads/PlanActiviteDialog', () => ({ default: () => null }))
vi.mock('../pages/crm/leads/ConvertirClientDialog', () => ({ default: () => null }))
vi.mock('../api/axios', () => ({
  default: { get: vi.fn(() => Promise.resolve({ data: [] })) },
}))

export const LEAD_A = { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false }

export function mockMatchMedia(mobile) {
  window.matchMedia = (query) => ({
    matches: mobile, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}

/** Hooks communs : media query desktop, stockage vidé avant ; nettoyage + mocks remis à zéro après. */
export function installerHooksLeadWorkspace() {
  beforeEach(() => { mockMatchMedia(false); try { localStorage.clear() } catch { /* noop */ } })
  afterEach(() => { cleanup(); vi.clearAllMocks() })
}

/** Rail identité intercepté : un bouton par entrée `[arguments d'onAction, libellé]`. */
export function identityRailMock(boutons = []) {
  return {
    default: ({ onAction }) => (
      <div data-testid="identity-rail">
        {boutons.map(([args, libelle]) => (
          <button key={libelle} type="button" onClick={() => onAction(...args)}>{libelle}</button>
        ))}
      </div>
    ),
  }
}

/** `crmApi` pour les suites qui montent les SECTIONS réelles (relance, photo-toit, ville). */
export function crmApiSections(surcharge = {}) {
  return {
    default: {
      getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
      getTags: vi.fn(() => Promise.resolve({ data: [] })),
      getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
      getLead: vi.fn(() => Promise.resolve({ data: { id: 1, nom: 'Ali', prenom: 'Ben', stage: 'NEW', is_archived: false } })),
      getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
      getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
      getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
      updateLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      // MRY15 — SectionPipeline (rendu réel) monte CadenceFrise en mode édition.
      getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
      // VT13 — SectionSite monte TraceToitClient, qui lit la photo-toit du lead.
      getLeadPhotoToit: vi.fn(() => Promise.resolve({ data: { visite_id: null, url: null, texture_calage: null } })),
      villeStatut: vi.fn(() => Promise.resolve({ data: { statut: 'connue' } })),
      // F4 — raccourci « ⋯ » du rail (onAction('relance-cadence')).
      initialiserRelance: vi.fn(() => Promise.resolve({ data: [{ id: 1 }] })),
      ...surcharge,
    },
  }
}

/** Objet `vi.mock('…/api/crmApi')` de base (lectures vides) ; `surcharge` remplace des clés. */
export function crmApiLeadWorkspace(surcharge = {}) {
  return {
    default: {
      getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
      getTags: vi.fn(() => Promise.resolve({ data: [] })),
      getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })),
      getLead: vi.fn(() => Promise.resolve({ data: {} })),
      getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
      getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
      getLeadPointsContact: vi.fn(() => Promise.resolve({ data: null })),
      // CRX37 — jalons devis fusionnés dans la timeline (enrichissement passif).
      getLeadJalonsDevis: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      // SectionPipeline lit la cadence du lead (cadence active ?) au montage.
      getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
      whatsappDevis: vi.fn(() => Promise.resolve({ data: {} })),
      logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
      mergeLeads: vi.fn(() => Promise.resolve({ data: {} })),
      updateLead: vi.fn(() => Promise.resolve({ data: {} })),
      createLead: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
      archiverLead: vi.fn(() => Promise.resolve({ data: {} })),
      restaurerLead: vi.fn(() => Promise.resolve({ data: {} })),
      ...surcharge,
    },
  }
}
