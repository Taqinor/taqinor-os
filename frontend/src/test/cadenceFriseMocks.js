import { vi } from 'vitest'

/* `crmApi` COMMUN des suites de la frise de cadence et du cockpit « Relances du
   jour » (ENF19) : lecture des étapes (fiche lead / cockpit) + gestes
   Fait/Sauter/Reporter/WhatsApp. À appeler depuis une fabrique `vi.mock`
   (`async () => (await import('…/test/cadenceFriseMocks')).crmApiFrise({ … })`).
   `surcharge` ajoute ou remplace des méthodes. */
export function crmApiFrise(surcharge = {}) {
  return {
    default: {
      getRelanceEtapesLead: vi.fn(),
      getRelanceEtapesDues: vi.fn(),
      marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
      marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
      reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
      getRelanceEtapeMessage: vi.fn(),
      whatsappRelanceEtape: vi.fn(),
      ...surcharge,
    },
  }
}
