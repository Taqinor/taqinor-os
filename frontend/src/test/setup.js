import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

/* Radix UI (Select, Dropdown…) s'appuie sur des APIs de pointeur/scroll que
   jsdom n'implémente pas : sans ces stubs, `user.click` n'ouvre jamais le
   menu (l'option cherchée reste introuvable). On les neutralise globalement. */
if (typeof window !== 'undefined') {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {}
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {}
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {}
  }
  /* Radix (Slider, ResponsiveDialog…) et les sparklines observent la taille :
     jsdom n'a pas ResizeObserver. Stub global (un no-op) pour ne pas répéter le
     polyfill dans chaque fichier de test. */
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
}

/* jsdom est recréé entre fichiers mais pas entre tests : on démonte le DOM
   après chaque test pour garder les `getByRole`/`getByLabelText` déterministes. */
afterEach(() => {
  cleanup()
})
