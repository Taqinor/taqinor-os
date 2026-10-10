import { vi } from 'vitest'

/* Shims jsdom PARTAGÉS des tests de l'écran générateur de devis.

   Le bloc « scrollIntoView / matchMedia / ResizeObserver » était recopié dans
   chaque test (ACAL345, `scripts/check_duplicats_litteraux.py`, refuse tout
   bloc de >= 6 lignes significatives copié dans deux fichiers). Les tests
   l'appellent désormais depuis leur `beforeEach`. */

/** Pose chaque shim seulement si jsdom n'en fournit pas. */
export function installerShimsJsdom({ pointerCapture = false } = {}) {
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (pointerCapture) {
    if (!Element.prototype.hasPointerCapture) Element.prototype.hasPointerCapture = () => false
    if (!Element.prototype.releasePointerCapture) Element.prototype.releasePointerCapture = () => {}
  }
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

/**
 * Corps commun des `beforeEach` des tests d'édition du générateur : remise à
 * zéro des mocks et du stockage, shims jsdom, enregistrements qui réussissent.
 */
export function reinitialiserEdition(ventesApi) {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  installerShimsJsdom()
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
}

/** Corps commun des `beforeEach` à date figée : horloge, stockage, shims. */
export function preparerEcranFige(date, options) {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(date)
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
  installerShimsJsdom(options)
}
