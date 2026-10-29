import { vi } from 'vitest'
import { reponseContrat } from './fixtures/contractSamples'

/* Neutralisations COMMUNES des suites « Suivi des relances » (ENF19) : le hook
   de rôle est un mock réassignable par test (`isAdminOrResponsableMock`) et
   `useSelector` ne lit que `auth.user.id` (pas de vrai Provider redux). Importer
   ce module (de préférence en PREMIER) enregistre ces `vi.mock`. */
export const isAdminOrResponsableMock = vi.fn(() => false)

vi.mock('../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

/** `crmApi` de base de l'écran ; `surcharge` remplace/ajoute des méthodes. */
export function crmApiSuivi(surcharge = {}) {
  return {
    default: {
      getRelanceEtapesSuivi: vi.fn(),
      getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      marquerRelanceEtapeFait: vi.fn(),
      marquerRelanceEtapeSautee: vi.fn(),
      reporterRelanceEtape: vi.fn(),
      getRelanceEtapeMessage: vi.fn(),
      whatsappRelanceEtape: vi.fn(),
      // SUIVI-ÉQUIPE — la vue d'équipe (rôles responsable/admin) lit le contrat
      // `controle_suivi` ; par défaut la société vide (`exemple_vide`), jamais
      // une forme retapée à la main (PACT10).
      getControleSuivi: vi.fn(() => Promise.resolve(
        reponseContrat('crm', 'controle_suivi', 'exemple_vide'))),
      ...surcharge,
    },
  }
}
