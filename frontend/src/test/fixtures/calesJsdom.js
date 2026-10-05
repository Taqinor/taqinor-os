// ACAL345 — cales jsdom partagées (scrollIntoView, matchMedia, ResizeObserver)
// pour les tests d'écrans lourds, au lieu d'être recopiées dans chaque fichier.
import { vi } from 'vitest'

export function installerCalesJsdom() {
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
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
