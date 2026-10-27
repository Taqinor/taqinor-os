import { vi } from 'vitest'

/* Fabriques de mocks partagées par les tests d'InterventionCapturePanels
   (check_duplicats_litteraux). Les `vi.mock(...)` restent dans chaque test
   (hoistage) ; le contenu vient d'ici par import dynamique. */

export const fieldOutboxMock = (outbox) => ({
  withOfflineFallback: outbox.withOfflineFallback,
  queuePhoto: outbox.queuePhoto,
  FIELD_OPS: outbox.FIELD_OPS,
})

export const prefsMock = () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
})
