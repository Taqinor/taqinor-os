import { vi } from 'vitest'

/* Fabriques `vi.mock` COMMUNES des suites SectionPipeline (ENF19). À appeler
   depuis une fabrique : `vi.mock('…/api/crmApi', async () => (await
   import('…/test/sectionPipelineMocks')).crmApiPipeline())`. */

/** `crmApi` minimal de la section Suivi commercial (relance, arrêt, frise, canaux). */
export function crmApiPipeline() {
  return {
    default: {
      initialiserRelance: vi.fn(),
      arreterCadence: vi.fn(),
      // CadenceFrise se charge elle-même au montage (mode édition).
      getRelanceEtapesLead: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
      // useCanaux() appelle getCanaux() au montage — sans ce stub, chaque test
      // crashe AVANT d'atteindre le bouton testé.
      getCanaux: vi.fn(() => Promise.resolve({ data: [] })),
    },
  }
}

/** `ui/confirm` : toasts espions, `toastPromise` ne fait que renvoyer sa promesse. */
export function confirmToastMock() {
  return {
    toast: { success: vi.fn(), error: vi.fn() },
    toastPromise: vi.fn((p) => p),
  }
}
