import { vi } from 'vitest'

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
      ...surcharge,
    },
  }
}
