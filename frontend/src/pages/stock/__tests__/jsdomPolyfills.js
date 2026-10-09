import { vi } from 'vitest'

const METHODES_EVENEMENT = [
  'addListener', 'removeListener', 'addEventListener', 'removeEventListener', 'dispatchEvent',
]

// Polyfills jsdom requis par les écrans stock (ThemeProvider → matchMedia,
// listes → scrollIntoView) : un seul endroit pour les nouveaux tests.
export function installJsdomPolyfills() {
  window.matchMedia ??= vi.fn((requete) => ({
    matches: false,
    media: requete,
    onchange: null,
    ...Object.fromEntries(METHODES_EVENEMENT.map((nom) => [nom, vi.fn()])),
  }))
  Element.prototype.scrollIntoView ??= () => {}
}
