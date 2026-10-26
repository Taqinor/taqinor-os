import { vi } from 'vitest'

/* Fabriques de mocks partagées par les tests de ChantierChecklist
   (check_duplicats_litteraux). Chaque test garde ses `vi.mock(...)` (hoistés)
   et délègue le contenu à ces fonctions via un import dynamique. */

export const recordsApiMock = () => ({ default: { uploadAttachment: vi.fn() } })

export const prefsMock = () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
})

/** Forme RÉELLE de `withOfflineFallback` : une erreur applicative (avec
    `response`) est relancée, sinon { queued:false, data:<réponse brute> }. */
export const fieldOutboxMock = (cocherOp) => ({
  withOfflineFallback: (fn) => fn().then((data) => ({ queued: false, data })),
  FIELD_OPS: { COCHER_CHECKLIST: cocherOp },
})
